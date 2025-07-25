from typing import Dict, List
from time import sleep

from pydantic import BaseModel, StrictStr, ValidationError, validator

from backend.api_types import FatalTaskError, AppResources, TaskContext

TOP_K=20

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

    print_to_debug_log = app_resources.print_to_debug_log

    ctx.emit_update("Thinking about your question...")

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

    # step 1: get metadata

    try:

        cursor = mysql_conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT title, author, description FROM documents WHERE id = %s",
            (document_id,)
        )
        document = cursor.fetchone()
        
        if document is None:
            raise FatalTaskError("Document not found", {"status": 404, "document_id": document_id})
            
        title = document.get("title", "")
        author = document.get("author", "")
        description = document.get("description", None)
        processed_object_id = document.get("processed_object_id", None)
        
    except Exception as e:
        if isinstance(e, FatalTaskError):
            raise
        raise FatalTaskError("Database error", {"status": 500, "error": str(e)})
    finally:
        cursor.close()


    qdrant_client = app_resources.qdrant_client

    # Step 2: Ensure that the collection with name equal to `processed_object_id` exists
    
    if processed_object_id is None:
        raise FatalTaskError("Document has not been processed yet", {"status": 400, "document_id": document_id})
    
    try:
        existing_collections = [c.name for c in qdrant_client.get_collections().collections]
        if processed_object_id not in existing_collections:
            raise FatalTaskError("Document collection not found in vector database", {"status": 404, "document_id": document_id, "processed_object_id": processed_object_id})
    except Exception as e:
        if isinstance(e, FatalTaskError):
            raise
        raise FatalTaskError("Vector database error", {"status": 500, "error": str(e)})
    
    # Step 3: Get the TOP_K vectors, in order, metadata only
    
    ctx.emit_update("Embedding your question...")
    
    # Load embedding model (same as used in ingestion)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Embed the question
    question_vector = model.encode([params.question], show_progress_bar=False)[0].tolist()
    
    ctx.emit_update("Searching for relevant content...")
    
    try:
        # Search Qdrant for the most similar vectors
        search_results = qdrant_client.search(
            collection_name=processed_object_id,
            query_vector=question_vector,
            limit=TOP_K,
            with_payload=True,
            with_vectors=False  # We only need metadata, not the vectors themselves
        )
    except Exception as e:
        raise FatalTaskError("Vector search error", {"status": 500, "error": str(e)})
    
    # Step 5: Tell UI to make new progress bar by emitting progress 0 with a unique name
    ctx.emit_progress(
        0,
        TOP_K,
        "Forming Text Blocks"
    )

    # Step 5 (temporary):

    for search_result in search_results:
        print_to_debug_log(f"Found document with id '{search_result.id}' and score '{search_result.score}'")

        # simulate delay to see progress bar works correctly
        sleep(0.1)

    




    return ""