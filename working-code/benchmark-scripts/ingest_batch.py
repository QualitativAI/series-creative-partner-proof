"""Ingest completed generation assets into benchmark/logs/generations.jsonl.

The primary input is the Track 2.A Flow Arm result manifest shape:
`handoff-result.v1`. Each `targets_completed[].assets[]` item becomes one
durable `generation_ingested` row with packet lineage and copied image storage.
This is intentionally not a perception row and not a Brain pre-eval row.

    brain_initial_score_raw = taste_alignment = gold_similarity - anti_similarity

If `--score` is used and score.py succeeds, only the score/rank diagnostics are
persisted. When scoring is not requested or cannot complete, all score/rank
fields are persisted as null. No Group A perception fields or Group B creative
judgment fields are fabricated at ingest time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import validate_eval
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import validate_eval  # noqa: E402


RESULT_MANIFEST_SCHEMA_VERSION = "handoff-result.v1"
EVAL_SCHEMA_VERSION = "v1"
DEFAULT_HANDOFF_RESULTS = Path("/workspace/handoff/results/incoming")
DEFAULT_VAULT_ROOT = Path("/workspace/series-vault")
if not DEFAULT_VAULT_ROOT.exists():
    DEFAULT_VAULT_ROOT = Path(__file__).resolve().parents[2]
if not DEFAULT_HANDOFF_RESULTS.exists():
    DEFAULT_HANDOFF_RESULTS = DEFAULT_VAULT_ROOT.parent / "SeriesHandoff" / "results" / "incoming"

DEFAULT_GENERATIONS_LOG = DEFAULT_VAULT_ROOT / "benchmark" / "logs" / "generations.jsonl"
DEFAULT_LIBRARY_ROOT = DEFAULT_VAULT_ROOT / "assets" / "images" / "generated" / "jobs"
VALID_WORLD_STATES = validate_eval.WORLD_STATES
VALID_TONES = validate_eval.TONES
VALID_CREATED_BY = validate_eval.CREATED_BY_VALUES
RESULT_STATUS_VALUES = {"success", "partial", "failed"}
TOP_LEVEL_REQUIRED_FIELDS = {
    "schema_version",
    "manifest_type",
    "job_id",
    "intent_id",
    "packet_revision",
    "source_packet_path",
    "handoff_status",
    "result_status",
    "created_at",
    "dispatched_at",
    "claimed_at",
    "completed_at",
    "completed_by",
    "output_root",
    "prompts_completed",
    "failures",
    "warnings",
}
PROMPT_REQUIRED_FIELDS = {"prompt_id", "base_concept", "world_state", "tone", "targets_completed"}
TARGET_REQUIRED_FIELDS = {
    "target_id",
    "model",
    "model_version",
    "platform",
    "created_by",
    "generation_model",
    "rendered_prompt",
    "assets",
}
ASSET_REQUIRED_FIELDS = {
    "asset_id",
    "output_index",
    "file_path",
    "mime_type",
    "width",
    "height",
    "image_origin",
    "event_timestamp",
    "sha256",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}: line {line_num}: invalid JSON: {e}") from e
            if not isinstance(row, dict):
                raise ValueError(f"{path}: line {line_num}: expected JSON object")
            rows.append(row)
    return rows


def safe_part(value: Any, fallback: str) -> str:
    raw = str(value or fallback)
    cleaned = []
    for char in raw:
        if char.isalnum() or char in {"-", "_", "."}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    result = "".join(cleaned).strip(".-")
    return result or fallback


def short_image_id(path: Path) -> tuple[str, str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest[:16]}", digest


def infer_handoff_root(manifest_path: Path, output_root: str | None) -> Path:
    if not output_root:
        return manifest_path.parent
    output_parts = Path(output_root).parts
    parent_parts = manifest_path.parent.parts
    if len(parent_parts) >= len(output_parts) and parent_parts[-len(output_parts):] == output_parts:
        root_parts = parent_parts[:-len(output_parts)]
        if root_parts:
            return Path(*root_parts)
    return manifest_path.parent


def resolve_asset_path(asset_file_path: str, manifest_path: Path, output_root: str | None) -> Path:
    raw = Path(asset_file_path)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        handoff_root = infer_handoff_root(manifest_path, output_root)
        candidates.extend([
            Path.cwd() / raw,
            handoff_root / raw,
            manifest_path.parent / raw.name,
        ])

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"asset file not found: {asset_file_path}")


def vault_relative(path: Path, vault_root: Path) -> str:
    try:
        return path.resolve().relative_to(vault_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def copy_asset(source: Path, library_root: Path, job_id: str, model: str, prompt_id: str, asset_id: str) -> Path:
    suffix = source.suffix or ".png"
    dest_dir = library_root / safe_part(job_id, "job") / safe_part(model, "model") / safe_part(prompt_id, "prompt")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{safe_part(asset_id, source.stem)}{suffix}"
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    return dest


def nullable_score_fields(score_result: dict[str, Any] | None) -> dict[str, Any]:
    if not score_result or not score_result.get("ok"):
        return {
            "taste_alignment": None,
            "brain_initial_score_raw": None,
            "brain_initial_gold_similarity": None,
            "brain_initial_anti_similarity": None,
            "brain_initial_rank": None,
            "score_status": "not_run" if score_result is None else "unavailable",
            "score_error": None if score_result is None else score_result.get("error") or score_result.get("stage"),
        }
    raw = score_result.get("brain_initial_score_raw", score_result.get("taste_alignment"))
    return {
        "taste_alignment": raw,
        "brain_initial_score_raw": raw,
        "brain_initial_gold_similarity": score_result.get(
            "brain_initial_gold_similarity",
            score_result.get("gold_similarity"),
        ),
        "brain_initial_anti_similarity": score_result.get(
            "brain_initial_anti_similarity",
            score_result.get("anti_similarity"),
        ),
        "brain_initial_rank": score_result.get("brain_initial_rank"),
        "score_status": "scored",
        "score_error": None,
    }


def maybe_score_image(image_path: Path, world_state: str | None, enabled: bool) -> dict[str, Any] | None:
    if not enabled:
        return None
    try:
        import score
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import score  # type: ignore  # noqa: E402
    return score.score_image(image_path, world_state=world_state)


def require_vocab(value: Any, vocab: set[str], field: str, context: str) -> str | None:
    if value is None:
        return None
    if value not in vocab:
        raise ValueError(f"{context}: {field} {value!r} is not in vocab {sorted(vocab)}")
    return value


def require_created_by(value: Any, context: str) -> str:
    created_by = value or "unknown"
    if created_by not in VALID_CREATED_BY:
        raise ValueError(f"{context}: created_by {created_by!r} is not in vocab {sorted(VALID_CREATED_BY)}")
    return created_by


def require_fields(obj: dict[str, Any], required: set[str], context: str):
    missing = sorted(required - set(obj))
    if missing:
        raise ValueError(f"{context}: missing required handoff-result.v1 field(s): {', '.join(missing)}")


def require_non_empty_string(obj: dict[str, Any], field: str, context: str):
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}: {field} must be a non-empty string")


def require_iso_timestamp(obj: dict[str, Any], field: str, context: str):
    require_non_empty_string(obj, field, context)
    if parse_timestamp(obj[field]) is None:
        raise ValueError(f"{context}: {field} must be ISO 8601")


def validate_result_manifest_contract(manifest: dict[str, Any]) -> None:
    """Validate the Plan 05 `handoff-result.v1` shape before flattening.

    This is deliberately separate from the sample fixture. It pins the contract
    fields documented in Plan 05 so a real Flow Arm manifest cannot drift from
    `assets[].file_path` to `path`, omit model_version, or otherwise slip
    through by coincidence.
    """
    context = "result manifest"
    require_fields(manifest, TOP_LEVEL_REQUIRED_FIELDS, context)
    if manifest.get("schema_version") != RESULT_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"{context}: schema_version must be {RESULT_MANIFEST_SCHEMA_VERSION!r}; "
            f"got {manifest.get('schema_version')!r}"
        )
    if manifest.get("manifest_type") != "series_flowarm_result":
        raise ValueError(f"{context}: manifest_type must be 'series_flowarm_result'")
    if manifest.get("handoff_status") != "completed":
        raise ValueError(f"{context}: handoff_status must be 'completed'")
    if manifest.get("result_status") not in RESULT_STATUS_VALUES:
        raise ValueError(f"{context}: result_status must be one of {sorted(RESULT_STATUS_VALUES)}")

    for field in ("job_id", "intent_id", "source_packet_path", "completed_by", "output_root"):
        require_non_empty_string(manifest, field, context)
    if not isinstance(manifest.get("packet_revision"), int) or isinstance(manifest.get("packet_revision"), bool):
        raise ValueError(f"{context}: packet_revision must be an integer")
    for field in ("created_at", "dispatched_at", "claimed_at", "completed_at"):
        require_iso_timestamp(manifest, field, context)
    for field in ("prompts_completed", "failures", "warnings"):
        if not isinstance(manifest.get(field), list):
            raise ValueError(f"{context}: {field} must be a list")

    for prompt_index, prompt in enumerate(manifest["prompts_completed"], start=1):
        prompt_context = f"prompts_completed[{prompt_index}]"
        if not isinstance(prompt, dict):
            raise ValueError(f"{prompt_context}: must be an object")
        require_fields(prompt, PROMPT_REQUIRED_FIELDS, prompt_context)
        for field in ("prompt_id", "base_concept"):
            require_non_empty_string(prompt, field, prompt_context)
        require_vocab(prompt.get("world_state"), VALID_WORLD_STATES, "world_state", prompt_context)
        require_vocab(prompt.get("tone"), VALID_TONES, "tone", prompt_context)
        if not isinstance(prompt.get("targets_completed"), list):
            raise ValueError(f"{prompt_context}: targets_completed must be a list")

        for target_index, target in enumerate(prompt["targets_completed"], start=1):
            target_context = f"{prompt_context}.targets_completed[{target_index}]"
            if not isinstance(target, dict):
                raise ValueError(f"{target_context}: must be an object")
            require_fields(target, TARGET_REQUIRED_FIELDS, target_context)
            for field in ("target_id", "model", "model_version", "platform", "generation_model", "rendered_prompt"):
                require_non_empty_string(target, field, target_context)
            require_created_by(target.get("created_by"), target_context)
            if not isinstance(target.get("assets"), list):
                raise ValueError(f"{target_context}: assets must be a list")

            for asset_index, asset in enumerate(target["assets"], start=1):
                asset_context = f"{target_context}.assets[{asset_index}]"
                if not isinstance(asset, dict):
                    raise ValueError(f"{asset_context}: must be an object")
                require_fields(asset, ASSET_REQUIRED_FIELDS, asset_context)
                for field in ("asset_id", "file_path", "mime_type", "image_origin"):
                    require_non_empty_string(asset, field, asset_context)
                if asset.get("image_origin") != "generation":
                    raise ValueError(f"{asset_context}: image_origin must be 'generation'")
                if not isinstance(asset.get("output_index"), int) or isinstance(asset.get("output_index"), bool):
                    raise ValueError(f"{asset_context}: output_index must be an integer")
                for field in ("width", "height"):
                    if not isinstance(asset.get(field), int) or isinstance(asset.get(field), bool) or asset[field] < 1:
                        raise ValueError(f"{asset_context}: {field} must be a positive integer")
                require_iso_timestamp(asset, "event_timestamp", asset_context)
                sha = asset.get("sha256")
                if sha is not None and (not isinstance(sha, str) or not sha):
                    raise ValueError(f"{asset_context}: sha256 must be null or a non-empty string")


def build_generation_row(
    manifest: dict[str, Any],
    prompt: dict[str, Any],
    target: dict[str, Any],
    asset: dict[str, Any],
    manifest_path: Path,
    vault_root: Path,
    library_root: Path,
    score_enabled: bool,
    strict_hash: bool,
) -> dict[str, Any]:
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("result manifest is missing job_id")
    prompt_id = prompt.get("prompt_id") or "prompt"
    target_id = target.get("target_id") or "target"
    asset_id = asset.get("asset_id") or f"{job_id}_{prompt_id}_{target_id}_{asset.get('output_index', 1)}"
    model = target.get("model") or target.get("generation_model") or "unknown-model"
    source = resolve_asset_path(str(asset.get("file_path") or ""), manifest_path, manifest.get("output_root"))
    copied = copy_asset(source, library_root, job_id, str(model), str(prompt_id), str(asset_id))
    image_id, actual_sha256 = short_image_id(copied)

    declared_sha = asset.get("sha256")
    sha_mismatch = bool(declared_sha and declared_sha != actual_sha256)
    if strict_hash and sha_mismatch:
        raise ValueError(
            f"asset_id={asset_id!r}: declared sha256 {declared_sha!r} does not match copied file {actual_sha256!r}"
        )
    context = f"job_id={job_id!r} prompt_id={prompt_id!r} target_id={target_id!r} asset_id={asset_id!r}"
    world_state = require_vocab(prompt.get("world_state"), VALID_WORLD_STATES, "world_state", context)
    tone = require_vocab(prompt.get("tone"), VALID_TONES, "tone", context)
    event_timestamp = asset.get("event_timestamp") or manifest.get("completed_at") or manifest.get("created_at") or utc_now()
    session_id = manifest.get("completed_at") or manifest.get("created_at") or event_timestamp
    if parse_timestamp(session_id) is None:
        session_id = utc_now()
    if parse_timestamp(event_timestamp) is None:
        event_timestamp = session_id

    ingested_at = utc_now()
    score_fields = nullable_score_fields(maybe_score_image(copied, world_state, score_enabled))
    created_by = require_created_by(target.get("created_by"), context)
    image_origin = asset.get("image_origin") or "generation"
    if image_origin != "generation":
        raise ValueError(f"{context}: result-manifest assets must use image_origin='generation', got {image_origin!r}")

    row = {
        "schema_version": EVAL_SCHEMA_VERSION,
        "session_id": session_id,
        "image_id": image_id,
        "filename": copied.name,
        "source_path": vault_relative(copied, vault_root),
        "image_origin": image_origin,
        "created_by": created_by,
        "event_type": "generation_ingested",
        "review_status": "pending",
        "event_timestamp": ingested_at,
        "job_id": job_id,
        "intent_id": manifest.get("intent_id"),
        "packet_revision": manifest.get("packet_revision"),
        "prompt_id": prompt_id,
        "target_id": target_id,
        "asset_id": asset_id,
        "output_index": asset.get("output_index"),
        "base_concept": prompt.get("base_concept") or "",
        "world_state": world_state,
        "tone": tone,
        "model": model,
        "model_version": target.get("model_version") or "",
        "platform": target.get("platform") or "",
        "generation_model": target.get("generation_model") or target.get("model") or str(model),
        "rendered_prompt": target.get("rendered_prompt") or "",
        "file_path": vault_relative(copied, vault_root),
        "original_file_path": asset.get("file_path"),
        "original_resolved_path": str(source),
        "asset_event_timestamp": event_timestamp,
        "mime_type": asset.get("mime_type"),
        "width": asset.get("width"),
        "height": asset.get("height"),
        "sha256": actual_sha256,
        "declared_sha256": declared_sha,
        "sha256_mismatch": sha_mismatch,
        "ingest_source_manifest": str(manifest_path),
        "ingested_at": ingested_at,
    }
    row.update(score_fields)

    validation = validate_eval.validate_record(row, "generation_ingested")
    if not validation["ok"]:
        raise ValueError(
            f"generated row for asset_id={asset_id!r} failed validation: "
            f"{json.dumps(validation['errors'], sort_keys=True)}"
        )
    return row


def flatten_result_manifest(
    manifest: dict[str, Any],
    manifest_path: Path,
    vault_root: Path,
    library_root: Path,
    score_enabled: bool,
    strict_hash: bool,
) -> list[dict[str, Any]]:
    validate_result_manifest_contract(manifest)
    rows = []
    prompts = manifest.get("prompts_completed", [])
    if not isinstance(prompts, list):
        raise ValueError("result manifest prompts_completed must be a list")
    for prompt_index, prompt in enumerate(prompts, start=1):
        if not isinstance(prompt, dict):
            raise ValueError(f"prompts_completed[{prompt_index}] must be an object")
        targets = prompt.get("targets_completed", [])
        if not isinstance(targets, list):
            raise ValueError(f"prompt {prompt.get('prompt_id')!r}: targets_completed must be a list")
        for target_index, target in enumerate(targets, start=1):
            if not isinstance(target, dict):
                raise ValueError(f"prompt {prompt.get('prompt_id')!r}: target #{target_index} must be an object")
            assets = target.get("assets", [])
            if not isinstance(assets, list):
                raise ValueError(f"target {target.get('target_id')!r}: assets must be a list")
            for asset_index, asset in enumerate(assets, start=1):
                if not isinstance(asset, dict):
                    raise ValueError(f"target {target.get('target_id')!r}: asset #{asset_index} must be an object")
                rows.append(
                    build_generation_row(
                        manifest,
                        prompt,
                        target,
                        asset,
                        manifest_path,
                        vault_root,
                        library_root,
                        score_enabled,
                        strict_hash,
                    )
                )
    return rows


def row_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (row.get("job_id"), row.get("asset_id"), row.get("event_type"), row.get("image_id"))


def append_new_rows(path: Path, rows: list[dict[str, Any]], dry_run: bool = False) -> dict[str, Any]:
    existing_rows = read_jsonl(path)
    existing_keys = {row_key(row) for row in existing_rows}
    new_rows = [row for row in rows if row_key(row) not in existing_keys]
    skipped = len(rows) - len(new_rows)
    if not dry_run and new_rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            for row in new_rows:
                f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "path": str(path),
        "input_rows": len(rows),
        "appended": 0 if dry_run else len(new_rows),
        "would_append": len(new_rows),
        "skipped_duplicates": skipped,
    }


def ingest_result_manifest(
    manifest_path: Path,
    generations_log: Path = DEFAULT_GENERATIONS_LOG,
    vault_root: Path = DEFAULT_VAULT_ROOT,
    library_root: Path = DEFAULT_LIBRARY_ROOT,
    score_enabled: bool = False,
    strict_hash: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = read_json(manifest_path)
    rows = flatten_result_manifest(manifest, manifest_path, vault_root, library_root, score_enabled, strict_hash)
    if not rows:
        raise ValueError(f"{manifest_path}: no assets found to ingest")
    append_result = append_new_rows(generations_log, rows, dry_run=dry_run)
    return {
        "ok": True,
        "job_id": manifest.get("job_id"),
        "manifest_path": str(manifest_path),
        "row_count": len(rows),
        "image_ids": [row["image_id"] for row in rows],
        "score_status_counts": count_values(rows, "score_status"),
        "sha256_mismatch_count": sum(1 for row in rows if row.get("sha256_mismatch")),
        "generations_log": append_result,
        "library_root": str(library_root),
        "dry_run": dry_run,
    }


def count_values(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def ingest_from_gpt(job_id: str, prompt_mappings: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Small adapter for Brain-side GPT Image 2 staging.

    `prompt_mappings` may be either a list of asset-like dictionaries or an
    object with `prompts_completed`. The adapter builds an in-memory
    handoff-result-shaped manifest so both Flow Arm and Brain-side generation
    follow the same flattening path.
    """
    if isinstance(prompt_mappings, dict) and "prompts_completed" in prompt_mappings:
        manifest = dict(prompt_mappings)
    elif isinstance(prompt_mappings, list):
        raise ValueError(
            "list-only GPT ingest is ambiguous and loses prompt identity; pass a handoff-result-shaped object "
            "with prompts_completed instead"
        )
    else:
        raise ValueError("prompt_mappings must be a list or an object with prompts_completed")
    temp_manifest = DEFAULT_VAULT_ROOT / "working" / "job-packets" / "gpt-ingest" / f"{safe_part(job_id, 'job')}.manifest.json"
    temp_manifest.parent.mkdir(parents=True, exist_ok=True)
    temp_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    return ingest_result_manifest(temp_manifest)


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest a Flow Arm handoff-result.v1 manifest into generations.jsonl.")
    parser.add_argument("job_id", nargs="?", help="Job ID. Used to find the default handoff manifest when --result-manifest is omitted.")
    parser.add_argument("--result-manifest", type=Path, help="Path to a handoff-result.v1 manifest.")
    parser.add_argument("--generations-log", type=Path, default=DEFAULT_GENERATIONS_LOG)
    parser.add_argument("--vault-root", type=Path, default=DEFAULT_VAULT_ROOT)
    parser.add_argument("--library-root", type=Path, default=DEFAULT_LIBRARY_ROOT)
    parser.add_argument("--score", action="store_true", help="Attempt score.py for each copied asset.")
    parser.add_argument(
        "--allow-sha-mismatch",
        action="store_true",
        help="Append rows even when a manifest sha256 does not match copied file bytes. Default is to refuse.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without appending to generations.jsonl.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.result_manifest
    if manifest_path is None:
        if not args.job_id:
            raise SystemExit("job_id is required when --result-manifest is omitted")
        manifest_path = DEFAULT_HANDOFF_RESULTS / args.job_id / "manifest.json"

    try:
        result = ingest_result_manifest(
            manifest_path=manifest_path,
            generations_log=args.generations_log,
            vault_root=args.vault_root,
            library_root=args.library_root,
            score_enabled=args.score,
            strict_hash=not args.allow_sha_mismatch,
            dry_run=args.dry_run,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
