import argparse
import os
import re
import mysql.connector
from collections import Counter
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from dotenv import dotenv_values
from termcolor import colored

from src.mistral import Mistral, OutOfMemoryError, OutOfTokensError, UnfinishedResponseError

# Load environment variables
mysql_env = dotenv_values(os.path.join(
    os.path.dirname(__file__), "..", "..", "servers", "mysql", ".env"
))
qdrant_env = dotenv_values(os.path.join(
    os.path.dirname(__file__), "..", "..", "servers", "qdrant", ".env"
))

mistral = Mistral(quantization='8bit', device_ids=None)  # Use all available devices.

mistral.report_memory_usage()

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
    parser.add_argument('-k', '--k', type=int, default=100, help='Number of top results to retrieve')
    parser.add_argument('-f', '--flank', type=int, default=2, help='Number of paragraphs for context before and after to form a topic')
    parser.add_argument('-t', '--num-top-bins', type=int, default=10, help='Number of top topics to retrieve')
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
    top_bins = [idx for idx, _ in hist.most_common(args.num_top_bins)]

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

    for i, result in enumerate(results):
        print(f"Post-processing result {i+1}/{len(results)}...")
        topic_name = mistral.completion({
            "messages": [
                {"role":"system", "content":
                 """
Decide on a name for the topic covered in the provided text.

Output only the topic name and nothing else.

"""
                 },
                {"role":"user", "content":"\n\n".join(result["context_paragraphs"])}
            ],

            "max_tokens": 128,
            "temperature":0.6,
            "top_p":0.9,
        }).strip().strip("'\"`")
        result["topic_name"] = topic_name


    mysql_cursor.close()
    mysql_conn.close()

    essay_user_message=f"""
[[Question]]: {args.query}

[[Evidence]]:

{f'\n\n{'-'*16}\n\n'.join([
    f'''
Topic {result_index+1}: "{result["topic_name"]}"

{'\n\n'.join(result["context_paragraphs"])}
'''.strip()
 for result_index, result in enumerate(results)])}

""".strip()
    
    print("")
    print(essay_user_message)
    print("")

    essay = mistral.completion({
        "messages": [
            {"role":"system",
             "content":"""
Please write an academic essay that answer's the user's question given the provided evidence (grouped by topic).
             """.strip()},
             {
                 "role":"user",
                 "content":essay_user_message
             }
        ],
        "max_tokens": None, # Defaults to full size of sliding window (about 4096) - token count of prior conversation / prompt
        "temperature":0.7,
        "top_p":0.9,
    }).strip()

    print("Drafting final essay...")

    print(colored("\n\nFinal Essay:\n\n", "green"))
    print(colored(essay,"green"))




if __name__ == '__main__':
    main()
