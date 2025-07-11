import eventlet
# 1) Monkey‐patch for Eventlet
eventlet.monkey_patch()



# app.py
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict
import uuid
from dotenv import dotenv_values
from backend.api_types import TaskContext, FatalTaskError
import os
import traceback
from termcolor import colored

from backend.tasks.version import version_task
from backend.tasks.progress_test import progress_test_task


env_vars = dotenv_values(os.path.join(os.path.dirname(__file__), '.env'))

if "SECRET_KEY" not in env_vars:
    raise ValueError("Missing SECRET_KEY environment variable")

app = Flask(__name__)
app.config['SECRET_KEY'] = env_vars['SECRET_KEY']
socketio = SocketIO(app, async_mode='eventlet')

TASKS: Dict[str, Callable[[TaskContext, dict], Any]] = {}

def register_task(name: str, fn: Callable[[TaskContext, dict], Any]):
    TASKS[name] = fn

register_task('version', version_task)
register_task('progress_test', progress_test_task)

# 6) HTTP endpoint to dispatch tasks
@app.route('/begin', methods=['POST'])
def begin_task():
    data = request.get_json(force=True)
    task_name = data.get('task')
    args = data.get('args', None)

    if task_name not in TASKS:
        return jsonify({"error": f"Unknown task '{task_name}'"}), 400

    # Create an unguessable room ID
    task_id = f"{task_name}:{uuid.uuid4()}"
    # Launch the task in background
    socketio.start_background_task(_run_task, task_name, task_id, args)

    return jsonify({"task_id": task_id}), 202


# 7) Internal runner
def _run_task(task_name: str, task_id: str, args: dict):
    ctx = TaskContext(room=task_id)
    handler = TASKS[task_name]

    try:
        result = handler(ctx, args)
        ctx.emit_success(result)
    except FatalTaskError as exc:
        ctx.emit_fatal_error(str(exc), cause=exc.cause)
    except Exception as exc:
        ctx.emit_fatal_error("An unknown server error occured. Please try again later.")
        print(colored(f"Server error occured upon user request: {str(exc)}","red"))
        print(colored(f"Traceback:","red"))
        traceback.print_exc()


# 8) Socket.IO “join room” handler
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
