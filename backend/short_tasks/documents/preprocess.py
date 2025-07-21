from typing import Dict, List
import os
import re
import uuid
from pydantic import BaseModel, StrictStr, ValidationError, validator

from backend.api_types import FatalTaskError, AppResources

# Unicode separators and exotic whitespace from scripts/clean_text_file.py
PARAGRAPH_SEPARATOR = "\u2029"
SECTION_SEPARATOR = "\u2028"
EXOTIC_WHITESPACE = {
    "\u000C": "FORM FEED",
    "\u000B": "LINE TABULATION",
    "\u00A0": "NO-BREAK SPACE",
}


class PreprocessParams(BaseModel):
    document_id: StrictStr

    @validator("document_id")
    def document_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document_id cannot be empty")
        return v.strip()


def _clean_text(text: str) -> str:
    """Preprocess raw text according to the backend pipeline."""
    # Step 1: Replace CRLF with LF
    cleaned = text.replace("\r\n", "\n")

    # Step 2: Remove stray carriage returns
    cleaned = cleaned.replace("\r", "")

    # Step 3: Convert/remove exotic whitespace characters
    cleaned = cleaned.replace(PARAGRAPH_SEPARATOR, "\n").replace(
        SECTION_SEPARATOR, "\n\n"
    )
    cleaned = cleaned.replace("\n" + "\u000C", "")
    for ws in EXOTIC_WHITESPACE:
        cleaned = cleaned.replace(ws, "")

    # Step 4: Remove all non-printing, non-whitespace characters
    cleaned = "".join(c for c in cleaned if c.isprintable() or c.isspace())

    # Step 5: Trim whitespace off start and end of entire document
    cleaned = cleaned.strip()

    # Step 6: Trim whitespace for each line
    lines = cleaned.split("\n")
    trimmed_lines = [line.strip() for line in lines]
    cleaned = "\n".join(trimmed_lines)

    # Step 7: Condense runs of >2 newlines to exactly two
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned


def task_preprocess(args: Dict, app_resources: AppResources) -> str:
    """Preprocess a document's text and store result in a new object."""
    try:
        params = PreprocessParams(**args)
    except ValidationError as exc:
        errors: List[str] = []
        for err in exc.errors():
            loc = err.get("loc", ["field"])[0]
            msg = err.get("msg", "")
            errors.append(f"{loc}: {msg}")
        raise FatalTaskError("Validation error", {"status": 400, "errors": errors})

    document_id = params.document_id
    mysql_conn = app_resources.mysql_conn
    bucket_path = app_resources.bucket_path

    cursor = mysql_conn.cursor()
    try:
        cursor.execute(
            "SELECT object_id, processed_object_id FROM documents WHERE id = %s",
            (document_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise FatalTaskError("Document not found", {"status": 404})
        object_id, processed_object_id = row
        if processed_object_id is not None:
            raise FatalTaskError("Document already processed", {"status": 400})
        if object_id is None:
            raise FatalTaskError(
                "Document is not linked to an object", {"status": 400}
            )

        cursor.execute(
            "SELECT name, mime_type FROM objects WHERE id = %s", (object_id,)
        )
        obj_row = cursor.fetchone()
        if not obj_row:
            raise FatalTaskError("Object metadata missing", {"status": 500})
        orig_name, mime_type = obj_row

        orig_path = os.path.join(bucket_path, object_id)
        if not os.path.isfile(orig_path):
            raise FatalTaskError("Object file not found", {"status": 404})
        with open(orig_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            raw = f.read()
        cleaned_text = _clean_text(raw)
        cleaned_bytes = cleaned_text.encode("utf-8")
        new_object_id = str(uuid.uuid4())
        new_name = f"__preprocessed__{orig_name}"
        cursor.execute(
            "INSERT INTO objects (id, name, mime_type, size) VALUES (%s, %s, %s, %s)",
            (new_object_id, new_name, mime_type, len(cleaned_bytes)),
        )
        cursor.execute(
            "UPDATE documents SET processed_object_id = %s WHERE id = %s",
            (new_object_id, document_id),
        )
        mysql_conn.commit()
        new_path = os.path.join(bucket_path, new_object_id)
        with open(new_path, "wb") as out:
            out.write(cleaned_bytes)
        return new_object_id
    except FatalTaskError:
        mysql_conn.rollback()
        raise
    except Exception as e:
        mysql_conn.rollback()
        raise FatalTaskError(f"Database error: {e}", {"status": 500})
    finally:
        cursor.close()
