"""Initialize Chroma collections for taste memory and visual anchors.

Idempotent: get_or_create_collection() means re-running is safe — but the HNSW
distance space is fixed at collection creation time, so this script must be
run against an empty chroma_data/ to actually pin the metric. If a collection
already exists with a different metric, that pre-existing metric wins.

Both collections use explicit cosine distance:
    distance = 1 - cosine_similarity, so cosine_similarity = 1 - distance
This makes score.py's similarity math metric-agnostic with respect to whether
Gemini Embedding 2 vectors are pre-normalized — Chroma normalizes internally
for cosine space.

Persistent path is inside the vault so collections survive container restarts.
"""

import chromadb

CHROMA_PATH = "/workspace/series-vault/benchmark/chroma_data"
HNSW_SPACE = "cosine"


def main() -> None:
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    taste_memory = client.get_or_create_collection(
        name="taste_memory",
        metadata={"hnsw:space": HNSW_SPACE},
    )
    visual_anchors = client.get_or_create_collection(
        name="visual_anchors",
        metadata={"hnsw:space": HNSW_SPACE},
    )

    print(f"taste_memory count: {taste_memory.count()} (space: {HNSW_SPACE})")
    print(f"visual_anchors count: {visual_anchors.count()} (space: {HNSW_SPACE})")
    print("Ready.")


if __name__ == "__main__":
    main()
