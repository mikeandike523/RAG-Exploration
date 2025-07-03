#!/usr/bin/env python3
import argparse
import os
import sys
import re
import uuid
import pysbd
from sentence_transformers import SentenceTransformer
import mysql.connector
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from dotenv import dotenv_values

# Load environment variables
mysql_env = dotenv_values(os.path.join(
    os.path.dirname(__file__) , ".." , "..", "servers", "mysql", ".env"
))
qdrant_env = dotenv_values(os.path.join(
    os.path.dirname(__file__), ".." , "..", "servers", "qdrant", ".env"
))


def get_mysql_connection():
    return mysql.connector.connect(
        host=mysql_env.get("MYSQL_HOST", "localhost"),
        port=int(mysql_env.get("MYSQL_PORT", 3306)),
        user=mysql_env["MYSQL_USER"],
        password=mysql_env["MYSQL_PASSWORD"],
        database=mysql_env["MYSQL_DATABASE"],
        charset="utf8mb4"
    )


def ensure_tables_exist(conn):
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS paragraphs (
        source_name VARCHAR(255),
        paragraph_index INT,
        paragraph_text TEXT,
        PRIMARY KEY (source_name, paragraph_index)
    ) CHARACTER SET utf8mb4;
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sentences (
        source_name VARCHAR(255),
        paragraph_index INT,
        sentence_index INT,
        sentence_text TEXT,
        PRIMARY KEY (source_name, paragraph_index, sentence_index)
    ) CHARACTER SET utf8mb4;
    """)
    conn.commit()
    cursor.close()


def clear_source_data(conn, source_name):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM paragraphs WHERE source_name = %s", (source_name,))
    cursor.execute("DELETE FROM sentences WHERE source_name = %s", (source_name,))
    conn.commit()
    cursor.close()


def drop_tables(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS sentences;")
    cursor.execute("DROP TABLE IF EXISTS paragraphs;")
    conn.commit()
    cursor.close()


def reset_qdrant(qdrant_client):
    """
    Drop all Qdrant collections.
    """
    collections = [c.name for c in qdrant_client.get_collections().collections]
    for coll in collections:
        qdrant_client.delete_collection(collection_name=coll)


def clean_collection_name(name: str) -> str:
    """
    Clean and slugify the source name into a Qdrant-compatible collection name.
    """
    # Lowercase, replace non-alphanumeric with underscore, collapse multiple underscores
    slug = re.sub(r"[^0-9a-z]+", "_", name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    # Ensure name does not start with a digit
    if re.match(r"^[0-9]", slug):
        slug = f"c_{slug}"
    return slug


def process_document(text, raw_name, mysql_conn, qdrant_client):
    # Normalize and clean name for Qdrant
    source = clean_collection_name(raw_name)

    # Normalize whitespace
    text = text.strip().replace("\r\n", "\n")
    text = "\n".join(line.strip() for line in text.split("\n"))

    # Split into paragraphs
    raw_paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    # Initialize segmenter and model
    seg = pysbd.Segmenter(language="en", char_span=False, clean=True, doc_type="pdf")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Recreate Qdrant collection to ensure no duplicate vectors
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if source in existing:
        qdrant_client.delete_collection(collection_name=source)
    qdrant_client.create_collection(
        collection_name=source,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )

    # Clear existing data in MySQL
    clear_source_data(mysql_conn, raw_name)

    # Insert paragraphs
    cursor = mysql_conn.cursor()
    for p_idx, para in enumerate(paragraphs):
        cursor.execute(
            "INSERT INTO paragraphs (source_name, paragraph_index, paragraph_text) VALUES (%s, %s, %s)",
            (raw_name, p_idx, para)
        )
    mysql_conn.commit()
    cursor.close()

    # Process each paragraph
    for p_idx, para in enumerate(paragraphs):
        print(f"Processing paragraph {p_idx+1} of {len(paragraphs)}...")
        sentences = seg.segment(para)
        embeddings = model.encode(sentences, show_progress_bar=False)

        # Insert sentences and upsert into Qdrant
        cursor = mysql_conn.cursor()
        points = []
        for s_idx, sentence in enumerate(sentences):
            cursor.execute(
                "INSERT INTO sentences (source_name, paragraph_index, sentence_index, sentence_text) VALUES (%s, %s, %s, %s)",
                (raw_name, p_idx, s_idx, sentence)
            )
            # Generate a random uuid4 for the vector ID
            vec_id = str(uuid.uuid4())
            point = PointStruct(
                id=vec_id,
                vector=embeddings[s_idx].tolist(),
                payload={
                    "source_name": raw_name,
                    "paragraph_index": p_idx,
                    "sentence_index": s_idx,
                    "sentence_text": sentence
                }
            )
            points.append(point)
        mysql_conn.commit()
        cursor.close()

        # Upsert vectors in batch
        qdrant_client.upsert(collection_name=source, points=points)


def main():
    parser = argparse.ArgumentParser(description="Ingest and embed document text or reset storage.")
    parser.add_argument('-f', '--file', help='Text file to ingest')
    parser.add_argument('-n', '--name', help='Document name or identifier')
    parser.add_argument('--reset', action='store_true', help='Drop tables and all Qdrant collections')
    args = parser.parse_args()

    # Connect to storage
    mysql_conn = get_mysql_connection()
    qdrant_client = QdrantClient(
        url=qdrant_env.get("QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333"))
    )

    if args.reset:
        print("Resetting MySQL tables and Qdrant collections...")
        drop_tables(mysql_conn)
        reset_qdrant(qdrant_client)
        mysql_conn.close()
        print("Reset complete.")
        sys.exit(0)

    # Ingestion path
    if not args.file or not args.name:
        parser.error("the following arguments are required: -f/--file, -n/--name (unless --reset is used)")

    # Prepare schema
    ensure_tables_exist(mysql_conn)

    # Read input text
    with open(args.file, 'r', encoding='utf-8') as f:
        text = f.read()

    process_document(text, args.name, mysql_conn, qdrant_client)
    mysql_conn.close()
    print("Done.")

if __name__ == '__main__':
    main()
