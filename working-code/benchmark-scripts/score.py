"""score.py — score a target image vs visual_anchors via cosine similarity.

Per benchmark/SCHEMA.md and plan 04 step 11.

Embeds the target image with Gemini Embedding 2 at 3072 dims (pre-normalized;
not double-normalized — see SCHEMA.md), queries the Chroma `visual_anchors`
collection for the top-k nearest gold and anti anchors, and returns mean
cosine similarities plus a composite taste_alignment.

The truthful-vs-false axis is:
    brain_initial_score_raw = taste_alignment = gold_similarity - anti_similarity

Higher = closer to taste-positive anchors. Lower = closer to taste-negative
anchors. Per SCHEMA.md Standing Rule #3, this is a similarity coordinate, not
a verdict on the image.

Retrieval behavior:
- world_state=None       -> top-k gold across all states; anti pool unfiltered.
- world_state=<vocab>    -> top-k gold filtered to {world_state, "dna-core"};
                            if state-matched pool < sparse_threshold, fall back
                            to unfiltered gold and report fallback in result.
                            Anti pool is always unfiltered.

Boot Clean / missing-anchor behavior (plan 04 contract):
- Empty visual_anchors collection -> ok=False, stage=anchor_pool, structured info.
- Gold or anti pool absent        -> ok=False, stage=anchor_pool, structured info.
- Never crashes on missing data.

Distance metric:
    visual_anchors is created with hnsw:space="cosine" by init_collections.py.
    Chroma returns cosine distance = 1 - cosine_similarity.
    Therefore cosine_similarity = 1 - distance.
    This is metric-agnostic with respect to whether the input vectors are
    pre-normalized — Chroma normalizes internally for cosine space.

Usage:
    python score.py <image_path>
    python score.py <image_path> --world-state sacred
    python score.py <image_path> --world-state flourishing --top-k 5
"""

import argparse
import json
import os
import sys
from pathlib import Path

# chromadb and google.genai are imported lazily so Boot Clean (empty collection
# on a host without deps installed) returns a structured error rather than
# crashing at top-level import. Same pattern as embed_anchors.py.

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMS = 3072

CHROMA_PATH = "/workspace/series-vault/benchmark/chroma_data"
COLLECTION_NAME = "visual_anchors"
DEFAULT_TOP_K = 5
DEFAULT_SPARSE_THRESHOLD = 3

WORLD_STATES = {
    "flourishing", "sacred", "broken", "corrupted",
    "abandoned", "harsh", "neutral", "dna-core",
}

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def embed_image(image_path: Path) -> list:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set in container env.")

    from google import genai
    from google.genai import types

    client = genai.Client()
    image_bytes = image_path.read_bytes()
    mime = MIME_BY_SUFFIX.get(image_path.suffix.lower(), "image/jpeg")

    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime)],
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    vec = list(result.embeddings[0].values)
    if len(vec) != EMBEDDING_DIMS:
        raise ValueError(f"Expected {EMBEDDING_DIMS}-dim vector, got {len(vec)}")
    return vec


def get_chroma_collection():
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name=COLLECTION_NAME)


def cos_sim_from_cosine_distance(distance: float) -> float:
    """Chroma cosine-space distance = 1 - cosine_similarity, so invert."""
    return 1.0 - distance


def mean_or_none(values):
    return sum(values) / len(values) if values else None


def rank_from_score(score):
    if score is None:
        return None
    if score >= 0.82:
        return "strong"
    if score >= 0.72:
        return "promising"
    if score >= 0.62:
        return "borderline"
    return "likely-miss"


def missing_anchor_payload(stage: str, error: str, world_state, anchor_count: dict) -> dict:
    return {
        "ok": False,
        "stage": stage,
        "error": error,
        "world_state": world_state,
        "taste_alignment": None,
        "gold_similarity": None,
        "anti_similarity": None,
        "brain_initial_score_raw": None,
        "brain_initial_gold_similarity": None,
        "brain_initial_anti_similarity": None,
        "brain_initial_rank": None,
        "anchor_count": anchor_count,
    }


def query_pool(collection, query_vec, where_filter, top_k):
    result = collection.query(
        query_embeddings=[query_vec],
        n_results=top_k,
        where=where_filter,
    )
    distances = (result.get("distances") or [[]])[0]
    return [cos_sim_from_cosine_distance(d) for d in distances]


