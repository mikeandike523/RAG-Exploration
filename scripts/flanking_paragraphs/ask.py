import argparse
import os
import re
import json
import mysql.connector
from collections import Counter
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from dotenv import dotenv_values

from src.mistral import Mistral, OutOfMemoryError, OutOfTokensError, UnfinishedResponseError

# Load environment variables
mysql_env = dotenv_values(os.path.join(
    os.path.dirname(__file__), "..", "..", "servers", "mysql", ".env"
))
qdrant_env = dotenv_values(os.path.join(
    os.path.dirname(__file__), "..", "..", "servers", "qdrant", ".env"
))

mistral = Mistral(quantization='8bit', device_ids=None)  # Use all available devices.

# We will use tool calling to better hint to the AI that search result data is not direct user quote
# In more rudimentary models, we use prompt engineer, and simply supply data as the user role with a sort or
# flag/indicator (for instance, [[data]] or [Data] or Data:) ...
# However modern models support tool calling
# Our plan is to inject search results into the conversation as a simulated tool call,
# i.e. we draft a "message list" where we force the AI to select the tool we want
# and then return the vector database search results as a tool call response

# We will use the following official guide by Mistral AI
# https://docs.mistral.ai/capabilities/function_calling/

TOOLS = [
    {
        "type": "function",
        "function":{
            "name": "semantic_search",
            "description": "Searches a large corpus "
            # ... todo
        }
    }
]

# However, for some purposes, such as deciding if a paragraph is still relevant
# we can use the simpler approach to lower the token count and ease the cognitive load.


def mistral_is_text_blob_irrelevant(text, question):
    system_prompt="""
    
Decide if the given text is fully irrelevant to the question.

Some examples of irrelevant text are:
  
    - Table of contents, formatting, and other information not related to the question.
    - Prematurely cutoff sentences or non-sequiturs.
    - References to unknown external resources (images, data, urls, etc.).

""".strip()

    user_prompt=f"""

""".strip()

    conversation = [
{
    "role":"system",
    "content": system_prompt
}        
    ]


def get_mysql_connection():
    return mysql.connector.connect(
        host=mysql_env.get("MYSQL_HOST", "localhost"),
        port=int(mysql_env.get("MYSQL_PORT", 3306)),
        user=mysql_env["MYSQL_USER"],
        password=mysql_env["MYSQL_PASSWORD"],
        database=mysql_env["MYSQL_DATABASE"],
        charset="utf8mb4"
    )


def clean_collection_name(name: str) -> str:
    slug = re.sub(r"[^0-9a-z]+", "_", name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if re.match(r"^[0-9]", slug):
        slug = f"c_{slug}"
    return slug


def parse_args():
    parser = argparse.ArgumentParser(description="Query a text source with semantic search and retrieve context.")
    parser.add_argument('-n', '--name', required=True, help='Name of text source (collection)')
    parser.add_argument('-q', '--query', required=True, help='Query text to search for')
    parser.add_argument('-k', '--k', type=int, default=30, help='Number of top results to retrieve')
    parser.add_argument('-f', '--flank', type=int, default=1, help='Number of paragraphs for context before and after')
    return parser.parse_args()


def get_qdrant_client():
    return QdrantClient(
        url=qdrant_env.get("QDRANT_URL", os.environ.get("QDRANT_URL", "http://localhost:6333"))
    )

def main():
    args = parse_args()
    collection = clean_collection_name(args.name)

    # Connect to Qdrant and MySQL
    qdrant = get_qdrant_client()
    mysql_conn = get_mysql_connection()
    mysql_cursor = mysql_conn.cursor(dictionary=True)

    # Load embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Embed query
    print(f"Embedding query: '{args.query}'...")
    query_vec = model.encode([args.query], show_progress_bar=False)[0].tolist()

    # Search Qdrant
    print(f"Searching top {args.k} results in '{collection}'...")
    search_results = qdrant.search(
        collection_name=collection,
        query_vector=query_vec,
        limit=args.k
    )  # returns List[ScoredPoint]

    # Histogram of paragraph indices
    paragraph_indices = [hit.payload.get('paragraph_index') for hit in search_results]
    hist = Counter(paragraph_indices)

    # Select top 5 most frequent paragraphs
    top_bins = [idx for idx, _ in hist.most_common(5)]

    # Assemble contexts for top bins
    results = []
    for p_idx in top_bins:
        count = hist[p_idx]
        start = max(0, p_idx - args.flank)
        end = p_idx + args.flank

        mysql_cursor.execute(
            "SELECT paragraph_index, paragraph_text FROM paragraphs "
            "WHERE source_name = %s AND paragraph_index BETWEEN %s AND %s "
            "ORDER BY paragraph_index",
            (args.name, start, end)
        )
        paras = mysql_cursor.fetchall()
        context_paras = [row['paragraph_text'] for row in paras]

        results.append({
            'paragraph_index': p_idx,
            'count': count,
            'context_paragraphs': context_paras
        })

    # Output JSON
    print(json.dumps(results, indent=2, ensure_ascii=False))

    mysql_cursor.close()
    mysql_conn.close()


if __name__ == '__main__':
    main()
