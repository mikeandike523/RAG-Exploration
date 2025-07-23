from typing import Dict, List
from pydantic import BaseModel, StrictStr, ValidationError, validator
from backend.api_types import FatalTaskError, AppResources


class GetMetadataParams(BaseModel):
    document_id: StrictStr

    @validator('document_id')
    def document_id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('document_id cannot be empty')
        return v.strip()


def task_get_metadata(args: Dict, app_resources: AppResources) -> Dict[str, str]:
    """
    Retrieves document metadata (title, author, description) by document ID.

    Args:
        args: dict with 'document_id'
        app_resources: holds mysql_conn and bucket_path

    Returns:
        dict with 'title', 'author', 'description'

    Raises:
        FatalTaskError on validation failure or if document not found.
    """

    app_resources.print_to_debug_log(args)

    # 1. Validate input
    try:
        params = GetMetadataParams(**args)
    except ValidationError as exc:
        errors: List[str] = []
        for err in exc.errors():
            loc = err.get('loc', ['field'])[0]
            msg = err.get('msg', '')
            errors.append(f"{loc}: {msg}")
        raise FatalTaskError('Validation error', {'status': 400, 'errors': errors})

    document_id = params.document_id

    # 2. Query database for document metadata
    mysql_conn = app_resources.mysql_conn
    cursor = mysql_conn.cursor()
    
    try:
        cursor.execute(
            "SELECT title, author, description FROM documents WHERE id = %s",
            (document_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise FatalTaskError("Document not found", {"status": 404})
        
        title, author, description = row
        
        return {
            "title": title,
            "author": author,
            "description": description
        }
        
    except FatalTaskError:
        raise
    except Exception as e:
        raise FatalTaskError(f"Database error: {e}", {"status": 500})
    finally:
        cursor.close()