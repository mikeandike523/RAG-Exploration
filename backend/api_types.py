from typing import Any, Optional, Union, Callable
from dataclasses import dataclass

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
    def __init__(self, room: str):
        self.room = room

    def emit_success(self, result: Any):
        payload = SuccessResponse(result=result)
        socketio.emit('success', asdict(payload), room=self.room)

    def emit_error(self, message: str, cause: Any = None):
        payload = ErrorResponse(message=message, cause=cause)
        socketio.emit('error', asdict(payload), room=self.room)

    def emit_fatal_error(self, message: str, cause: Any = None):
        payload = FatalErrorResponse(message=message, cause=cause)
        socketio.emit('fatal_error', asdict(payload), room=self.room)

    def emit_progress(self, current: int, total: int, name: Optional[str] = None):
        payload = ProgressResponse(current=current, total=total)
        socketio.emit('progress', asdict(payload), room=self.room)

    def emit_update(self, message: str, extra: Optional[Any] = None):
        payload = UpdateResponse(message=message, extra=extra)
        socketio.emit('update', asdict(payload), room=self.room)

    def emit_warning(self, message: str, extra: Optional[Any] = None):
        payload = WarningResponse(message=message,extra=extra)
        socketio.emit('warning', asdict(payload), room=self.room)
        

@dataclass
class AppResources:
    mysql_conn: mysql.connector.MySQLConnection
    bucket_path: str