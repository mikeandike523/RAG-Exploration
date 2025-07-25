from sentence_transformers import CrossEncoder
from rank_bm25 import BM25Okapi
import numpy as np

# === CONSTANTS ===
EPS = 1e-6  # small epsilon to avoid zero in multiplication

# === INITIALIZE REUSABLE RESOURCES ===
# Cross-encoder for fine-grained scoring


CROSS_ENCODER = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cuda:0")


def paragraph_to_query_relevance(query: str, paragraphs: list[str]) -> list[float]:
    """
    Compute combined relevance scores for each paragraph by blending BM25 and cross-encoder signals.

    Args:
        query: The user query string.
        paragraphs: A list of text chunks (paragraphs) to score.
                    Can be of any length (including 1 for a single paragraph).

    Returns:
        List of combined relevance scores, in the same order as `paragraphs`.
    """
    # --- BM25 scoring ---
    # Tokenize each paragraph for BM25
    tokenized_docs = [p.split() for p in paragraphs]
    bm25 = BM25Okapi(tokenized_docs)
    tokenized_query = query.split()
    bm25_scores = np.array(bm25.get_scores(tokenized_query))

    # --- Cross-encoder scoring ---
    # Prepare list of query-para pairs
    pair_list = [[query, p] for p in paragraphs]
    ce_scores = np.array(CROSS_ENCODER.predict(pair_list))

    # --- Normalization helper ---
    def normalize(x: np.ndarray) -> np.ndarray:
        min_val, max_val = x.min(), x.max()
        return (x - min_val) / (max_val - min_val + EPS)

    # Normalize both score vectors to [0,1]
    norm_bm25 = normalize(bm25_scores)
    norm_ce   = normalize(ce_scores)

    # --- Combine via geometric mean ---
    combined = (norm_ce + EPS) * (norm_bm25 + EPS)

    return combined.tolist()
