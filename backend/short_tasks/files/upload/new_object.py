from typing import Dict, List, Iterable, Callable, TypeVar
import os
import uuid
import itertools
import mysql.connector
from pydantic import BaseModel, StrictInt, StrictStr, ValidationError, validator

from backend.api_types import FatalTaskError, AppResources

# Constants
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_TYPES = {
    "text/plain": {
        "description": "Plain Text",
        "extensions": ["txt"],
    },
    # Add other mime types as needed
}
MAX_RETRIES = 5

# Derive allowed extensions using list comprehension flattening
allowed_extensions: List[str] = [
    ext
    for type_info in ALLOWED_TYPES.values()
    for ext in type_info["extensions"]
]

# Pydantic model for incoming parameters
class NewObjectParams(BaseModel):
    name: StrictStr
    mime_type: StrictStr
    size: StrictInt

    @validator('size')
    def size_must_be_in_range(cls, v: int) -> int:
        if v < 0:
            raise ValueError('size must be non-negative')
        if v > MAX_FILE_SIZE:
            raise ValueError(f'size exceeds maximum limit of {MAX_FILE_SIZE}')
        return v

    @validator('name')
    def name_must_have_allowed_extension(cls, v: str) -> str:
        if '.' not in v:
            raise ValueError('missing file extension')
        ext = v.rsplit('.', 1)[-1]
        if ext not in allowed_extensions:
            raise ValueError(f'unsupported file extension: {ext}')
        return v

    @validator('mime_type')
    def mime_type_must_be_allowed(cls, v: str) -> str:
        if v not in ALLOWED_TYPES:
            raise ValueError(f'unsupported mime type: {v}')
        return v


def task_new_object(args: Dict, app_resources: AppResources) -> str:
    """
    API route logic: validate inputs, insert metadata, reserve file space.

    Args:
        args: dict with 'name', 'mime_type', 'size'
        app_resources: holds mysql_conn and bucket_path

    Returns:
        object_id (str): UUID of the newly created object.

    Raises:
        FatalTaskError on any validation or runtime failure.
    """
    # 1. Validate and parse
    try:
        params = NewObjectParams(**args)
    except ValidationError as exc:
        # Format errors for API response
        details: List[str] = []
        for err in exc.errors():
            loc = err.get('loc', ['field'])[0]
            msg = err.get('msg', '')
            details.append(f"{loc}: {msg}")
        raise FatalTaskError(
            'Validation error',
            {'status': 400, 'errors': details}
        )

    name = params.name
    mime_type = params.mime_type
    size = params.size

    # 2. Insert into database with UUID retry logic
    mysql_conn = app_resources.mysql_conn
    bucket_path = app_resources.bucket_path
    object_id = str(uuid.uuid4())

    for attempt in range(MAX_RETRIES):
        try:
            cursor = mysql_conn.cursor()
            cursor.execute(
                "INSERT INTO objects (id, name, mime_type, size) VALUES (%s, %s, %s, %s)",
                (object_id, name, mime_type, size)
            )
            mysql_conn.commit()
            cursor.close()
            break
        except mysql.connector.Error as err:
            cursor.close()
            # Duplicate key error code 1062: retry
            if err.errno == 1062 and attempt < MAX_RETRIES - 1:
                object_id = str(uuid.uuid4())
                continue
            if err.errno == 1062:
                raise FatalTaskError(
                    'Failed to generate unique object ID after multiple attempts',
                    {'status': 500}
                )
            raise FatalTaskError(f'Database error: {err}', {'status': 500})

    # 3. Reserve file storage
    file_path = os.path.join(bucket_path, object_id)
    try:
        with open(file_path, 'wb') as f:
            f.truncate(size)
    except OSError as e:
        # Optionally roll back DB insert here
        raise FatalTaskError(f'Could not create object file: {e}', {'status': 500})

    return object_id
