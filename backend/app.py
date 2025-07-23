import json
import eventlet

eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from dataclasses import asdict
from typing import Any, Callable, Dict
import uuid
from dotenv import dotenv_values
from backend.api_types import (
    ErrorResponse,
    TaskContext,
    FatalTaskError,
    AppResources,
    UpdateResponse,
)
import os
import traceback
from termcolor import colored
import mysql.connector
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer


from src.utils.project_structure import get_project_root

from backend.short_tasks.files.upload.new_object import task_new_object
from backend.short_tasks.files.upload.write_object_bytes import task_write_object_bytes
from backend.short_tasks.documents.create import task_create as task_create_document
from backend.short_tasks.documents.preprocess import task_preprocess
from backend.short_tasks.documents.get_metadata import task_get_metadata

from backend.long_tasks.documents.ingest_sentences import task_ingest_sentences

project_root = get_project_root()

backend_folder = os.path.join(project_root, "backend")

logs_folder = os.path.join(backend_folder, "logs")

logs_file_debug = os.path.join(logs_folder, "debug.txt")

def print_to_debug_log(message, *args, **kwargs):
    with open(logs_file_debug, "a") as fl:
        print(message, *args, file=fl, flush=True, **kwargs)

print_to_debug_log("Loading env vars...")

env_vars = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))

if "SECRET_KEY" not in env_vars:
    raise ValueError("Missing SECRET_KEY environment variable")

redis_env_vars = dotenv_values(
    os.path.join(os.path.dirname(__file__), "..", "servers", "redis", ".env")
)
redis_url = f"redis://{redis_env_vars['REDIS_HOST']}:{redis_env_vars['REDIS_PORT']}/{redis_env_vars['REDIS_DB']}"

mysql_env_vars = dotenv_values(
    os.path.join(os.path.dirname(__file__), "..", "servers", "mysql", ".env")
)

qdrant_env_vars = dotenv_values(
    os.path.join(os.path.dirname(__file__), "..", "servers", "qdrant", ".env")
)

print_to_debug_log("Done.")

print_to_debug_log("Connecting to MySQL...")

mysql_conn = mysql.connector.connect(
    host=mysql_env_vars.get("MYSQL_HOST", "localhost"),
    port=int(mysql_env_vars.get("MYSQL_PORT", 3306)),
    user=mysql_env_vars["MYSQL_USER"],
    password=mysql_env_vars["MYSQL_PASSWORD"],
    database=mysql_env_vars["MYSQL_DATABASE"],
)

print_to_debug_log("Done.")

print_to_debug_log("Connecting to Qdrant...")

qdrant_client = QdrantClient(
    url=f"http://localhost:{qdrant_env_vars['QDRANT_HTTP_PORT']}"
)

print_to_debug_log("Done.")

print_to_debug_log("Loading SentenceTransformer (all-MiniLM-L6-v2)...")

# Use GPU0 specifically, not any other GPU
embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cuda:0")

print("Done.")

print("Structuring app and defining routes...")

app = Flask(__name__)

app.config["SECRET_KEY"] = env_vars["SECRET_KEY"]

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    message_queue=redis_url,
    logger=True,  # prints Socket.IO events
    engineio_logger=True,  # prints Engine.IO debug info
)

# Workaround for cors_allowed_origins="*" not working as library documentation intended
# Had same issues with explicit allowed origins as well such as http://localhost:3000
#     I even tried both single string and list-of strings as the value, both had same issue
# This code is, esentially, doing the work that the internal CORS management should have done
# Using this code, the app works perfectly
# I saw some sources mentioning:

# 1. WSGI server may strip the allow origin headers
# -- I doubt it as I am using the built in wsgi server made by using socketio.run
# 2. bug in newest version of libraries or library compatibility issue
# I tried downgrading and I got the same issue and if I tried downgrading too far (such as downgrading to version 4 of flask-socketio)
# it just did not load at all (was not compatible with latest flask)
# I do not want to downgrade all tools incredibly far due to security concerns

