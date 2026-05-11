"""Search V1.1 taste_memory records and emit lightbox-compatible JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from taste_memory_common import (
    COLLECTION_NAME,
    RANKING_VERSION,
    SEARCH_INDEX_VERSION,
    default_chroma_path,
    default_vault_root,
    embed_image,
    embed_text,
    get_chroma_collection,
    json_exit,
    similarity_from_distance,
)


ANCHOR_PROMOTIONS = {"gold", "anti", "aspirational", "none"}
QUALITY_TIERS = {"bad", "okay", "great", "aspirational", "approved", "canon"}
FAILURE_MODES = {"execution", "concept", "partial", "none"}


def positive_int_arg(value):
    try:
        parsed = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("must be an integer") from e
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def parse_bool(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def parse_args():
    vault_root = default_vault_root()
    parser = argparse.ArgumentParser(description="Search reviewed/generated images in taste_memory.")
    parser.add_argument("query", nargs="?", default="", help="Free-text query for text/hybrid modes.")
    parser.add_argument("--query-image", type=Path, help="Reference image for image or hybrid mode.")
    parser.add_argument("--mode", choices=["text", "image", "hybrid", "all"], default="text")
    parser.add_argument("--top-k", type=positive_int_arg, default=20)
    parser.add_argument("--anchor-promotion", choices=sorted(ANCHOR_PROMOTIONS))
    parser.add_argument("--quality-tier", choices=sorted(QUALITY_TIERS))
    parser.add_argument("--min-aaron-score", type=float)
    parser.add_argument("--max-aaron-score", type=float)
    parser.add_argument("--model")
    parser.add_argument("--created-by")
    parser.add_argument("--job-id")
    parser.add_argument("--world-state")
    parser.add_argument("--tone")
    parser.add_argument("--failure-mode", choices=sorted(FAILURE_MODES))
    parser.add_argument("--canon-candidate", type=parse_bool)
    parser.add_argument("--include-holdouts", action="store_true")
    parser.add_argument("--score-threshold", type=float)
    parser.add_argument("--vault-root", type=Path, default=vault_root)
    parser.add_argument("--chroma-path", type=Path, default=default_chroma_path(vault_root))
    return parser.parse_args()


def base_where(modality: str, args) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = [
        {"search_index_version": {"$eq": SEARCH_INDEX_VERSION}},
        {"modality": {"$eq": modality}},
    ]
    if not args.include_holdouts:
        clauses.append({"image_origin": {"$ne": "holdout_benchmark"}})
    exact_filters = {
        "anchor_promotion": args.anchor_promotion,
        "quality_tier": args.quality_tier,
        "model": args.model,
        "created_by": args.created_by,
        "job_id": args.job_id,
        "world_state": args.world_state,
        "tone": args.tone,
        "failure_mode": args.failure_mode,
    }
    for field, value in exact_filters.items():
        if value is not None:
            clauses.append({field: {"$eq": value}})
    if args.canon_candidate is not None:
        clauses.append({"canon_candidate": {"$eq": args.canon_candidate}})
    if args.min_aaron_score is not None:
        clauses.append({"aaron_score": {"$gte": args.min_aaron_score}})
    if args.max_aaron_score is not None:
        clauses.append({"aaron_score": {"$lte": args.max_aaron_score}})
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def query_collection(collection, vector, modality: str, args):
    try:
        total = collection.count()
    except Exception as e:
        raise RuntimeError(f"chroma count failed: {type(e).__name__}: {e}") from e
    if total == 0:
        return []
    n_results = max(args.top_k * 4, args.top_k)
    n_results = min(n_results, total)
    result = collection.query(
        query_embeddings=[vector],
        n_results=n_results,
        where=base_where(modality, args),
        include=["metadatas", "documents", "distances"],
    )
    ids = (result.get("ids") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    matches = []
    for record_id, metadata, document, distance in zip(ids, metadatas, documents, distances):
        metadata = metadata or {}
        score = similarity_from_distance(distance)
        if args.score_threshold is not None and score < args.score_threshold:
            continue
        matches.append({
            "record_id": record_id,
            "image_id": metadata.get("image_id"),
            "modality": modality,
            "score": score,
            "metadata": metadata,
            "document": document or "",
        })
    return matches


def empty_payload(args, note: str) -> dict[str, Any]:
    return {
        "ok": True,
        "query": args.query,
        "collection": COLLECTION_NAME,
        "mode": args.mode,
        "count": 0,
        "top_k": args.top_k,
        "matches": [],
        "image_ids": [],
        "note": note,
    }


def merge_matches(text_matches, image_matches, top_k: int):
    merged: dict[str, dict[str, Any]] = {}
    for item in text_matches:
        image_id = item.get("image_id")
        if not isinstance(image_id, str):
            continue
        row = merged.setdefault(image_id, {"image_id": image_id, "metadata": item["metadata"]})
        row["text_score"] = max(row.get("text_score", float("-inf")), item["score"])
        row["text_document"] = item.get("document", "")
        row["metadata"] = item["metadata"]
    for item in image_matches:
        image_id = item.get("image_id")
        if not isinstance(image_id, str):
            continue
        row = merged.setdefault(image_id, {"image_id": image_id, "metadata": item["metadata"]})
        row["image_score"] = max(row.get("image_score", float("-inf")), item["score"])
        row["image_document"] = item.get("document", "")
        row["metadata"] = item["metadata"]

    results = []
    for image_id, row in merged.items():
        text_score = row.get("text_score")
        image_score = row.get("image_score")
        if text_score is not None and image_score is not None:
            score = (0.55 * text_score) + (0.45 * image_score)
            basis = "hybrid"
        elif text_score is not None:
            score = text_score
            basis = "text_only"
        else:
            score = image_score
            basis = "image_only"
        metadata = row.get("metadata") or {}
        document = row.get("text_document") or row.get("image_document") or ""
        summary = document.strip().splitlines()[0] if document.strip() else metadata.get("filename", "")
        match = {
            "image_id": image_id,
            "score": round(float(score), 6),
            "image_score": None if image_score is None else round(float(image_score), 6),
            "text_score": None if text_score is None else round(float(text_score), 6),
            "score_basis": basis,
            "source_path": metadata.get("source_path"),
            "review_image_path": "",
            "anchor_promotion": metadata.get("anchor_promotion"),
            "quality_tier": metadata.get("quality_tier"),
            "aaron_score": metadata.get("aaron_score"),
            "model": metadata.get("model") or metadata.get("generation_model"),
            "job_id": metadata.get("job_id"),
            "image_origin": metadata.get("image_origin"),
            "summary": summary[:320],
        }
        results.append(match)
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def validate_inputs(args):
    if args.mode in {"text", "hybrid", "all"} and not args.query.strip():
        if args.mode != "hybrid" or not args.query_image:
            return "query must be non-empty for text search"
    if args.mode == "image" and not args.query_image:
        return "--query-image is required for image mode"
    if args.query_image and (not args.query_image.exists() or not args.query_image.is_file()):
        return f"query image not found: {args.query_image}"
    if args.mode == "hybrid" and not args.query.strip() and not args.query_image:
        return "hybrid mode requires query text, query image, or both"
    return None


def main():
    args = parse_args()
    args.query = args.query.strip()
    input_error = validate_inputs(args)
    if input_error:
        return json_exit({"ok": False, "stage": "input_validation", "error": input_error}, 2)

    try:
        collection = get_chroma_collection(args.chroma_path, create=True)
    except Exception as e:
        return json_exit({"ok": False, "stage": "chroma_client_init", "error": f"{type(e).__name__}: {e}"}, 1)

    try:
        if collection.count() == 0:
            return json_exit(empty_payload(args, "no indexed taste_memory records found"))
    except Exception as e:
        return json_exit({"ok": False, "stage": "chroma_count", "error": f"{type(e).__name__}: {e}"}, 1)

    text_matches = []
    image_matches = []
    try:
        if args.mode in {"text", "hybrid", "all"} and args.query:
            text_vec = embed_text(args.query)
            text_matches = query_collection(collection, text_vec, "search_text", args)
        if args.mode == "all" and args.query:
            image_matches.extend(query_collection(collection, text_vec, "image", args))
        if args.mode in {"image", "hybrid"} and args.query_image:
            image_vec = embed_image(args.query_image)
            image_matches = query_collection(collection, image_vec, "image", args)
    except Exception as e:
        stage = "embed_or_query"
        return json_exit({"ok": False, "stage": stage, "error": f"{type(e).__name__}: {e}"}, 1)

    matches = merge_matches(text_matches, image_matches, args.top_k)
    payload = {
        "ok": True,
        "query": args.query,
        "collection": COLLECTION_NAME,
        "mode": args.mode,
        "count": len(matches),
        "top_k": args.top_k,
        "ranking_version": RANKING_VERSION,
        "search_index_version": SEARCH_INDEX_VERSION,
        "filters": {
            "anchor_promotion": args.anchor_promotion,
            "quality_tier": args.quality_tier,
            "min_aaron_score": args.min_aaron_score,
            "max_aaron_score": args.max_aaron_score,
            "model": args.model,
            "created_by": args.created_by,
            "job_id": args.job_id,
            "world_state": args.world_state,
            "tone": args.tone,
            "failure_mode": args.failure_mode,
            "canon_candidate": args.canon_candidate,
            "include_holdouts": args.include_holdouts,
            "score_threshold": args.score_threshold,
        },
        "matches": matches,
        "image_ids": [match["image_id"] for match in matches],
    }
    if not matches:
        payload["note"] = "no indexed taste_memory records matched"
    if args.include_holdouts:
        payload["holdout_notice"] = "holdout_benchmark rows were explicitly allowed for this search"
    return json_exit(payload)


if __name__ == "__main__":
    sys.exit(main())
