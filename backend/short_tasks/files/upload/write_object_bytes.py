import os
import base64
from typing import Dict, List
from pydantic import BaseModel, StrictInt, StrictStr, ValidationError, validator
from backend.api_types import FatalTaskError, AppResources

# Pydantic model for incoming write parameters
def get_max_file_size(path: str) -> int:
    return os.path.getsize(path)

class WriteBytesParams(BaseModel):
    object_id: StrictStr
    position: StrictInt
    data: StrictStr  # base64-encoded

    @validator('object_id')
    def object_id_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('object_id cannot be empty')
        return v

    @validator('position')
    def position_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError('position must be non-negative')
        return v

    @validator('data')
    def valid_base64(cls, v: str) -> str:
        try:
            # Validate base64
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError('data must be valid base64')
        return v


def task_write_object_bytes(args: Dict, app_resources: AppResources) -> Dict[str, int]:
    """
    Writes decoded bytes into an existing object file at a specified position.

    Args:
        args: dict with 'object_id', 'position', 'data'
        app_resources: holds bucket_path

    Returns:
        dict with 'bytes_written'
    """
    # 1. Validate input
    try:
        params = WriteBytesParams(**args)
    except ValidationError as exc:
        errors: List[str] = []
        for err in exc.errors():
            loc = err.get('loc', ['field'])[0]
            msg = err.get('msg', '')
            errors.append(f"{loc}: {msg}")
        raise FatalTaskError('Validation error', {'status': 400, 'errors': errors})

    object_id = params.object_id
    position = params.position
    data_b64 = params.data

    # 2. Resolve file path and check existence
    bucket_path = app_resources.bucket_path
    file_path = os.path.join(bucket_path, object_id)
    if not os.path.isfile(file_path):
        raise FatalTaskError(f"Object not found: {object_id}", {'status': 404})

    # 3. Decode data and check bounds
    try:
        blob = base64.b64decode(data_b64)
    except Exception as e:
        raise FatalTaskError(f"Failed to decode base64 data: {e}", {'status': 400})

    file_size = os.path.getsize(file_path)
    end_position = position + len(blob)
    if position > file_size:
        raise FatalTaskError("Write position is beyond end of file", {'status': 400})
    if end_position > file_size:
        raise FatalTaskError("Data write exceeds file bounds", {'status': 400})

    # 4. Write bytes at position
    try:
        with open(file_path, 'r+b') as f:
            f.seek(position)
            written = f.write(blob)
            f.flush()
    except OSError as e:
        raise FatalTaskError(f"File write error: {e}", {'status': 500})

    return {'bytes_written': written}
