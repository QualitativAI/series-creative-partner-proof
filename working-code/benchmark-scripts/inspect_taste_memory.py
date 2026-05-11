"""Inspect V1.1 taste_memory collection shape without modifying it."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from taste_memory_common import (
    COLLECTION_NAME,
    SEARCH_INDEX_VERSION,
    compatibility_warnings,
    default_chroma_path,
    default_vault_root,
    get_chroma_collection,
    is_valid_v11_record,
    json_exit,
)


def parse_args():
    vault_root = default_vault_root()
    parser = argparse.ArgumentParser(description="Inspect V1.1 taste_memory records.")
    parser.add_argument("--vault-root", type=Path, default=vault_root)
    parser.add_argument("--chroma-path", type=Path, default=default_chroma_path(vault_root))
    parser.add_argument("--sample", type=int, default=3)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        collection = get_chroma_collection(args.chroma_path, create=True)
        data = collection.get(include=["metadatas", "documents"])
    except Exception as e:
        return json_exit({"ok": False, "stage": "chroma_inspect", "error": f"{type(e).__name__}: {e}"}, 1)

    ids = data.get("ids") or []
    metadatas = data.get("metadatas") or []
    documents = data.get("documents") or []
    by_modality = Counter()
    by_anchor = Counter()
    by_origin = Counter()
    image_ids = set()
    samples = []
    for record_id, metadata, document in zip(ids, metadatas, documents):
        metadata = metadata or {}
        if not is_valid_v11_record(record_id, metadata):
            continue
        image_ids.add(metadata.get("image_id"))
        by_modality[metadata.get("modality")] += 1
        by_anchor[metadata.get("anchor_promotion", "none")] += 1
        by_origin[metadata.get("image_origin", "unknown")] += 1
        if len(samples) < args.sample:
            samples.append({
                "record_id": record_id,
                "image_id": metadata.get("image_id"),
                "modality": metadata.get("modality"),
                "anchor_promotion": metadata.get("anchor_promotion"),
                "source_path": metadata.get("source_path"),
                "document_preview": (document or "")[:220],
            })

    payload = {
        "ok": True,
        "collection": COLLECTION_NAME,
        "count": len(ids),
        "v11_count": sum(by_modality.values()),
        "unique_image_count": len(image_ids),
        "search_index_version": SEARCH_INDEX_VERSION,
        "by_modality": dict(sorted(by_modality.items())),
        "by_anchor_promotion": dict(sorted(by_anchor.items())),
        "by_image_origin": dict(sorted(by_origin.items())),
        "compatibility_warnings": compatibility_warnings(collection),
        "sample_records": samples,
    }
    return json_exit(payload)


if __name__ == "__main__":
    sys.exit(main())
