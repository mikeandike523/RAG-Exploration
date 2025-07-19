from typing import Dict, List, Optional
from pydantic import BaseModel, StrictStr, ValidationError, validator
import uuid
import os
from backend.api_types import FatalTaskError, AppResources

class FinalizeDocumentParams(BaseModel):
    title: StrictStr
    author: StrictStr
    description: Optional[StrictStr] = None
    object_id: StrictStr

    @validator('title')
    def title_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()

    @validator('author')
    def author_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Author cannot be empty')
        return v.strip()

    @validator('description')
    def description_optional_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    @validator('object_id')
    def object_id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Object ID cannot be empty')
        return v.strip()


def task_create(args: Dict, app_resources: AppResources) -> Dict[str, str]:
    """
    Creates a document record with metadata and links it to an existing object.

    Args:
        args: dict with 'title', 'author', 'description' (optional), 'object_id'
        app_resources: holds mysql_conn and bucket_path

    Returns:
        dict with 'document_id'
    """
    # 1. Validate input
    try:
        params = FinalizeDocumentParams(**args)
    except ValidationError as exc:
        errors: List[str] = []
        for err in exc.errors():
            loc = err.get('loc', ['field'])[0]
            msg = err.get('msg', '')
            errors.append(f"{loc}: {msg}")
        raise FatalTaskError('Validation error', {'status': 400, 'errors': errors})

    title = params.title
    author = params.author
    description = params.description
    object_id = params.object_id

    # 2. Verify object exists in both database and filesystem
    mysql_conn = app_resources.mysql_conn
    bucket_path = app_resources.bucket_path
    
    cursor = mysql_conn.cursor()
    try:
        # Check if object exists in database
        cursor.execute("SELECT id FROM `objects` WHERE id = %s", (object_id,))
        if not cursor.fetchone():
            raise FatalTaskError(f"Object not found in database: {object_id}", {'status': 404})
        
        # Check if object file exists in filesystem
        file_path = os.path.join(bucket_path, object_id)
        if not os.path.isfile(file_path):
            raise FatalTaskError(f"Object file not found: {object_id}", {'status': 404})

        # 3. Generate document ID and create document record
        document_id = str(uuid.uuid4())
        
        cursor.execute(
            """
            INSERT INTO `documents` (id, title, author, description, object_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (document_id, title, author, description, object_id)
        )
        mysql_conn.commit()

        return document_id

    except Exception as e:
        mysql_conn.rollback()
        if isinstance(e, FatalTaskError):
            raise
        raise FatalTaskError(f"Database error: {e}", {'status': 500})
    finally:
        cursor.close()