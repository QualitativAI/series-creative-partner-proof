"""Shared helpers for V1.1 taste_memory semantic search tooling."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMS = 3072
COLLECTION_NAME = "taste_memory"
SEARCH_INDEX_VERSION = "v1.1-taste-memory-001"
RANKING_VERSION = "v1.1-hybrid-0.55-text-0.45-image"
HNSW_SPACE = "cosine"

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

STRING_FIELDS = {
    "image_id",
    "record_id",
    "modality",
    "filename",
    "source_path",
    "image_origin",
    "created_by",
    "job_id",
    "intent_id",
    "prompt_id",
    "target_id",
    "asset_id",
    "model",
    "model_version",
    "generation_model",
    "world_state",
    "tone",
    "quality_tier",
    "anchor_promotion",
    "failure_mode",
    "fits_current_scene",
    "feedback_tags",
    "review_status",
    "event_type_latest",
    "latest_event_timestamp",
    "final_eval_timestamp",
    "brain_initial_rank",
    "brain_initial_quality_tier",
    "brain_initial_anchor_promotion_recommendation",
    "schema_version",
    "search_index_version",
}

NUMERIC_FIELDS = {"aaron_score"}
BOOLEAN_FIELDS = {"canon_candidate"}
MODALITIES = {"image", "search_text"}


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
    return Path(__file__).resolve().parents[2]


def default_chroma_path(vault_root: Path) -> Path:
    return vault_root / "benchmark" / "chroma_data"


def json_exit(payload: dict[str, Any], code: int = 0) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return code


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as e:
        raise ValueError("must be an integer") from e
    if parsed < 1:
        raise ValueError("must be positive")
    return parsed


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    malformed = []
    if not path.exists():
        return rows, malformed
    with path.open() as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as e:
                malformed.append({"path": str(path), "line": line_num, "error": str(e)})
                continue
            if isinstance(row, dict):
                row["_append_order"] = len(rows)
                row["_source_log"] = path.name
                rows.append(row)
            else:
                malformed.append({"path": str(path), "line": line_num, "error": "JSON root is not an object"})
    return rows, malformed


def vault_relative_path(path: Path, vault_root: Path) -> str:
    try:
        return path.resolve().relative_to(vault_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def resolve_source_path(value: Any, vault_root: Path) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        workspace_root = Path("/workspace/series-vault")
        try:
            return vault_root / path.relative_to(workspace_root)
        except ValueError:
            return path
    return vault_root / path


def scalar_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def scalar_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False


def scalar_number(value: Any, default: float = -1.0) -> int | float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return default
        return int(parsed) if parsed.is_integer() else parsed
    return default


def compact_text(value: Any, limit: int = 700) -> str:
    text = scalar_string(value).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def row_sort_key(row: dict[str, Any]) -> tuple[datetime, int]:
    return (parse_timestamp(row.get("event_timestamp")), int(row.get("_append_order", 0)))


def latest_by_event(rows: list[dict[str, Any]], event_type: str) -> dict[str, dict[str, Any]]:
    latest = {}
    for row in rows:
        if row.get("event_type") != event_type:
            continue
        image_id = row.get("image_id")
        if not isinstance(image_id, str) or not image_id:
            continue
        key = row_sort_key(row)
        current = latest.get(image_id)
        if current is None or key >= current[0]:
            latest[image_id] = (key, row)
    return {image_id: row for image_id, (_, row) in latest.items()}


def load_source_rows(vault_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    logs_dir = vault_root / "benchmark" / "logs"
    paths = [
        logs_dir / "generations.jsonl",
        logs_dir / "perception_history.jsonl",
        logs_dir / "pre_eval_history.jsonl",
        logs_dir / "final_eval_history.jsonl",
    ]
    rows = []
    malformed = []
    order = 0
    for path in paths:
        loaded, bad = read_jsonl(path)
        for row in loaded:
            row["_append_order"] = order
            order += 1
            rows.append(row)
        malformed.extend(bad)
    return rows, malformed


def load_promoted_anchor_sources(vault_root: Path) -> dict[str, str]:
    manifest = read_json(vault_root / "benchmark" / "anchors" / "manifest.json")
    anchors = manifest.get("anchors")
    if not isinstance(anchors, dict):
        return {}
    result = {}
    for image_id, entry in anchors.items():
        if isinstance(image_id, str) and isinstance(entry, dict) and isinstance(entry.get("source_path"), str):
            result[image_id] = entry["source_path"]
    return result


def unified_states(vault_root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    rows, malformed = load_source_rows(vault_root)
    generation = latest_by_event(rows, "generation_ingested")
    perception = latest_by_event(rows, "perception")
    pre_eval = latest_by_event(rows, "pre_eval")
    final_eval = latest_by_event(rows, "final_eval")
    promoted_sources = load_promoted_anchor_sources(vault_root)
    image_ids = sorted(set(generation) | set(perception) | set(pre_eval) | set(final_eval))
    states = {}
    for image_id in image_ids:
        merged: dict[str, Any] = {}
        latest_event_row = None
        for layer in (generation.get(image_id), perception.get(image_id), pre_eval.get(image_id), final_eval.get(image_id)):
            if not layer:
                continue
            merged.update({k: v for k, v in layer.items() if not k.startswith("_")})
            latest_event_row = layer
        if latest_event_row:
            merged["event_type_latest"] = latest_event_row.get("event_type", "")
            merged["latest_event_timestamp"] = latest_event_row.get("event_timestamp", "")
        if image_id in promoted_sources:
            merged["anchor_source_path"] = promoted_sources[image_id]
        states[image_id] = merged
    return states, malformed


def build_search_text(record: dict[str, Any]) -> str:
    perception_bits = [
        compact_text(record.get("perception_subject"), 240),
        compact_text(record.get("perception_composition"), 240),
        compact_text(record.get("perception_atmosphere"), 240),
        compact_text(record.get("perception_notable_details"), 260),
    ]
    perception_bits = [bit for bit in perception_bits if bit]
    corrections = record.get("aaron_perception_corrections")
    if isinstance(corrections, list):
        corrections_text = "; ".join(str(item) for item in corrections if isinstance(item, str))
    else:
        corrections_text = scalar_string(corrections)
    parts = [
        f"Image ID: {scalar_string(record.get('image_id'))}",
        f"Visual description: {' '.join(perception_bits)}",
        f"Full perception excerpt: {compact_text(record.get('perception_text'), 900)}",
        (
            "Brain initial read: "
            f"quality {scalar_string(record.get('brain_initial_quality_tier'), 'unknown')}; "
            f"world_state {scalar_string(record.get('brain_initial_world_state'), 'unknown')}; "
            f"tone {scalar_string(record.get('brain_initial_tone'), 'unknown')}; "
            "promotion recommendation "
            f"{scalar_string(record.get('brain_initial_anchor_promotion_recommendation'), 'unknown')}; "
            f"rank {scalar_string(record.get('brain_initial_rank'), 'unknown')}; "
            f"notes {compact_text(record.get('brain_initial_notes'), 450)}; "
            f"tags {compact_text(record.get('brain_initial_tags'), 260)}."
        ),
        (
            "Aaron final read: "
            f"anchor promotion {scalar_string(record.get('anchor_promotion'), 'none')}; "
            f"score {scalar_string(record.get('aaron_score'), 'unknown')}; "
            f"quality {scalar_string(record.get('quality_tier'), 'unknown')}; "
            f"world_state {scalar_string(record.get('world_state'), 'unknown')}; "
            f"tone {scalar_string(record.get('tone'), 'unknown')}; "
            f"scene fit {scalar_string(record.get('fits_current_scene'), 'unknown')}; "
            f"failure mode {scalar_string(record.get('failure_mode'), 'none')}; "
            f"canon candidate {scalar_string(record.get('canon_candidate'), 'false')}."
        ),
        (
            "Aaron feedback: "
            f"{compact_text(record.get('feedback_text'), 700)} "
            f"Final notes: {compact_text(record.get('final_notes'), 450)} "
            f"Perception corrections: {compact_text(corrections_text, 300)} "
            f"Feedback tags: {compact_text(record.get('feedback_tags'), 260)}."
        ),
        (
            "Lineage: "
            f"job {scalar_string(record.get('job_id'), 'unknown')}; "
            f"prompt {scalar_string(record.get('prompt_id'), 'unknown')}; "
            f"model {scalar_string(record.get('model') or record.get('generation_model'), 'unknown')}; "
            f"created_by {scalar_string(record.get('created_by'), 'unknown')}; "
            f"base concept {compact_text(record.get('base_concept'), 360)}; "
            f"rendered prompt summary {compact_text(record.get('rendered_prompt'), 500)}."
        ),
    ]
    return "\n".join(part for part in parts if part.strip())


def build_metadata(record: dict[str, Any], record_id: str, modality: str, source_path: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    merged = dict(record)
    merged["record_id"] = record_id
    merged["modality"] = modality
    merged["source_path"] = source_path
    merged["search_index_version"] = SEARCH_INDEX_VERSION
    merged["fits_current_scene"] = scalar_string(merged.get("fits_current_scene"), "")
    failure_mode = scalar_string(merged.get("failure_mode"), "").strip()
    merged["failure_mode"] = failure_mode or "none"
    for field in STRING_FIELDS:
        value = merged.get(field)
        if field == "anchor_promotion":
            value = value if value is not None else "none"
        elif field == "modality":
            value = modality
        elif field == "record_id":
            value = record_id
        elif field == "source_path":
            value = source_path
        elif field == "search_index_version":
            value = SEARCH_INDEX_VERSION
        metadata[field] = scalar_string(value)
    for field in NUMERIC_FIELDS:
        metadata[field] = scalar_number(merged.get(field), -1)
    for field in BOOLEAN_FIELDS:
        metadata[field] = scalar_bool(merged.get(field))
    return metadata


def is_valid_v11_record(record_id: str, metadata: dict[str, Any] | None) -> bool:
    if not isinstance(record_id, str) or "::" not in record_id:
        return False
    if not isinstance(metadata, dict):
        return False
    if metadata.get("search_index_version") != SEARCH_INDEX_VERSION:
        return False
    if metadata.get("modality") not in MODALITIES:
        return False
    image_id = metadata.get("image_id")
    modality = metadata.get("modality")
    return isinstance(image_id, str) and record_id == f"{image_id}::{modality}"


def get_chroma_collection(chroma_path: Path, create: bool = True):
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_path))
    if create:
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": HNSW_SPACE},
        )
    return client.get_collection(COLLECTION_NAME)


def compatibility_warnings(collection) -> list[dict[str, Any]]:
    warnings = []
    try:
        data = collection.get(include=["metadatas"])
    except Exception as e:
        return [{"record_id": "", "warning": f"compatibility audit failed: {type(e).__name__}: {e}"}]
    ids = data.get("ids") or []
    metadatas = data.get("metadatas") or []
    for record_id, metadata in zip(ids, metadatas):
        metadata = metadata or {}
        if is_valid_v11_record(record_id, metadata):
            continue
        reason = "non-v1.1 record shape"
        if isinstance(record_id, str) and "::" not in record_id:
            reason = "plain image_id or legacy id"
        elif metadata.get("search_index_version") != SEARCH_INDEX_VERSION:
            reason = "missing or non-v1.1 search_index_version"
        elif metadata.get("modality") not in MODALITIES:
            reason = "missing or invalid modality"
        warnings.append({
            "record_id": record_id,
            "image_id": metadata.get("image_id") or record_id,
            "warning": reason,
        })
    return warnings


def embed_text(text: str) -> list[float]:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set in environment.")
    from google import genai
    from google.genai import types

    client = genai.Client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    vec = list(result.embeddings[0].values)
    if len(vec) != EMBEDDING_DIMS:
        raise ValueError(f"Expected {EMBEDDING_DIMS}-dim vector, got {len(vec)}")
    return vec


def embed_image(image_path: Path) -> list[float]:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set in environment.")
    from google import genai
    from google.genai import types

    client = genai.Client()
    mime = MIME_BY_SUFFIX.get(image_path.suffix.lower(), "image/jpeg")
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[types.Part.from_bytes(data=image_path.read_bytes(), mime_type=mime)],
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    vec = list(result.embeddings[0].values)
    if len(vec) != EMBEDDING_DIMS:
        raise ValueError(f"Expected {EMBEDDING_DIMS}-dim vector, got {len(vec)}")
    return vec


def similarity_from_distance(distance: Any) -> float:
    return 1.0 - float(distance)


def source_summary(record: dict[str, Any]) -> str:
    return compact_text(
        record.get("final_notes")
        or record.get("feedback_text")
        or record.get("brain_initial_notes")
        or record.get("perception_subject")
        or "",
        260,
    )