# I may post on stackoverflow but I am worried since there are many similarly named posts that, though not relevant, will muddy the discussion
# I am considering raising a github issue but the work to make a minimal example repository is a lot
# Either way, need to do those later as I am too busy right now


@app.after_request
def apply_cors_after(response):
    # 1) Always allow the Origin that made the request (or * as fallback)
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")

    # 2) Tell the browser which methods we support
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    )

    # 3) Echo back any custom headers the client asked to use
    response.headers["Access-Control-Allow-Headers"] = request.headers.get(
        "Access-Control-Request-Headers", "Content-Type, Authorization"
    )

    # 4) If you need to include cookies/auth credentials
    response.headers["Access-Control-Allow-Credentials"] = "true"

    # 5) For a preflight (OPTIONS) request, return no content
    if request.method == "OPTIONS":
        response.status_code = 204

    return response


LONG_TASKS: Dict[str, Callable[[TaskContext, Any, AppResources], Any]] = {}


def register_long_task(name: str, fn: Callable[[TaskContext, dict], Any]):
    LONG_TASKS[name] = fn


SHORT_TASKS: Dict[str, Callable[[Any, AppResources], Any]] = {}


def register_short_task(name: str, fn: Callable[[Any], Any]):
    SHORT_TASKS[name] = fn


register_short_task("/files/upload/new-object", task_new_object)
register_short_task("/files/upload/write-object-bytes", task_write_object_bytes)
register_short_task("/documents/create", task_create_document)
register_short_task("/documents/preprocess", task_preprocess)
register_short_task("/documents/get-metadata", task_get_metadata)


register_long_task("/documents/ingest-sentences", task_ingest_sentences)


app_resources = AppResources(
    mysql_conn=mysql_conn,
    qdrant_client=qdrant_client,
    bucket_path=os.path.join(project_root, "bucket"),
    print_to_debug_log=print_to_debug_log,
    embedding_model=embedding_model
)

@app.route("/run", methods=["POST"])
def run_short_task():
    body_text = request.get_data(as_text=True)

    try:
        data = json.loads(body_text)
    except json.JSONDecodeError:
        print_to_debug_log(colored(f'/run -- Bad Input Data', "red"))
        return jsonify({"error": "Bad input data. Request body must eb valid JSON."}), 400

    if not isinstance(data, dict) or "task" not in data:
        print_to_debug_log(colored(f'/run -- Bad Input Data', "red"))
        return jsonify({"error": "Bad input data. Requestion body must be a JSON object with `task` and optionally `args` field."}), 400

    task_name = data.get("task")

    if task_name not in SHORT_TASKS:
        print_to_debug_log(colored(f'/run -- Unknown Task "{task_name}"', "red"))
        return jsonify({"error": f"Bad input data. Unknown task '{task_name}'"}), 400

    args = data.get("args", None)

    if args is not None:
        print_to_debug_log(colored(f'/run -- Starting task "{task_name}", input args type="{type(args)}"', "blue"))
    else:
        print_to_debug_log(colored(f'/run -- Starting task "{task_name}", no input args', "blue"))


    handler = SHORT_TASKS[task_name]

    try:
        result = handler(args, app_resources)
    except FatalTaskError as exc:
        print_to_debug_log(colored(f"Server error occured upon user request: {str(exc)}", "red"))
        print_to_debug_log(colored(f"Traceback:", "red"))
        print_to_debug_log(traceback.format_exc())
        if exc.cause is not None:
            if isinstance(exc.cause, dict):
                if "status" in exc.cause:
                    return (
                        jsonify({"message": str(exc), "cause": exc.cause}),
                        exc.cause["status"],
                    )
            return jsonify({"message": str(exc), "cause": exc.cause}), 500
        return jsonify({"message": str(exc)}), 500
    except Exception as exc:
        print_to_debug_log(colored(f"Server error occured upon user request: {str(exc)}", "red"))
        print_to_debug_log(colored(f"Traceback:", "red"))
        print_to_debug_log(traceback.format_exc())
        return (
            jsonify(
                {"error": "An unknown server error occurred. Please try again later."}
            ),
            500,
        )

    return jsonify(result), 200


