"""Long running task to ingest a document into sentence level vectors."""

from typing import Dict, List
import os
import uuid

import pysbd
from pydantic import BaseModel, StrictStr, ValidationError, validator
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from backend.api_types import TaskContext, AppResources, FatalTaskError


QDRANT_UPLOAD_BATCH_SIZE = 128


class IngestSentencesParams(BaseModel):
    """Parameters for the ingest sentences task."""

    document_id: StrictStr

    @validator("document_id")
    def document_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document_id cannot be empty")
        return v.strip()


def task_ingest_sentences(
    ctx: TaskContext, args: Dict, app_resources: AppResources
) -> Dict[str, int]:
    """Read a preprocessed document, embed its sentences and store them."""

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
    bucket_path = app_resources.bucket_path
    qdrant_client = app_resources.qdrant_client
    model = app_resources.embedding_model

    cursor = mysql_conn.cursor()
    try:
        cursor.execute(
            "SELECT title, author, processed_object_id FROM documents WHERE id = %s",
            (document_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise FatalTaskError("Document not found", {"status": 404})

        title, author, processed_object_id = row
        if processed_object_id is None:
            raise FatalTaskError("Document has not been preprocessed", {"status": 400})

        file_path = os.path.join(bucket_path, processed_object_id)
        if not os.path.isfile(file_path):
            raise FatalTaskError("Processed document file missing", {"status": 500})

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    finally:
        cursor.close()

    # Segment text into sentences preserving blank lines
    seg = pysbd.Segmenter(language="en", char_span=False, clean=True, doc_type="pdf")
    raw_chunks = text.split("\n\n")
    chunks = [c.strip() for c in raw_chunks if c.strip()]

    sentences: List[str] = []
    for chunk in chunks:
        sentences.extend([s.strip() for s in seg.segment(chunk) if s.strip()])
        sentences.append("")
    if sentences:
        sentences.pop()  # remove final blank line

    num_blank_lines = sum(1 for s in sentences if not s)
    embed_sentences = [s for s in sentences if s]
    num_embedded_sentences = len(embed_sentences)
    total_line_count = len(sentences)

    ctx.emit_update("Embedding sentences")
    embeddings = model.encode(embed_sentences, show_progress_bar=False)

    # Reset any existing data for this object
    cursor = mysql_conn.cursor()
    try:
        cursor.execute("DELETE FROM sentences WHERE object_id = %s", (processed_object_id,))
        mysql_conn.commit()
    finally:
        cursor.close()

    existing = [c.name for c in qdrant_client.get_collections().collections]
    if processed_object_id in existing:
        qdrant_client.delete_collection(collection_name=processed_object_id)
    qdrant_client.create_collection(
        collection_name=processed_object_id,
        vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
    )

    ctx.emit_progress(0, total_line_count)

    embed_iter = iter(embeddings)
    points: List[PointStruct] = []
    cursor = mysql_conn.cursor()
    sentence_idx = 0
    try:
        for sent in sentences:
            vector_id = str(uuid.uuid4()) if sent else None
            cursor.execute(
                "INSERT INTO sentences (object_id, sentence_index, sentence_text, vector_uuid) VALUES (%s, %s, %s, %s)",
                (processed_object_id, sentence_idx, sent, vector_id),
            )

            if sent:
                vec = next(embed_iter)
                points.append(
                    PointStruct(
                        id=vector_id,
                        vector=vec.tolist(),
                        payload={
                            "object_id": processed_object_id,
                            "sentence_index": sentence_idx,
                            "sentence_text": sent,
                            "title": title,
                            "author": author,
                        },
                    )
                )

            sentence_idx += 1
            ctx.emit_progress(sentence_idx, total_line_count)

        mysql_conn.commit()
    finally:
        cursor.close()

    # Batch upload to Qdrant
    for i in range(0, len(points), QDRANT_UPLOAD_BATCH_SIZE):
        batch = points[i : i + QDRANT_UPLOAD_BATCH_SIZE]
        qdrant_client.upsert(collection_name=processed_object_id, points=batch)

    return {
        "num_embedded_sentences": num_embedded_sentences,
        "num_blank_lines": num_blank_lines,
        "total_line_count": total_line_count,
    }