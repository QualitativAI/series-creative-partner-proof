"""embed_anchors.py — embed confirmed anchors into Chroma with hard guardrails.

Per benchmark/SCHEMA.md "Embed-after-confirm rule" and plan 04 step 10.

Two modes:

    --record-file <path>     single confirmed eval record from file
    --record-stdin           single confirmed eval record from stdin
    --bulk                   re-embed every entry in manifest.json (recovery / re-index)

Single-record mode is the canonical write path used during anchor curation.
It runs the full validate_eval.py --mode embed_ready guardrail before any
Chroma write, embeds the image via Gemini Embedding 2 at 3072 dims,
upserts into the visual_anchors collection, appends the locked entry to
manifest.json, and appends a status-bump row to final_eval_history.jsonl.

Bulk mode is for recovery only (e.g., Chroma index loss). It trusts the
manifest entries as already-validated and re-embeds them. It does NOT
append status-bump rows — that's only for first-time embeds.

If anchor_promotion == "none" the script returns "skipped" without
embedding, never writes to Chroma, never updates manifest.json.

Holdout benchmark anti-leakage is stricter: image_origin=holdout_benchmark
with any promotion other than "none" hard-fails before validation, Chroma, or
manifest writes. With promotion "none" it returns a holdout-specific skip.

Output: JSON to stdout describing what happened.
Exit 0 on success, 1 on validation/embedding failure.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_eval  # noqa: E402

# chromadb and google.genai are imported lazily inside the functions that need them.
# Reason: anchor_promotion=="none" returns a structured skip before any heavy
# dependency is initialized. If we top-level-imported these, a missing dep would
# crash the script before main() runs, defeating the structured-error guarantee.

SCHEMA_VERSION = "v1"
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMS = 3072

CHROMA_PATH = "/workspace/series-vault/benchmark/chroma_data"
MANIFEST_PATH = Path("/workspace/series-vault/benchmark/anchors/manifest.json")
FINAL_EVAL_LOG_PATH = Path("/workspace/series-vault/benchmark/logs/final_eval_history.jsonl")
VAULT_CONTAINER_ROOT = Path("/workspace/series-vault")
COLLECTION_NAME = "visual_anchors"

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def default_vault_root() -> Path:
    env_root = os.environ.get("SERIES_VAULT_ROOT")
    if env_root:
        return Path(env_root)
    cwd = Path.cwd()
    if (cwd / "benchmark" / "SCHEMA.md").exists():
        return cwd
    workspace_root = Path("/workspace/series-vault")
    if (workspace_root / "benchmark" / "SCHEMA.md").exists():
        return workspace_root
    return cwd


def configure_paths(vault_root: Path) -> None:
    global CHROMA_PATH, MANIFEST_PATH, FINAL_EVAL_LOG_PATH, VAULT_CONTAINER_ROOT
    VAULT_CONTAINER_ROOT = vault_root
    CHROMA_PATH = str(vault_root / "benchmark" / "chroma_data")
    MANIFEST_PATH = vault_root / "benchmark" / "anchors" / "manifest.json"
    FINAL_EVAL_LOG_PATH = vault_root / "benchmark" / "logs" / "final_eval_history.jsonl"
    validate_eval.VAULT_CONTAINER_ROOT = vault_root


def vault_relative_path(path_str: str) -> str:
    """Return path as vault-relative for storage in manifest.json + Chroma metadata."""
    p = Path(path_str)
    if p.is_absolute():
        try:
            return str(p.relative_to(VAULT_CONTAINER_ROOT))
        except ValueError:
            return path_str
    return path_str


def embed_image(image_path: Path) -> list:
    """Embed an image via Gemini Embedding 2 at 3072 dims. Lazy-imports google.genai."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set in container env. Check docker_forward_env in profile config.")

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


def get_chroma_client():
    """Lazy import of chromadb so the script can return structured skip errors
    even when chromadb is not installed. Wraps init in try/except for stage reporting."""
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_PATH)


def compute_image_id(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest[:16]}"


def build_chroma_metadata(record: dict) -> dict:
    """Flat scalars/strings only — Chroma metadata flatness rule."""
    return {
        "image_id": record["image_id"],
        "filename": record["filename"],
        "source_path": vault_relative_path(record["source_path"]),
        "anchor_type": record["anchor_promotion"],
        "created_by": record.get("created_by", "unknown"),
        "image_origin": record.get("image_origin", "anchor_seed"),
        "world_state": record["world_state"],
        "tone": record["tone"],
        "quality_tier": record["quality_tier"],
        "aaron_score": int(record["aaron_score"]),
        "session_id": record["session_id"],
        "final_eval_timestamp": record["final_eval_timestamp"],
        "schema_version": record["schema_version"],
    }


