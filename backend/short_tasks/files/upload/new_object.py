from typing import TypedDict

import uuid

from backend.api_types import FatalTaskError, AppResources

MAX_FILE_SIZE = 20 * 1024 * 1024
const ALLOWED_TYPES = {
  "text/plain": {
    "description": "Plain Text",
    "extensions": ["txt"],
  },
}

# Defive allowed extensions

allowed_extensions = []
for type_info in ALLOWED_TYPES.values():
    allowed_extensions.extend(type_info["extensions"])

class RouteParams(TypedDict):
    name: str
    mime_type: str
    size: int

def task_new_object(args, app_resources: AppResources):
    name = args.get('name')
    mime_type = args.get('mime_type')
    size = args.get('size')

    if not name or not mime_type or not size:
        raise FatalTaskError("Missing required parameters", {"status":400})

    if not isinstance(name, str) or not isinstance(mime_type, str) or not isinstance(size, int):
        raise FatalTaskError("Invalid parameter types", {"status": 400})    

    if size < 0:
        raise FatalTaskError("Invalid file size", {"status": 400})

    if size > MAX_FILE_SIZE:
        raise FatalTaskError("File size exceeds maximum limit", {"status": 413})

    if "." not in name:
        raise FatalTaskError("File must have an extension.", {"status": 400})

    ext = os.path.splitext(name)[1].lower()

    if ext not in allowed_extensions:
        raise FatalTaskError(f"Unsupported file type: {ext}", {"status": 415})

    if mime_type not in ALLOWED_TYPES:
        raise FatalTaskError(f"Unsupported mime type: {mime_type}", {"status": 415})

    mysql_conn = app_resources.mysql_conn
    bucket_path = app_resources.bucket_path

    object_id = str(uuid.uuid4())

    # insert into objects values (object_id, name, mime_type, size, DEFAULT, DEFAULT, DEFAULT)
    # while have key constraint violation, try again with new object id (uuidv4) (even though this should virtually never occur, we need to be correct)
    # so we need to catch mysql errors and read error code

    

