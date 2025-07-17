import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict
import uuid
from dotenv import dotenv_values
from backend.api_types import TaskContext, FatalTaskError, ClientMessage, AppResources
import os
import traceback
from termcolor import colored
import mysql.connector
from src.utils.project_structure import get_project_root

from backend.short_tasks.files.upload.new_object import task_new_object

project_root = get_project_root()

env_vars = dotenv_values(os.path.join(os.path.dirname(__file__), '.env'))

if "SECRET_KEY" not in env_vars:
    raise ValueError("Missing SECRET_KEY environment variable")

redis_env_vars = dotenv_values(os.path.join(os.path.dirname(__file__),"..","servers","redis",".env"))
redis_url = f"redis://{redis_env_vars['REDIS_HOST']}:{redis_env_vars['REDIS_PORT']}/{redis_env_vars['REDIS_DB']}"

mysql_env_vars = dotenv_values(os.path.join(os.path.dirname(__file__), "..", "servers", "mysql", ".env"))
mysql_conn = mysql.connector.connect(
    host=mysql_env_vars.get('MYSQL_HOST', 'localhost'),
    port=int(mysql_env_vars.get('MYSQL_PORT', 3306)),
    user=mysql_env_vars['MYSQL_USER'],
    password=mysql_env_vars['MYSQL_PASSWORD'],
    database=mysql_env_vars['MYSQL_DATABASE'],
)

app = Flask(__name__)
app.config['SECRET_KEY'] = env_vars['SECRET_KEY']
socketio = SocketIO(app, async_mode='eventlet', message_queue=redis_url)

LONG_TASKS: Dict[str, Callable[[TaskContext, Any, AppResources], Any]] = {}

def register_long_task(name: str, fn: Callable[[TaskContext, dict], Any]):
    LONG_TASKS[name] = fn

SHORT_TASKS: Dict[str, Callable[[Any, AppResources], Any]] = {}

def register_short_task(name: str, fn: Callable[[Any], Any]):
    SHORT_TASKS[name] = fn

register_short_task('/files/upload/new-object', task_new_object)


app_resources = AppResources(
    mysql_conn=mysql_conn,
    bucket_path=os.path.join(project_root, 'bucket')
    )

@app.route('/run', methods=['POST'])
def run_short_task():
    data = request.get_json(force=True)
    task_name = data.get('task')
    args = data.get('args', None)

    if task_name not in SHORT_TASKS:
        return jsonify({"error": f"Unknown task '{task_name}'"}), 400

    handler = SHORT_TASKS[task_name]

    try:
        result = handler(args, app_resources)
    except FatalTaskError as exc:
        if exc.cause is not None:
            if isinstance(exc.cause, dict):
                if "status" in exc.cause:
                    return jsonify({"message": str(exc), "cause": exc.cause}), exc.cause["status"]
            return jsonify({"message": str(exc), "cause": exc.cause}), 500
        return jsonify({"message": str(exc)}), 500
    except Exception as exc:
        print(colored(f"Server error occured upon user request: {str(exc)}","red"))
        print(colored(f"Traceback:","red"))
        traceback.print_exc()
        return jsonify({"error": "An unknown server error occurred. Please try again later."}), 500


    return jsonify(result), 200    

@app.route('/begin', methods=['POST'])
def begin_task():
    data = request.get_json(force=True)
    task_name = data.get('task')
    args = data.get('args', None)

    if task_name not in LONG_TASKS:
        return jsonify({"error": f"Unknown task '{task_name}'"}), 400

    task_id = f"{task_name}:{uuid.uuid4()}"
    socketio.start_background_task(_run_long_task, task_name, task_id, args)

    return jsonify({"task_id": task_id}), 202

def _run_long_task(task_name: str, task_id: str, args: dict):

    ctx = TaskContext(room=task_id)
    handler = TASKS[task_name]

    try:
        result = handler(ctx, args, app_resources)
        ctx.emit_success(result)
    except FatalTaskError as exc:
        ctx.emit_fatal_error(str(exc), cause=exc.cause)
    except Exception as exc:
        ctx.emit_fatal_error("An unknown server error occured. Please try again later.")
        print(colored(f"Server error occured upon user request: {str(exc)}","red"))
        print(colored(f"Traceback:","red"))
        traceback.print_exc()


@socketio.on('join')
def on_join(data):
    task_id = data.get('task_id')
    if not task_id:
        emit('error', asdict(ErrorResponse(message="No task_id provided")))
        return

    join_room(task_id)
    emit('update', asdict(UpdateResponse(message=f"Joined room {task_id}")))


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=env_vars.get("PORT", 5000), debug=True)
