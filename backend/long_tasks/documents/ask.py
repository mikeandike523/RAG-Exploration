from typing import Dict, List

from pydantic import BaseModel, StrictStr, ValidationError, validator

from backend.api_types import FatalTaskError, AppResources, TaskContext

class IngestSentencesParams(BaseModel):
    """Parameters for the ingest sentences task."""

    document_id: StrictStr
    question: StrictStr

    @validator("document_id")
    def document_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document_id cannot be empty")
        return v.strip()



def task_ask(ctx:TaskContext,args: Dict, app_resources: AppResources) -> str:

    ctx.emit_update("Thinking about your question...")

    # while True:
    #     pass

    try:
        params = IngestSentencesParams(**args)
    except ValidationError as exc:  # pragma: no cover - simple validation
        errors: List[str] = []
        for err in exc.errors():
            loc = err.get("loc", ["field"])[0]
            msg = err.get("msg", "")
            errors.append(f"{loc}: {msg}")
        raise FatalTaskError("Validation error", {"status": 400, "errors": errors})
    
    document_id = params.document_id

    mysql_conn = app_resources.mysql_conn


    return ""