def build_manifest_entry(record: dict) -> dict:
    """Per SCHEMA.md manifest.json per-anchor entry shape."""
    return {
        "image_id": record["image_id"],
        "filename": record["filename"],
        "source_path": vault_relative_path(record["source_path"]),
        "anchor_type": record["anchor_promotion"],
        "created_by": record.get("created_by", "unknown"),
        "image_origin": record.get("image_origin", "anchor_seed"),
        "world_state": record["world_state"],
        "tone": record["tone"],
        "quality_tier": record["quality_tier"],
        "aaron_score": int(record["aaron_score"]),
        "notes": record["final_notes"],
        "session_id": record["session_id"],
        "final_eval_timestamp": record["final_eval_timestamp"],
        "schema_version": record["schema_version"],
    }


def update_manifest(entry: dict) -> None:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"manifest.json not found at {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text())
    if "anchors" not in manifest or not isinstance(manifest["anchors"], dict):
        raise ValueError("manifest.json missing or malformed 'anchors' object")
    manifest["anchors"][entry["image_id"]] = entry
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def append_status_bump(record: dict) -> None:
    """Per SCHEMA.md: append {event_type: embedded, review_status: embedded} bump row."""
    FINAL_EVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    bump = {
        "schema_version": record["schema_version"],
        "session_id": record["session_id"],
        "image_id": record["image_id"],
        "filename": record["filename"],
        "source_path": vault_relative_path(record["source_path"]),
        "image_origin": record.get("image_origin", "anchor_seed"),
        "created_by": record.get("created_by", "unknown"),
        "event_type": "embedded",
        "review_status": "embedded",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with FINAL_EVAL_LOG_PATH.open("a") as f:
        f.write(json.dumps(bump) + "\n")


def embed_single_record(record: dict, chroma_client) -> dict:
    """Single-record path: validate, embed, write to all three durable surfaces.

    Wraps each stage in try/except so failures return structured JSON describing
    which stage failed instead of raising tracebacks.
    """
    image_id = record.get("image_id")

    if record.get("image_origin") == "holdout_benchmark":
        if record.get("anchor_promotion") != "none":
            return {
                "ok": False,
                "image_id": image_id,
                "stage": "holdout_anti_leakage",
                "error": (
                    "holdout_benchmark images cannot be embedded; re-ingest as "
                    "image_origin=anchor_seed if promotion is intended."
                ),
            }
        return {
            "ok": True,
            "image_id": image_id,
            "skipped": "holdout reviewed without promotion - no embed or manifest write.",
        }

    if record.get("anchor_promotion") == "none":
        return {
            "ok": True,
            "image_id": image_id,
            "skipped": "anchor_promotion=none — logged elsewhere, not embedded",
        }

    try:
        validation = validate_eval.validate_record(record, "embed_ready")
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "validation_invocation",
                "error": f"{type(e).__name__}: {e}"}
    if not validation["ok"]:
        return {
            "ok": False,
            "image_id": image_id,
            "stage": "validate_eval --mode embed_ready",
            "errors": validation["errors"],
        }

    try:
        src = validate_eval.resolve_source_path(record)
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "resolve_source_path",
                "error": f"{type(e).__name__}: {e}"}

    try:
        vec = embed_image(src)
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "embed_image",
                "error": f"{type(e).__name__}: {e}"}

    try:
        metadata = build_chroma_metadata(record)
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        collection.upsert(
            ids=[record["image_id"]],
            embeddings=[vec],
            metadatas=[metadata],
        )
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "chroma_upsert",
                "error": f"{type(e).__name__}: {e}"}

    try:
        entry = build_manifest_entry(record)
        update_manifest(entry)
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "update_manifest",
                "error": f"{type(e).__name__}: {e}"}

    try:
        append_status_bump(record)
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "append_status_bump",
                "error": f"{type(e).__name__}: {e}"}

    return {
        "ok": True,
        "image_id": image_id,
        "anchor_type": record["anchor_promotion"],
        "vector_dims": len(vec),
        "chroma_collection": COLLECTION_NAME,
        "manifest_updated": True,
        "status_bump_logged": True,
    }


