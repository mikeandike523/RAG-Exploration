from pydantic import BaseModel, StrictStr, ValidationError, validator

class IngestSentencesParams(BaseModel):
    """Parameters for the ingest sentences task."""

    document_id: StrictStr
    question: StrictStr

    @validator("document_id")
    def document_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document_id cannot be empty")
        return v.strip()



def task_ask(args: Dict, app_resources: AppResources) -> str:
    ...