"""search_anchors.py - semantic search over seeded visual anchors.

V1 scope is intentionally narrow: this searches only the Chroma
`visual_anchors` collection populated by confirmed anchor seeding. It does not
search generated-image `taste_memory`.

The query is embedded with Gemini Embedding 2 at 3072 dimensions, then used to
retrieve top-K nearest anchor images. Output is always JSON.

Operational details:
- Empty collections return the pinned empty JSON before any API-key check.
- `--score-threshold` filters the nearest-neighbor candidates after Chroma
  returns up to `--top-k`; it can reduce the final count below top_k.
"""

import argparse
import json
import os
import sys
from pathlib import Path

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMS = 3072
COLLECTION_NAME = "visual_anchors"

DEFAULT_VAULT_ROOT = Path("/workspace/series-vault")
if not DEFAULT_VAULT_ROOT.exists():
    DEFAULT_VAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHROMA_PATH = DEFAULT_VAULT_ROOT / "benchmark" / "chroma_data"


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("must be an integer") from e
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def parse_args():
    parser = argparse.ArgumentParser(description="Search seeded visual anchors by free text.")
    parser.add_argument("query", help="Free-text visual concept to search for.")
    parser.add_argument("--top-k", type=positive_int, default=20, help="Maximum number of candidate anchors.")
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="Optional minimum cosine similarity score to keep.",
    )
    parser.add_argument(
        "--chroma-path",
        type=Path,
        default=DEFAULT_CHROMA_PATH,
        help="Persistent Chroma path. Defaults to benchmark/chroma_data.",
    )
    return parser.parse_args()


def json_exit(payload, code=0):
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return code


def get_collection(chroma_path: Path):
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_query(query: str):
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set in environment.")

    from google import genai
    from google.genai import types

    client = genai.Client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    vec = list(result.embeddings[0].values)
    if len(vec) != EMBEDDING_DIMS:
        raise ValueError(f"Expected {EMBEDDING_DIMS}-dim vector, got {len(vec)}")
    return vec


def similarity_from_distance(distance):
    return 1.0 - float(distance)


def match_from_result(image_id, metadata, distance):
    metadata = metadata or {}
    score = similarity_from_distance(distance)
    return {
        "image_id": metadata.get("image_id") or image_id,
        "score": round(score, 6),
        "source_path": metadata.get("source_path"),
        "anchor_promotion": metadata.get("anchor_type") or metadata.get("anchor_promotion"),
    }


def search(query: str, top_k: int, score_threshold, chroma_path: Path):
    stripped_query = query.strip()
    if not stripped_query:
        return {"ok": False, "stage": "input_validation", "error": "query must be non-empty"}, 2

    try:
        collection = get_collection(chroma_path)
    except Exception as e:
        return {"ok": False, "stage": "chroma_client_init", "error": f"{type(e).__name__}: {e}"}, 1

    try:
        total_count = collection.count()
    except Exception as e:
        return {"ok": False, "stage": "chroma_count", "error": f"{type(e).__name__}: {e}"}, 1

    if total_count == 0:
        return {
            "ok": True,
            "query": stripped_query,
            "collection": COLLECTION_NAME,
            "count": 0,
            "top_k": top_k,
            "matches": [],
            "image_ids": [],
            "note": "no seeded visual anchors found",
        }, 0

    try:
        query_vec = embed_query(stripped_query)
    except Exception as e:
        return {"ok": False, "stage": "embed_query", "error": f"{type(e).__name__}: {e}"}, 1

    n_results = min(top_k, total_count)
    try:
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=n_results,
            include=["metadatas", "distances"],
        )
    except Exception as e:
        return {"ok": False, "stage": "anchor_query", "error": f"{type(e).__name__}: {e}"}, 1

    ids = (result.get("ids") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    matches = []
    for image_id, metadata, distance in zip(ids, metadatas, distances):
        match = match_from_result(image_id, metadata, distance)
        if score_threshold is not None and match["score"] < score_threshold:
            continue
        matches.append(match)

    return {
        "ok": True,
        "query": stripped_query,
        "collection": COLLECTION_NAME,
        "count": len(matches),
        "top_k": top_k,
        "matches": matches,
        "image_ids": [match["image_id"] for match in matches],
    }, 0


def main():
    args = parse_args()
    payload, code = search(args.query, args.top_k, args.score_threshold, args.chroma_path)
    return json_exit(payload, code)


if __name__ == "__main__":
    sys.exit(main())
