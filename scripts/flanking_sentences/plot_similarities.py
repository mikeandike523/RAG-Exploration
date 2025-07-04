#!/usr/bin/env python3
import os
import sys
import click
import numpy as np
import matplotlib.pyplot as plt
from dotenv import dotenv_values
import mysql.connector
from qdrant_client import QdrantClient
from tqdm import tqdm as pb

DEBUG_DIR = "debug"

def get_mysql_connection():
    mysql_env = dotenv_values(os.path.join(
        os.path.dirname(__file__), "..", "..", "servers", "mysql", ".env"
    ))
    return mysql.connector.connect(
        host=mysql_env.get("MYSQL_HOST", "localhost"),
        port=int(mysql_env.get("MYSQL_PORT", 3306)),
        user=mysql_env["MYSQL_USER"],
        password=mysql_env["MYSQL_PASSWORD"],
        database=mysql_env["MYSQL_DATABASE"],
        charset="utf8mb4"
    )

def get_qdrant_client():
    qdrant_env = dotenv_values(os.path.join(
        os.path.dirname(__file__), "..", "..", "servers", "qdrant", ".env"
    ))
    return QdrantClient(
        url=qdrant_env.get("QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333"))
    )

@click.command()
@click.option('-i', '--identifier', 'source_id', required=True, help='Source identifier (slug)')
@click.option('-c', '--count', 'count', type=int, default=None, help='Number of sentences to process')
@click.option('-o', '--offset', 'offset', type=int, default=0, help='Offset into the sentence list')
def analyze_similarities(source_id, count, offset):
    # Ensure output directory exists
    os.makedirs(DEBUG_DIR, exist_ok=True)

    click.echo("Connecting to MySQL and Qdrant...")
    mysql_conn = get_mysql_connection()
    qdrant_client = get_qdrant_client()

    # Fetch source metadata
    cursor = mysql_conn.cursor()
    cursor.execute("SELECT title, author FROM sources WHERE id=%s", (source_id,))
    row = cursor.fetchone()
    cursor.close()
    title_text = row[0] if row and row[0] else source_id
    author_text = row[1] if row and row[1] else "Unknown"

    click.echo(f"Fetching sentences for source: {source_id} ({title_text} by {author_text})")
    cursor = mysql_conn.cursor()
    cursor.execute(
        "SELECT sentence_index, vector_uuid FROM sentences "
        "WHERE source_id=%s ORDER BY sentence_index ASC",
        (source_id,)
    )
    records = cursor.fetchall()
    cursor.close()

    total_sentences = len(records)
    change_markers = sum(1 for _, uuid in records if uuid is None)
    click.echo(f"Found {total_sentences} sentences, including {change_markers} change markers.")

    # Validate offset and determine processing range
    if offset < 0 or offset >= total_sentences:
        click.echo(f"Invalid offset {offset}; must be between 0 and {total_sentences - 1}.")
        sys.exit(1)
    if count is None:
        end = total_sentences
    else:
        end = min(offset + count + 1, total_sentences)
    click.echo(f"Processing sentences from index {offset} to {end - 1} (count {end - offset})")

    # Slice records
    indices = [rec[0] for rec in records]
    uuids = [rec[1] for rec in records]
    sub_indices = indices[offset:end]
    sub_uuids = uuids[offset:end]

    # Compute similarities
    sims = []
    pbar = pb(total=len(sub_indices) - 1, desc="Computing similarities")
    for i in range(1, len(sub_indices)):
        prev_uuid = sub_uuids[i - 1]
        curr_uuid = sub_uuids[i]
        if prev_uuid and curr_uuid:
            prev_point = qdrant_client.retrieve(
                collection_name=source_id,
                ids=[prev_uuid],
                with_vectors=True
            )
            curr_point = qdrant_client.retrieve(
                collection_name=source_id,
                ids=[curr_uuid],
                with_vectors=True
            )
            v0 = np.array(prev_point[0].vector)
            v1 = np.array(curr_point[0].vector)
            sims.append(float(np.dot(v0, v1) / (np.linalg.norm(v0) * np.linalg.norm(v1))))
        else:
            sims.append(np.nan)
        pbar.update(1)
    pbar.close()

    # Prepare plot data
    x = np.array(sub_indices[1:])
    y = np.array(sims)

    # Mask defined and undefined similarities
    defined_mask = ~np.isnan(y)
    undef_mask = np.isnan(y)

    # Plot as histogram-style bar plot for defined values
    plt.figure(figsize=(12, 6), dpi=200)
    cmap = plt.cm.bwr
    norm = plt.Normalize(-1.0, 1.0)
    bar_x = x[defined_mask]
    bar_y = y[defined_mask]
    colors = cmap(norm(bar_y))
    plt.bar(bar_x, bar_y, width=1.0, edgecolor='black', color=colors, align='center')

    # Plot smaller dots at baseline for undefined values
    nan_x = x[undef_mask]
    if nan_x.size > 0:
        plt.scatter(nan_x, np.zeros_like(nan_x), marker='o', color='black', s=8, zorder=3)

    # Set y-limits based on finite data only
    if bar_y.size > 0:
        ymin, ymax = bar_y.min(), bar_y.max()
        plt.ylim(ymin, ymax)

    # Adjust ticks to include min, max, and evenly spaced in between
    # X-axis ticks (10 ticks)
    if bar_x.size > 0:
        xmin, xmax = bar_x.min(), bar_x.max()
    else:
        xmin, xmax = x.min(), x.max()
    xticks = np.linspace(xmin, xmax, num=10)
    xticks = np.round(xticks).astype(int)
    plt.xticks(xticks)

    # Y-axis ticks (10 ticks, formatted to 2 decimal places)
    y_min, y_max = plt.ylim()
    yticks = np.linspace(y_min, y_max, num=10)
    ytick_labels = [f"{tick:.2f}" for tick in yticks]
    plt.yticks(yticks, ytick_labels)

    plt.xlabel("Sentence Index")
    plt.ylabel("Cosine Similarity to Previous Sentence")
    plt.title(f"Similarity Plot: {title_text} by {author_text}")
    plt.tight_layout()

    # Save figure
    out_path = os.path.join(DEBUG_DIR, f"similarities_{source_id}.png")
    plt.savefig(out_path)
    click.echo(f"Saved plot to {out_path}")

if __name__ == "__main__":
    analyze_similarities()