def reembed_from_manifest_entry(entry: dict, chroma_client) -> dict:
    """Bulk recovery: re-embed an existing manifest entry. Skips status-bump.

    Verifies the file's current sha256 matches the manifest's image_id before
    upserting, so a replaced-on-disk file can't sneak new pixels in under the
    old logical ID.
    """
    image_id = entry.get("image_id")
    src_str = entry.get("source_path", "")
    src = Path(src_str)
    if not src.is_absolute():
        src = VAULT_CONTAINER_ROOT / src_str
    if not src.exists() or not src.is_file():
        return {"ok": False, "image_id": image_id, "stage": "file_check",
                "error": f"file not found: {src}"}

    try:
        computed = compute_image_id(src)
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "compute_image_id",
                "error": f"{type(e).__name__}: {e}"}
    if computed != image_id:
        return {
            "ok": False, "image_id": image_id, "stage": "content_hash_check",
            "error": f"file at {src} hashes to {computed}, does not match manifest's {image_id}",
        }

    try:
        vec = embed_image(src)
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "embed_image",
                "error": f"{type(e).__name__}: {e}"}

    try:
        metadata = {
            "image_id": entry["image_id"],
            "filename": entry["filename"],
            "source_path": entry["source_path"],
            "anchor_type": entry["anchor_type"],
            "created_by": entry.get("created_by", "unknown"),
            "image_origin": entry.get("image_origin", "anchor_seed"),
            "world_state": entry["world_state"],
            "tone": entry["tone"],
            "quality_tier": entry["quality_tier"],
            "aaron_score": int(entry["aaron_score"]),
            "session_id": entry["session_id"],
            "final_eval_timestamp": entry["final_eval_timestamp"],
            "schema_version": entry["schema_version"],
        }
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        collection.upsert(
            ids=[entry["image_id"]],
            embeddings=[vec],
            metadatas=[metadata],
        )
    except Exception as e:
        return {"ok": False, "image_id": image_id, "stage": "chroma_upsert",
                "error": f"{type(e).__name__}: {e}"}

    return {
        "ok": True,
        "image_id": image_id,
        "anchor_type": entry["anchor_type"],
        "vector_dims": len(vec),
        "mode": "bulk_reembed",
    }


def run_bulk(chroma_client) -> int:
    if not MANIFEST_PATH.exists():
        sys.stderr.write(f"ERROR: manifest.json not found at {MANIFEST_PATH}\n")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text())
    anchors = manifest.get("anchors", {})

    if not anchors:
        print(json.dumps({"ok": True, "mode": "bulk", "embedded_count": 0, "note": "no anchors to embed"}, indent=2))
        return 0

    results = []
    any_failed = False
    for image_id, entry in anchors.items():
        try:
            result = reembed_from_manifest_entry(entry, chroma_client)
        except Exception as e:
            result = {"ok": False, "image_id": image_id, "error": f"exception: {type(e).__name__}: {e}"}
        results.append(result)
        if not result.get("ok"):
            any_failed = True

    print(json.dumps({"ok": not any_failed, "mode": "bulk", "results": results}, indent=2))
    return 0 if not any_failed else 1


def main():
    configure_paths(default_vault_root())
    parser = argparse.ArgumentParser(description="Embed confirmed anchors into Chroma's visual_anchors collection.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--record-file", help="Path to a JSON file containing a single confirmed eval record")
    src.add_argument("--record-stdin", action="store_true", help="Read a single confirmed eval record from stdin")
    src.add_argument("--bulk", action="store_true", help="Re-embed every entry in manifest.json (recovery mode)")
    args = parser.parse_args()

    if args.bulk:
        try:
            chroma_client = get_chroma_client()
        except Exception as e:
            print(json.dumps({
                "ok": False,
                "stage": "chroma_client_init",
                "error": f"{type(e).__name__}: {e}",
                "chroma_path": CHROMA_PATH,
            }, indent=2))
            sys.exit(1)
        sys.exit(run_bulk(chroma_client))

    # Single-record mode: read input FIRST, check promotion, only init Chroma if actually embedding.
    if args.record_file:
        raw = Path(args.record_file).read_text()
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        print(json.dumps({"ok": False, "stage": "input_read", "error": "empty input"}, indent=2))
        sys.exit(1)

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "stage": "input_parse", "error": f"input is not valid JSON: {e}"}, indent=2))
        sys.exit(1)

    # Skip and holdout-guard paths return without ever importing chromadb.
    # This is the primary reason for lazy imports.
    if record.get("anchor_promotion") == "none" or record.get("image_origin") == "holdout_benchmark":
        result = embed_single_record(record, chroma_client=None)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["ok"] else 1)

    # Real embed path: now we need Chroma. Initialize with structured error reporting.
    try:
        chroma_client = get_chroma_client()
    except Exception as e:
        print(json.dumps({
            "ok": False,
            "stage": "chroma_client_init",
            "error": f"{type(e).__name__}: {e}",
            "chroma_path": CHROMA_PATH,
        }, indent=2))
        sys.exit(1)

    result = embed_single_record(record, chroma_client)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
