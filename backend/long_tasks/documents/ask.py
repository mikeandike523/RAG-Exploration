from typing import Dict, List
from time import sleep

from pydantic import BaseModel, StrictStr, ValidationError, validator

from backend.api_types import FatalTaskError, AppResources, TaskContext

TOP_K=20

TARGET_PARAGRAPH_SIZE=15 # On average 15-sentence chunks
MAX_PARAGRAPH_SIZE=25 # Hard maximum of 25

# Flood procedure:

# Suppose we have sentence at index i in a document, called S_i

# To expand the paragraphs, we flood "up" (less than i) and "down" (greater than i)
# to "collect" sentences to reach our target paragraph size.

# First, we will not expand evenly, we alternate between flood-up and flood-down until we reach a stop condition at either

# Rule #1

# If we hit the hard max, then we stop (prob_continue = 0.0)

# The probability of continuing is the multiplication of several components:

# 1. proximity to target paragraph size
# prob_continue_comp_1 = 1-(num_sentences/TARGET_PARAGRAPH_SIZE)**(some_power) (lets start with 1 or 2)


# 2. Be aware, in the database, there are two types of sentences:
    # - a blank sentece, that does not have a corresponding vector
    # - a non-blank sentence, which has a corresponding vector
    # So, if we encounter a blank sentence, we record the cosine similarity as 0, as in neither similar nor dissimilar
    # (cosine similarity is between current "flood wavefront" and the potential next sentence to flood to)
# prob_continue_comp_2 = ((1+cosine_similarity)/2) ** (power) (lets start with 1 or 2)

# Some notes:

# 1. We can optimize our algorithm by using mysql pagination to pre-fetch MAX_PARAGRAPH_SIZE sentences both
# above and below the seed sentence (i.e. worst case scenario) (leading to MAX_PARAGRAPH_SIZE * 2) sentences to start off)

# If a given "wavefront" (up or down) reaches a stop condition, we keep propogating  the other until it also stops,
# i.e. propogation stops once both wavefronts stop.

# if the initial +- MAX_PARAGRAPH_SIZE search chunk is near the start or end of the document, we may not
# even be able to retrieve that many, so if our "propogation" hits the edge of our initial_search_chunk, we just stop propogation
# most of the time this will not occur as most relevant sentences are near the middle of the document,
# but it can happen and is an important edge case

# Question, does mysql pagination support a negative offset?, and does it handle borders gracefully for partial result sets?


class IngestSentencesParams(BaseModel):
    """Parameters for the ingest sentences task."""

    document_id: StrictStr
    question: StrictStr

    @validator("document_id")
    def document_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document_id cannot be empty")
        return v.strip()

def search_result_to_text_block(result, app_resources: AppResources) -> str:
    print_to_debug_log = app_resources.print_to_debug_log

    sentence_metadata = result.payload
    sentence_vector = result.vector


    object_id = sentence_metadata["object_id"]
    sentence_index = sentence_metadata["sentence_index"]


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
            "SELECT title, author, description, processed_object_id FROM documents WHERE id = %s",
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
            with_vectors=True
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

    found_text_blocks = []

    for i,search_result in enumerate(search_results):
        print_to_debug_log(f"Found document with id '{search_result.id}' and score '{search_result.score}'")

        found_text_blocks.append(
            search_result_to_text_block(search_result, app_resources)
        )

        ctx.emit_progress(
            i+1,
            TOP_K,
            "Forming Text Blocks"
        )

    




    return ""