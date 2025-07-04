#!/usr/bin/env python3
import click
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
from tqdm import tqdm as pb

# Constants
QDRANT_UPLOAD_BATCH_SIZE = 128

# Load environment variables
mysql_env = dotenv_values(os.path.join(
    os.path.dirname(__file__), "..", "..", "servers", "mysql", ".env"
))
qdrant_env = dotenv_values(os.path.join(
    os.path.dirname(__file__), "..", "..", "servers", "qdrant", ".env"
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
    # Create sentences table with nullable vector_uuid
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sentences (
            source_id VARCHAR(255),
            sentence_index INT,
            sentence_text TEXT,
            vector_uuid VARCHAR(36) NULL,
            PRIMARY KEY (source_id, sentence_index)
        ) CHARACTER SET utf8mb4;
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255),
            author VARCHAR(255) NULL,
            metadata TEXT NULL
        ) CHARACTER SET utf8mb4;
        """
    )
    conn.commit()
    cursor.close()


def clear_source_data(conn, source_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sentences WHERE source_id = %s", (source_id,))
    conn.commit()
    cursor.close()


def drop_tables(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS sentences;")
    cursor.execute("DROP TABLE IF EXISTS sources;")
    conn.commit()
    cursor.close()


def reset_qdrant(qdrant_client):
    for coll in qdrant_client.get_collections().collections:
        qdrant_client.delete_collection(collection_name=coll.name)


def clean_collection_name(name: str) -> str:
    slug = re.sub(r"[^0-9a-z]+", "_", name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if re.match(r"^[0-9]", slug):
        slug = f"c_{slug}"
    return slug


def clean_text_source(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "")
    text = text.strip()
    lines = text.split("\n")
    cleaned = ["" if line.strip() == "" else line for line in lines]
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def process_document(text, title, identifier, author, mysql_conn, qdrant_client):
    click.echo("Cleaning document...")
    text = clean_text_source(text)
    click.echo("Done cleaning document.")

    source_id = identifier or clean_collection_name(title)
    if not identifier:
        click.echo(f"Generated source_id: {source_id}")

    cursor = mysql_conn.cursor()
    cursor.execute(
        "INSERT INTO sources (id, title, author, metadata) VALUES (%s, %s, %s, NULL) "
        "ON DUPLICATE KEY UPDATE title = VALUES(title), author = VALUES(author)",
        (source_id, title, author)
    )
    mysql_conn.commit()
    cursor.close()

    existing = [c.name for c in qdrant_client.get_collections().collections]
    if source_id in existing:
        qdrant_client.delete_collection(collection_name=source_id)
    qdrant_client.create_collection(
        collection_name=source_id,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )

    clear_source_data(mysql_conn, source_id)

    raw_chunks = text.split("\n\n")
    chunks = [c.strip() for c in raw_chunks if c.strip()]

    click.echo("Loading sentence segmenter...")
    seg = pysbd.Segmenter(language="en", char_span=False, clean=True, doc_type="pdf")
    click.echo("Done loading segmenter.")

    all_sentences = []
    with pb(total=len(chunks), desc="Parsing document") as pbar:
        for chunk in chunks:
            all_sentences.extend([s.strip() for s in seg.segment(chunk) if s.strip() and s.strip()!= ""])
            all_sentences.append("")
            pbar.update(1)
    all_sentences.pop()

    total_sentences = len(all_sentences)
    embed_sentences = [s for s in all_sentences if s]
   
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(embed_sentences, show_progress_bar=True)

    pbar = pb(total=total_sentences, desc="Ingesting sentences")
    sentence_idx = 0
    embed_iter = iter(embeddings)
    points = []

    for sent in all_sentences:
        # Generate UUID for vector if sentence is non-empty
        vector_id = str(uuid.uuid4()) if sent else None
        # Insert sentence record with vector_uuid (nullable)
        cursor = mysql_conn.cursor()
        cursor.execute(
            "INSERT INTO sentences (source_id, sentence_index, sentence_text, vector_uuid) VALUES (%s, %s, %s, %s)",
            (source_id, sentence_idx, sent, vector_id)
        )
        mysql_conn.commit()
        cursor.close()

        if sent:
            vec = next(embed_iter)
            # Prepare point with same UUID
            points.append(
                PointStruct(
                    id=vector_id,
                    vector=vec.tolist(),
                    payload={
                        "source_id": source_id,
                        "sentence_index": sentence_idx,
                        "sentence_text": sent,
                        "title": title,
                        "author": author
                    }
                )
            )
        sentence_idx += 1
        pbar.update(1)
    pbar.close()

    # Batch upload to Qdrant
    for i in range(0, len(points), QDRANT_UPLOAD_BATCH_SIZE):
        batch = points[i:i + QDRANT_UPLOAD_BATCH_SIZE]
        qdrant_client.upsert(collection_name=source_id, points=batch)

@click.group()
def cli():
    pass

@cli.command()
@click.option('-f', '--file', 'infile', type=click.File('r', encoding='utf-8'), help='Text file to ingest')
@click.option('-n', '--name', 'title', required=True, help='Title of the source')
@click.option('-i', '--identifier', help='Custom slug identifier for storage')
@click.option('-a', '--author', help='Author of the source')
def ingest(infile, title, identifier, author):
    mysql_conn = get_mysql_connection()
    qdrant_client = QdrantClient(url=qdrant_env.get("QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333")))
    raw = infile.read() if infile else (sys.stdin.read() if not sys.stdin.isatty() else None)
    if raw is None:
        raise click.UsageError("No input: use -f or pipe via stdin.")
    ensure_tables_exist(mysql_conn)
    process_document(raw, title, identifier, author, mysql_conn, qdrant_client)
    mysql_conn.close()
    click.echo("Done ingesting sentences.")

@cli.command()
@click.option('-y', '--yes', is_flag=True, help='Automatic yes to confirmation prompt')
def reset(yes):
    if not yes and not click.confirm("This will erase all data and collections. Continue?", default=False):
        click.echo("Reset aborted.")
        sys.exit(0)
    mysql_conn = get_mysql_connection()
    qdrant_client = QdrantClient(url=qdrant_env.get("QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333")))
    drop_tables(mysql_conn)
    reset_qdrant(qdrant_client)
    mysql_conn.close()
    click.echo("Reset complete.")

if __name__ == '__main__':
    cli()
