"""Rebuild V1.1 taste_memory semantic-search records from durable logs.

Non-destructive by default: this script upserts stable V1.1 records and never
deletes or resets the taste_memory collection unless a future explicit cleanup
tool is written and Aaron approves running it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from taste_memory_common import (
    COLLECTION_NAME,
    SEARCH_INDEX_VERSION,
    build_metadata,
    build_search_text,
    compatibility_warnings,
    default_chroma_path,
    default_vault_root,
    embed_image,
    embed_text,
    get_chroma_collection,
    json_exit,
    resolve_source_path,
    source_summary,
    unified_states,
    vault_relative_path,
)


def parse_args():
    vault_root = default_vault_root()
    parser = argparse.ArgumentParser(description="Build or audit V1.1 taste_memory semantic-search records.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Plan work without writing Chroma records.")
    mode.add_argument("--apply", action="store_true", help="Upsert V1.1 taste_memory records.")
    parser.add_argument("--job-id", help="Limit to a reviewed/generated job id.")
    parser.add_argument("--image-id", help="Limit to one image_id.")
    parser.add_argument("--include-holdouts", action="store_true", help="Include holdout_benchmark rows.")
    parser.add_argument(
        "--include-non-generation-reviewed",
        action="store_true",
        help="Also index reviewed non-generation rows such as anchor_seed/external_inbox. Default is generation only.",
    )
    parser.add_argument("--compatibility-audit", action="store_true", help="Report non-V1.1 taste_memory records.")
    parser.add_argument("--vault-root", type=Path, default=vault_root)
    parser.add_argument("--chroma-path", type=Path, default=default_chroma_path(vault_root))
    return parser.parse_args()


def skip_reason(record: dict[str, Any], image_path: Path | None, args) -> str | None:
    if record.get("image_origin") == "smoke_test":
        return "image_origin=smoke_test"
    if record.get("image_origin") == "holdout_benchmark" and not args.include_holdouts:
        return "image_origin=holdout_benchmark excluded by default"
    if record.get("image_origin") != "generation" and not args.include_non_generation_reviewed:
        return f"image_origin={record.get('image_origin', 'unknown')} excluded by default"
    if args.job_id and record.get("job_id") != args.job_id:
        return "filtered_by_job_id"
    if args.image_id and record.get("image_id") != args.image_id:
        return "filtered_by_image_id"
    if image_path is None:
        return "missing source_path"
    if not image_path.exists() or not image_path.is_file():
        return f"image file not readable: {image_path}"
    return None


def candidate_records(args) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    states, malformed = unified_states(args.vault_root)
    candidates = []
    skipped = []
    for image_id, record in sorted(states.items()):
        source_value = record.get("source_path") or record.get("file_path")
        image_path = resolve_source_path(source_value, args.vault_root)
        reason = skip_reason(record, image_path, args)
        if reason:
            if reason not in {"filtered_by_job_id", "filtered_by_image_id"}:
                skipped.append({"image_id": image_id, "reason": reason})
            continue
        assert image_path is not None
        relative_source = vault_relative_path(image_path, args.vault_root)
        search_text = build_search_text(record)
        candidates.append({
            "image_id": image_id,
            "record": record,
            "image_path": image_path,
            "source_path": relative_source,
            "search_text": search_text,
        })
    return candidates, skipped, malformed


def audit(args) -> list[dict[str, Any]]:
    try:
        collection = get_chroma_collection(args.chroma_path, create=True)
    except Exception as e:
        return [{"record_id": "", "warning": f"chroma audit unavailable: {type(e).__name__}: {e}"}]
    return compatibility_warnings(collection)


def upsert_candidates(collection, candidates: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    upserted = 0
    failures = []
    for item in candidates:
        record = item["record"]
        image_id = item["image_id"]
        image_record_id = f"{image_id}::image"
        text_record_id = f"{image_id}::search_text"
        try:
            image_embedding = embed_image(item["image_path"])
            text_embedding = embed_text(item["search_text"])
            image_metadata = build_metadata(record, image_record_id, "image", item["source_path"])
            text_metadata = build_metadata(record, text_record_id, "search_text", item["source_path"])
            image_doc = source_summary(record)
            collection.upsert(
                ids=[image_record_id, text_record_id],
                embeddings=[image_embedding, text_embedding],
                metadatas=[image_metadata, text_metadata],
                documents=[image_doc, item["search_text"]],
            )
            upserted += 2
        except Exception as e:
            failures.append({"image_id": image_id, "stage": "upsert", "error": f"{type(e).__name__}: {e}"})
    return upserted, failures


def main():
    args = parse_args()
    candidates, skipped, malformed = candidate_records(args)
    warnings = audit(args) if args.compatibility_audit or args.apply else []
    failures: list[dict[str, Any]] = []
    upserted_records = 0
    before_count = None
    after_count = None

    if args.apply:
        try:
            collection = get_chroma_collection(args.chroma_path, create=True)
            before_count = collection.count()
        except Exception as e:
            return json_exit({"ok": False, "stage": "chroma_client_init", "error": f"{type(e).__name__}: {e}"}, 1)
        upserted_records, failures = upsert_candidates(collection, candidates)
        try:
            after_count = collection.count()
        except Exception:
            after_count = None

    indexed_images = len(candidates) if not failures else len(candidates) - len({item["image_id"] for item in failures})
    payload = {
        "ok": not failures,
        "dry_run": bool(args.dry_run),
        "collection": COLLECTION_NAME,
        "search_index_version": SEARCH_INDEX_VERSION,
        "candidate_images": len(candidates),
        "indexed_images": indexed_images if args.apply else 0,
        "would_index_images": len(candidates) if args.dry_run else None,
        "upserted_records": upserted_records,
        "skipped": skipped,
        "malformed_rows": malformed,
        "compatibility_warnings": warnings,
        "by_modality": {
            "image": indexed_images if args.apply else len(candidates),
            "search_text": indexed_images if args.apply else len(candidates),
        },
        "filters": {
            "job_id": args.job_id,
            "image_id": args.image_id,
            "include_holdouts": args.include_holdouts,
            "include_non_generation_reviewed": args.include_non_generation_reviewed,
        },
        "record_ids": [
            record_id
            for item in candidates
            for record_id in (f"{item['image_id']}::image", f"{item['image_id']}::search_text")
        ],
        "count_before": before_count,
        "count_after": after_count,
        "failures": failures,
        "destructive_actions": [],
        "note": "non-destructive: no taste_memory records were deleted or reset",
    }
    if args.dry_run:
        payload["indexed_images"] = 0
        payload["upserted_records"] = 0
    return json_exit(payload, 0 if payload["ok"] else 1)


if __name__ == "__main__":
    sys.exit(main())