@app.route("/begin", methods=["POST"])
def begin_task():
    body_text = request.get_data(as_text=True)

    try:
        data = json.loads(body_text)
    except json.JSONDecodeError:
        print_to_debug_log(colored(f'/begin -- Bad Input Data', "red"))
        return jsonify({"error": "Bad input data. Request body must be valid JSON."}), 400

    if not isinstance(data, dict) or "task" not in data:
        print_to_debug_log(colored(f'/begin -- Bad Input Data', "red"))
        return jsonify({"error": "Bad input data. Request body must be a JSON object with `task` and optionally `args` field."}), 400

    task_name = data.get("task")
    args = data.get("args", None)

    if task_name not in LONG_TASKS:
        print_to_debug_log(colored(f'/begin -- Unknown Task "{task_name}"', "red"))
        return jsonify({"error": f"Bad input data. Unknown task '{task_name}'"}), 400

    if args is not None:
        print_to_debug_log(colored(f"/begin -- Starting long task '{task_name}', input args type='{type(args)}'", "blue"))
    else:
        print_to_debug_log(colored(f"/begin -- Starting long task '{task_name}', no input args", "blue"))

    task_id = f"{task_name}:{uuid.uuid4()}"

    try:
        socketio.start_background_task(_run_long_task, task_name, task_id, args)
    except Exception as exc:
        print_to_debug_log(colored(f"/begin -- Failed to start background task '{task_name}': {str(exc)}", "red"))
        print_to_debug_log(colored("Traceback:", "red"))
        print_to_debug_log(traceback.format_exc())
        return jsonify({"error": "An unknown server error occurred. Please try again later."}), 500

    return jsonify({"task_id": task_id}), 202


def _run_long_task(task_name: str, task_id: str, args: dict):
    ctx = TaskContext(room=task_id, socketio=socketio)
    handler = LONG_TASKS[task_name]

    try:
        print_to_debug_log(colored(f"_run_long_task -- Running '{task_name}' with task_id='{task_id}'", "blue"))
        result = handler(ctx, args, app_resources)
        ctx.emit_success(result)
        print_to_debug_log(colored(f"_run_long_task -- Completed '{task_name}' task_id='{task_id}'", "green"))
    except FatalTaskError as exc:
        ctx.emit_fatal_error(str(exc), cause=exc.cause)
        print_to_debug_log(colored(f"_run_long_task -- FatalTaskError in '{task_name}' task_id='{task_id}': {str(exc)}", "red"))
        if exc.cause:
            print_to_debug_log(colored(f"Cause: {exc.cause}", "red"))
        print_to_debug_log(colored("Traceback:", "red"))
        print_to_debug_log(traceback.format_exc())
    except Exception as exc:
        ctx.emit_fatal_error("An unknown server error occurred. Please try again later.")
        print_to_debug_log(colored(f"_run_long_task -- Unknown error in '{task_name}' task_id='{task_id}': {str(exc)}", "red"))
        print_to_debug_log(colored("Traceback:", "red"))
        print_to_debug_log(traceback.format_exc())


@socketio.on("join")
def on_join(data):
    task_id = data.get("task_id")
    if not task_id:
        emit("error", asdict(ErrorResponse(message="No task_id provided")))
        return

    join_room(task_id)

print_to_debug_log("Done.")

if __name__ == "__main__":

    print_to_debug_log("Running main procedure...")
    socketio.run(app, host="localhost", port=env_vars.get("PORT", 5050), debug=True)
    print("Done running main procedure.")