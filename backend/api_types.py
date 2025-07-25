from typing import Any, Optional, Callable
from dataclasses import asdict, dataclass

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import mysql.connector

# 2) Define your response dataclasses
@dataclass
class SuccessResponse:
    result: Any = None

@dataclass
class ErrorResponse:
    message: str
    cause: Optional[Any] = None

@dataclass
class FatalErrorResponse:
    message: str
    cause: Optional[Any] = None

@dataclass
class ProgressResponse:
    current: int
    total: int
    name: Optional[str] = None

@dataclass
class UpdateResponse:
    message: str
    extra: Optional[Any] = None

@dataclass
class WarningResponse:
    message: str
    extra: Optional[Any] = None

@dataclass
class FatalTaskError(Exception):
    
    def __init__(self, message: str, cause: Any = None):
        super().__init__(message)
        self.cause = cause

@dataclass
class ClientMessage:
    action: str
    payload: Optional[Any] = None

# 3) A simple context to wrap emits into the room
class TaskContext:
    def __init__(self, room: str, socketio):
        self.room = room
        self.socketio=socketio

    def emit_success(self, result: Any):
        payload = SuccessResponse(result=result)
        self.socketio.emit('success', asdict(payload), room=self.room)

    def emit_error(self, message: str, cause: Any = None):
        payload = ErrorResponse(message=message, cause=cause)
        self.socketio.emit('error', asdict(payload), room=self.room)

    def emit_fatal_error(self, message: str, cause: Any = None):
        payload = FatalErrorResponse(message=message, cause=cause)
        self.socketio.emit('fatal_error', asdict(payload), room=self.room)

    def emit_progress(self, current: int, total: int, name: Optional[str] = None):
        payload = ProgressResponse(current=current, total=total, name=name)
        self.socketio.emit('progress', asdict(payload), room=self.room)

    def emit_update(self, message: str, extra: Optional[Any] = None):
        payload = UpdateResponse(message=message, extra=extra)
        self.socketio.emit('update', asdict(payload), room=self.room)

    def emit_warning(self, message: str, extra: Optional[Any] = None):
        payload = WarningResponse(message=message,extra=extra)
        self.socketio.emit('warning', asdict(payload), room=self.room)
        

@dataclass
class AppResources:
    mysql_conn: mysql.connector.MySQLConnection
    qdrant_client: QdrantClient
    embedding_model: SentenceTransformer
    bucket_path: str
    print_to_debug_log: Callable[[Any],None]
