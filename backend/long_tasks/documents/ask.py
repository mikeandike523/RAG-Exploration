from typing import Dict, List
from time import sleep
import math
import random

from pydantic import BaseModel, StrictStr, ValidationError, validator

from backend.api_types import FatalTaskError, AppResources, TaskContext

TOP_K=50

TARGET_PARAGRAPH_SIZE=20 # On average 15-sentence chunks
MAX_PARAGRAPH_SIZE=30 # Hard maximum of 25

FLOOD_PROB_COMP_SIZE_POWER=1/8
FLOOD_PROB_COMP_SIMILARITY_POWER=1/8
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


def _cosine_similarity(v1, v2) -> float:
    """Compute cosine similarity between two vectors represented as lists."""
    if v1 is None or v2 is None:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def search_result_to_text_block(result, app_resources: AppResources) -> str:
    print_to_debug_log = app_resources.print_to_debug_log

    sentence_metadata = result.payload
    sentence_vector = result.vector

    mysql_conn = app_resources.mysql_conn
    qdrant_client = app_resources.qdrant_client

    object_id = sentence_metadata["object_id"]
    sentence_index = sentence_metadata["sentence_index"]

    start_idx = max(0, sentence_index - MAX_PARAGRAPH_SIZE)
    end_idx = sentence_index + MAX_PARAGRAPH_SIZE

    cursor = mysql_conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT sentence_index, sentence_text, vector_uuid FROM sentences "
            "WHERE object_id=%s AND sentence_index >= %s AND sentence_index <= %s "
            "ORDER BY sentence_index ASC",
            (object_id, start_idx, end_idx),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    idx_to_row = {row["sentence_index"]: row for row in rows}

    up_idx = sentence_index - 1
    down_idx = sentence_index + 1
    included_indices = [sentence_index]
    up_vector = sentence_vector
    down_vector = sentence_vector
    up_stopped = False
    down_stopped = False

    def get_vector(vec_uuid):
        if not vec_uuid:
            return None
        try:
            point = qdrant_client.retrieve(
                collection_name=object_id,
                ids=[vec_uuid],
                with_vectors=True,
            )
            return point[0].vector if point else None
        except Exception as exc:  # pragma: no cover - retrieval failures
            print_to_debug_log(f"Vector retrieval failed: {exc}")
            return None

    while (
        len(included_indices) < MAX_PARAGRAPH_SIZE
        and not (up_stopped and down_stopped)
    ):
        for direction in ("up", "down"):
            if direction == "up":
                if up_stopped:
                    continue
                idx = up_idx
                up_idx -= 1
                ref_vec = up_vector
            else:
                if down_stopped:
                    continue
                idx = down_idx
                down_idx += 1
                ref_vec = down_vector

            row = idx_to_row.get(idx)
            if row is None:
                if direction == "up":
                    up_stopped = True
                else:
                    down_stopped = True
                continue

            candidate_vec = get_vector(row.get("vector_uuid"))
            sim = _cosine_similarity(ref_vec, candidate_vec)

            comp1 = 1.0 - (len(included_indices) / TARGET_PARAGRAPH_SIZE)
            if comp1 < 0:
                comp1 = 0.0
            comp1 = comp1 ** FLOOD_PROB_COMP_SIZE_POWER
            comp2 = ((1.0 + sim) / 2.0) ** FLOOD_PROB_COMP_SIMILARITY_POWER
            prob_continue = comp1 * comp2

            if len(included_indices) >= MAX_PARAGRAPH_SIZE:
                prob_continue = 0.0

            if random.random() <= prob_continue:
                if direction == "up":
                    included_indices.insert(0, idx)
                    up_vector = candidate_vec
                else:
                    included_indices.append(idx)
                    down_vector = candidate_vec
            else:
                if direction == "up":
                    up_stopped = True
                else:
                    down_stopped = True

            if len(included_indices) >= MAX_PARAGRAPH_SIZE:
                break

        # loop ends when both directions stopped

    sentences = [idx_to_row[i]["sentence_text"] for i in included_indices if i in idx_to_row]
    return "\n".join(sentences).strip()


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

    for i,text_block in enumerate(found_text_blocks):
        print_to_debug_log(f"Text Block {i+1}/{len(found_text_blocks)}:\n\n{text_block}\n\n")




    return ""