def score_image(
    image_path: Path,
    world_state=None,
    top_k: int = DEFAULT_TOP_K,
    sparse_threshold: int = DEFAULT_SPARSE_THRESHOLD,
) -> dict:
    if world_state is not None and world_state not in WORLD_STATES:
        return {
            "ok": False,
            "stage": "input_validation",
            "error": f"world_state {world_state!r} not in vocab; must be one of {sorted(WORLD_STATES)}",
        }

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        return {
            "ok": False,
            "stage": "input_validation",
            "error": f"top_k must be a positive integer; got {top_k!r}",
        }

    if not isinstance(sparse_threshold, int) or isinstance(sparse_threshold, bool) or sparse_threshold < 1:
        return {
            "ok": False,
            "stage": "input_validation",
            "error": f"sparse_threshold must be a positive integer; got {sparse_threshold!r}",
        }

    try:
        collection = get_chroma_collection()
    except Exception as e:
        return {"ok": False, "stage": "chroma_client_init", "error": f"{type(e).__name__}: {e}"}

    try:
        total_count = collection.count()
    except Exception as e:
        return {"ok": False, "stage": "chroma_count", "error": f"{type(e).__name__}: {e}"}

    if total_count == 0:
        return missing_anchor_payload(
            "anchor_pool",
            "visual_anchors collection is empty — no anchors to score against",
            world_state,
            {"gold": 0, "anti": 0, "total_in_collection": 0},
        )

    try:
        vec = embed_image(image_path)
    except Exception as e:
        return {"ok": False, "stage": "embed_image", "error": f"{type(e).__name__}: {e}"}

    try:
        anti_sims = query_pool(collection, vec, {"anchor_type": "anti"}, top_k)
    except Exception as e:
        return {"ok": False, "stage": "anti_query", "error": f"{type(e).__name__}: {e}"}

    gold_pool_mode = "all"
    if world_state is not None:
        state_filter = {
            "$and": [
                {"anchor_type": "gold"},
                {"$or": [{"world_state": world_state}, {"world_state": "dna-core"}]},
            ]
        }
        try:
            gold_sims = query_pool(collection, vec, state_filter, top_k)
        except Exception as e:
            return {"ok": False, "stage": "gold_query_state_matched", "error": f"{type(e).__name__}: {e}"}
        gold_pool_mode = "state-matched"
        if len(gold_sims) < sparse_threshold:
            try:
                gold_sims = query_pool(collection, vec, {"anchor_type": "gold"}, top_k)
            except Exception as e:
                return {"ok": False, "stage": "gold_query_fallback", "error": f"{type(e).__name__}: {e}"}
            gold_pool_mode = "fallback-all"
    else:
        try:
            gold_sims = query_pool(collection, vec, {"anchor_type": "gold"}, top_k)
        except Exception as e:
            return {"ok": False, "stage": "gold_query", "error": f"{type(e).__name__}: {e}"}

    if not gold_sims:
        return missing_anchor_payload(
            "anchor_pool",
            "no gold anchors present in visual_anchors",
            world_state,
            {"gold": 0, "anti": len(anti_sims), "total_in_collection": total_count},
        )
    if not anti_sims:
        return missing_anchor_payload(
            "anchor_pool",
            "no anti anchors present in visual_anchors",
            world_state,
            {"gold": len(gold_sims), "anti": 0, "total_in_collection": total_count},
        )

    gold_similarity = mean_or_none(gold_sims)
    anti_similarity = mean_or_none(anti_sims)
    taste_alignment = gold_similarity - anti_similarity
    brain_initial_rank = rank_from_score(taste_alignment)

    return {
        "ok": True,
        "world_state": world_state,
        "taste_alignment": taste_alignment,
        "gold_similarity": gold_similarity,
        "anti_similarity": anti_similarity,
        "brain_initial_score_raw": taste_alignment,
        "brain_initial_gold_similarity": gold_similarity,
        "brain_initial_anti_similarity": anti_similarity,
        "brain_initial_rank": brain_initial_rank,
        "anchor_count": {
            "gold": len(gold_sims),
            "anti": len(anti_sims),
            "gold_pool": gold_pool_mode,
            "total_in_collection": total_count,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Score an image's taste alignment vs visual_anchors.")
    parser.add_argument("image_path", help="Container path to the image to score")
    parser.add_argument(
        "--world-state",
        default=None,
        choices=sorted(WORLD_STATES),
        help="Optional world_state to focus gold retrieval; combined with dna-core",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Top-k anchors per pool")
    parser.add_argument(
        "--sparse-threshold",
        type=int,
        default=DEFAULT_SPARSE_THRESHOLD,
        help="If state-matched gold pool returns fewer than this, fall back to unfiltered gold",
    )
    args = parser.parse_args()

    image_path = Path(args.image_path)
    if not image_path.exists() or not image_path.is_file():
        print(json.dumps({
            "ok": False,
            "stage": "image_input",
            "error": f"image not found or not a file: {image_path}",
        }, indent=2))
        sys.exit(1)

    result = score_image(
        image_path,
        world_state=args.world_state,
        top_k=args.top_k,
        sparse_threshold=args.sparse_threshold,
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
