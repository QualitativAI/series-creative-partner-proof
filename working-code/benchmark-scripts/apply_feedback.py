"""apply_feedback.py - append confirmed Aaron feedback to benchmark logs.

Reads a structured pending-feedback JSON file, finds the latest
`generations.jsonl` row for each referenced image, merges confirmed Group C
feedback onto that latest row, validates the resulting final-eval record, and
appends it to:

- benchmark/logs/feedback.jsonl
- benchmark/logs/final_eval_history.jsonl
- benchmark/logs/generations.jsonl

Confirmed rows with anchor_promotion in {gold, anti, aspirational} are also
materialized into the visual anchor system by copying generated assets into
benchmark/anchors/<promotion>/ and invoking embed_anchors.py.

Existing rows are never edited. Consumers should use latest-row-per-image
logic when presenting review packets or summaries.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from promote_generated_anchors import PROMOTED_VALUES, preflight_records, promote_records
from taste_memory_common import SEARCH_INDEX_VERSION
from validate_eval import ANCHOR_PROMOTIONS, FAILURE_MODES, GROUP_C_FIELDS, GROUP_C_OPTIONAL, QUALITY_TIERS
from validate_eval import TONES, WORLD_STATES, validate_record


OPTIONAL_GROUP_C_FIELDS = GROUP_C_OPTIONAL
FEEDBACK_CONTROL_FIELDS = {"image_id", "filename", "event_timestamp"}
ALLOWED_FEEDBACK_FIELDS = GROUP_C_FIELDS | OPTIONAL_GROUP_C_FIELDS | FEEDBACK_CONTROL_FIELDS
OBSOLETE_LIVE_FIELDS = {"brain_initial_score"}
USABLE_BASE_EVENT_TYPES = {"pre_eval", "final_eval"}


class StructuredApplyFeedbackError(Exception):
    def __init__(self, message: str, detail: dict):
        super().__init__(message)
        self.detail = detail


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON: {e}") from e


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}: line {line_num}: invalid JSON: {e}") from e
            if not isinstance(row, dict):
                raise ValueError(f"{path}: line {line_num}: expected JSON object")
            rows.append(row)
    return rows


def parse_timestamp(value):
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def latest_rows_by_image(rows: list[dict]) -> dict[str, dict]:
    latest = {}
    for index, row in enumerate(rows):
        if row.get("event_type") not in USABLE_BASE_EVENT_TYPES:
            continue
        image_id = row.get("image_id")
        if not isinstance(image_id, str):
            continue
        key = (parse_timestamp(row.get("event_timestamp")), index)
        current = latest.get(image_id)
        if current is None or key > current[0]:
            latest[image_id] = (key, row)
    return {image_id: row for image_id, (_, row) in latest.items()}


def normalize_feedback_payload(payload) -> list[dict]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("feedback"), list):
            records = payload["feedback"]
        elif isinstance(payload.get("records"), list):
            records = payload["records"]
        else:
            records = [payload]
    else:
        raise ValueError("pending feedback must be a JSON object, an array, or an object with feedback[]")

    normalized = []
    for index, item in enumerate(records, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"feedback item {index}: expected object")
        unknown = sorted(set(item) - ALLOWED_FEEDBACK_FIELDS)
        if unknown:
            raise ValueError(f"feedback item {index}: unknown field(s): {', '.join(unknown)}")
        if not isinstance(item.get("image_id"), str) or not item["image_id"]:
            raise ValueError(f"feedback item {index}: image_id is required")
        normalized.append(dict(item))
    return normalized


def normalize_tags(value):
    if isinstance(value, list):
        if not all(isinstance(tag, str) for tag in value):
            raise ValueError("feedback_tags list must contain only strings")
        return ", ".join(tag.strip() for tag in value if tag.strip())
    return value


def is_scene_fit_value(value) -> bool:
    return value is True or value is False or value == "n-a"


def validate_feedback_item(item: dict, index: int):
    if "aaron_score" in item:
        score = item["aaron_score"]
        if not (isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 10):
            raise ValueError(f"feedback item {index}: aaron_score must be an integer in [0, 10]")

    if "quality_tier" in item and item["quality_tier"] not in QUALITY_TIERS:
        raise ValueError(f"feedback item {index}: quality_tier must be one of {sorted(QUALITY_TIERS)}")

    if "world_state" in item and item["world_state"] not in WORLD_STATES:
        raise ValueError(f"feedback item {index}: world_state must be one of {sorted(WORLD_STATES)}")

    if "tone" in item and item["tone"] not in TONES:
        raise ValueError(f"feedback item {index}: tone must be one of {sorted(TONES)}")

    if "fits_current_scene" in item and not is_scene_fit_value(item["fits_current_scene"]):
        raise ValueError(f"feedback item {index}: fits_current_scene must be true, false, or 'n-a'")

    if "failure_mode" in item and item["failure_mode"] is not None and item["failure_mode"] not in FAILURE_MODES:
        raise ValueError(f"feedback item {index}: failure_mode must be one of {sorted(FAILURE_MODES)} or null")

    if "anchor_promotion" in item and item["anchor_promotion"] not in ANCHOR_PROMOTIONS:
        raise ValueError(f"feedback item {index}: anchor_promotion must be one of {sorted(ANCHOR_PROMOTIONS)}")

    if "canon_candidate" in item and not isinstance(item["canon_candidate"], bool):
        raise ValueError(f"feedback item {index}: canon_candidate must be boolean")

    if "aaron_perception_corrections" in item:
        corrections = item["aaron_perception_corrections"]
        if not isinstance(corrections, list) or not all(isinstance(v, str) for v in corrections):
            raise ValueError(f"feedback item {index}: aaron_perception_corrections must be a list of strings")


def reject_obsolete_fields(record: dict, context: str):
    present = sorted(OBSOLETE_LIVE_FIELDS & set(record))
    if present:
        raise ValueError(f"{context}: obsolete live field(s) present: {', '.join(present)}")


def build_final_eval_record(base: dict, feedback: dict, index: int) -> tuple[dict, list[str]]:
    reject_obsolete_fields(base, f"base row for {feedback['image_id']}")

    item = dict(feedback)
    item["feedback_tags"] = normalize_tags(item.get("feedback_tags", ""))
    validate_feedback_item(item, index)
    warnings = []

    timestamp = item.get("event_timestamp") or now_iso()
    final_timestamp = item.get("final_eval_timestamp") or timestamp

    merged = dict(base)
    for field in GROUP_C_FIELDS | OPTIONAL_GROUP_C_FIELDS:
        if field in item:
            merged[field] = item[field]

    merged["event_type"] = "final_eval"
    merged["review_status"] = "confirmed"
    merged["event_timestamp"] = timestamp
    merged["final_eval_timestamp"] = final_timestamp

    if "feedback_text" not in merged:
        merged["feedback_text"] = ""
        warnings.append(f"feedback item {index}: feedback_text missing; wrote empty string per schema")
    if "feedback_tags" not in merged:
        merged["feedback_tags"] = ""
    if not isinstance(merged.get("final_notes"), str) or not merged["final_notes"]:
        raise ValueError(f"feedback item {index}: final_notes is required and must be a non-empty string")

    reject_obsolete_fields(merged, f"feedback row for {feedback['image_id']}")
    result = validate_record(merged, "final_eval")
    if not result["ok"]:
        raise ValueError(
            f"feedback item {index}: merged final_eval row failed validation: "
            f"{json.dumps(result['errors'], sort_keys=True)}"
        )
    return merged, warnings


def feedback_key(record: dict) -> tuple[str, str]:
    return (record.get("image_id"), record.get("final_eval_timestamp"))


def existing_feedback_keys(rows: list[dict]) -> set[tuple[str, str]]:
    keys = set()
    for row in rows:
        image_id = row.get("image_id")
        final_timestamp = row.get("final_eval_timestamp")
        if isinstance(image_id, str) and isinstance(final_timestamp, str):
            keys.add((image_id, final_timestamp))
    return keys


def feedback_content(record: dict) -> dict:
    fields = (GROUP_C_FIELDS | OPTIONAL_GROUP_C_FIELDS) - {"final_eval_timestamp"}
    return {field: record.get(field) for field in sorted(fields)}


def existing_feedback_content(rows: list[dict]) -> set[tuple[str, str]]:
    fingerprints = set()
    for row in rows:
        image_id = row.get("image_id")
        if row.get("event_type") != "final_eval" or not isinstance(image_id, str):
            continue
        fingerprints.add((image_id, json.dumps(feedback_content(row), sort_keys=True, separators=(",", ":"))))
    return fingerprints


def split_new_rows(rows: list[dict], existing_logs: dict[str, list[dict]]) -> tuple[list[dict], list[str]]:
    existing_keys = {name: existing_feedback_keys(log_rows) for name, log_rows in existing_logs.items()}
    existing_fingerprints = {
        name: existing_feedback_content(log_rows)
        for name, log_rows in existing_logs.items()
    }

    new_rows = []
    skipped = []
    new_keys = set()
    new_fingerprints = set()
    for row in rows:
        key = feedback_key(row)
        fingerprint = (row["image_id"], json.dumps(feedback_content(row), sort_keys=True, separators=(",", ":")))
        if key in new_keys or fingerprint in new_fingerprints:
            skipped.append(row["image_id"])
            continue

        seen_by = [
            name for name in existing_logs
            if key in existing_keys[name] or fingerprint in existing_fingerprints[name]
        ]
        if seen_by:
            if len(seen_by) != len(existing_logs):
                missing = sorted(set(existing_logs) - set(seen_by))
                raise ValueError(
                    f"partial duplicate state for image_id {row['image_id']!r}; "
                    f"matching feedback exists in {sorted(seen_by)} but is missing from {missing}; "
                    "manual repair required"
                )
            skipped.append(row["image_id"])
            continue
        new_keys.add(key)
        new_fingerprints.add(fingerprint)
        new_rows.append(row)
    return new_rows, skipped


def infer_job_id(record: dict) -> str | None:
    job_id = record.get("job_id")
    if isinstance(job_id, str) and job_id:
        return job_id
    source_path = str(record.get("source_path", ""))
    marker = "job-"
    start = source_path.find(marker)
    if start == -1:
        return None
    tail = source_path[start:]
    return tail.split("/", 1)[0] or None


def recovery_commands(records: list[dict]) -> list[str]:
    job_ids = sorted({job_id for row in records if (job_id := infer_job_id(row))})
    return [
        f"python3 benchmark/scripts/promote_generated_anchors.py --job-id {job_id}"
        for job_id in job_ids
    ]


def failed_image_ids(result: dict) -> list[str]:
    ids = []
    for item in result.get("results", []):
        if not item.get("ok") and item.get("image_id"):
            ids.append(item["image_id"])
    return ids


def append_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def flat_chroma_metadata(record: dict) -> dict:
    fields = [
        "aaron_score",
        "quality_tier",
        "world_state",
        "tone",
        "fits_current_scene",
        "failure_mode",
        "feedback_tags",
        "feedback_text",
        "anchor_promotion",
        "canon_candidate",
        "final_notes",
        "final_eval_timestamp",
        "review_status",
    ]
    metadata = {}
    for field in fields:
        value = record.get(field)
        if value is None:
            metadata[field] = ""
        elif isinstance(value, (str, int, float, bool)):
            metadata[field] = value
        else:
            metadata[field] = json.dumps(value, sort_keys=True)
    return metadata


def update_existing_chroma_metadata(collection, records: list[dict]) -> dict:
    ids = [record["image_id"] for record in records]
    v11_ids = [
        record_id
        for image_id in ids
        for record_id in (f"{image_id}::image", f"{image_id}::search_text")
    ]
    existing_payload = collection.get(ids=ids + v11_ids, include=["metadatas"])
    existing_ids = set(existing_payload.get("ids", []))
    missing_ids = [image_id for image_id in ids if image_id not in existing_ids]
    v11_existing_ids = sorted(record_id for record_id in existing_ids if "::" in record_id)
    updated_ids = []
    for record in records:
        image_id = record["image_id"]
        if image_id not in existing_ids:
            continue
        collection.update(
            ids=[image_id],
            metadatas=[flat_chroma_metadata(record)],
        )
        updated_ids.append(image_id)
    return {
        "attempted": True,
        "updated": len(updated_ids),
        "matched_existing": len(updated_ids),
        "missing_ids": missing_ids,
        "updated_ids": updated_ids,
        "v1_1_records_detected": len(v11_existing_ids),
        "v1_1_record_ids": v11_existing_ids,
        "v1_1_search_index_version": SEARCH_INDEX_VERSION,
        "v1_1_rebuild_required": bool(v11_existing_ids),
        "v1_1_rebuild_commands": [
            f"python3 benchmark/scripts/rebuild_taste_memory_index.py --apply --job-id {job_id}"
            for job_id in sorted(filter(None, (infer_job_id(row) for row in records)))
        ],
    }


def update_chroma_metadata(records: list[dict], chroma_path: Path, collection_name: str) -> dict:
    try:
        import chromadb
    except ImportError as e:
        raise RuntimeError("chromadb not installed; use --skip-chroma only for isolated sample tests") from e

    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_collection(collection_name)
    result = update_existing_chroma_metadata(collection, records)
    result["collection"] = collection_name
    return result


def main():
    vault_root = default_vault_root()
    parser = argparse.ArgumentParser(description="Apply confirmed structured feedback as append-only latest rows.")
    parser.add_argument("pending_feedback", type=Path, help="Path to pending-feedback.json")
    parser.add_argument(
        "--generations-log",
        type=Path,
        default=vault_root / "benchmark" / "logs" / "generations.jsonl",
        help="Path to generations.jsonl",
    )
    parser.add_argument(
        "--feedback-log",
        type=Path,
        default=vault_root / "benchmark" / "logs" / "feedback.jsonl",
        help="Path to feedback.jsonl",
    )
    parser.add_argument(
        "--final-eval-log",
        type=Path,
        default=vault_root / "benchmark" / "logs" / "final_eval_history.jsonl",
        help="Path to final_eval_history.jsonl",
    )
    parser.add_argument(
        "--chroma-path",
        type=Path,
        default=vault_root / "benchmark" / "chroma_data",
        help="Path to Chroma persistent data",
    )
    parser.add_argument("--collection", default="taste_memory", help="Chroma collection to update")
    parser.add_argument("--skip-chroma", action="store_true", help="Skip Chroma metadata update")
    parser.add_argument(
        "--skip-anchor-promotion",
        action="store_true",
        help="Skip generated visual-anchor materialization. Intended only for isolated tests.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and print summary without appending")
    args = parser.parse_args()

    try:
        feedback_records = normalize_feedback_payload(load_json(args.pending_feedback))
        generations = load_jsonl(args.generations_log)
        feedback_log_rows = load_jsonl(args.feedback_log)
        final_eval_log_rows = load_jsonl(args.final_eval_log)
        latest = latest_rows_by_image(generations)
        candidate_rows = []
        warnings = []
        for index, item in enumerate(feedback_records, start=1):
            image_id = item["image_id"]
            base = latest.get(image_id)
            if base is None:
                raise ValueError(
                    f"feedback item {index}: no usable pre_eval/final_eval generation row found for image_id {image_id!r}"
                )
            row, row_warnings = build_final_eval_record(base, item, index)
            candidate_rows.append(row)
            warnings.extend(row_warnings)
        output_rows, skipped_duplicates = split_new_rows(candidate_rows, {
            "feedback_log": feedback_log_rows,
            "final_eval_log": final_eval_log_rows,
            "generations_log": generations,
        })

        preflight_result = {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "would_promote": 0,
            "candidate_count": sum(1 for row in candidate_rows if row.get("anchor_promotion") in PROMOTED_VALUES),
            "reason": "not run",
            "results": [],
        }
        if not args.skip_anchor_promotion and not args.dry_run:
            preflight_result = preflight_records(candidate_rows, vault_root=vault_root)
            if preflight_result.get("failed"):
                raise StructuredApplyFeedbackError(
                    "anchor promotion preflight failed; no JSONL rows were appended",
                    {
                        "stage": "anchor_promotion_preflight",
                        "failed_image_ids": failed_image_ids(preflight_result),
                        "recovery_commands": recovery_commands(candidate_rows),
                        "anchor_promotions": preflight_result,
                    },
                )

        if args.dry_run:
            chroma_result = {"attempted": False, "updated": 0, "reason": "dry run"}
            anchor_promotion_result = {
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "would_promote": 0,
                "candidate_count": sum(1 for row in candidate_rows if row.get("anchor_promotion") in PROMOTED_VALUES),
                "reason": "dry run",
                "results": [],
            }
        else:
            if args.skip_chroma:
                chroma_result = {"attempted": False, "updated": 0, "reason": "skipped by --skip-chroma"}
            elif not output_rows:
                chroma_result = {"attempted": False, "updated": 0, "reason": "no new rows"}
            else:
                chroma_result = update_chroma_metadata(output_rows, args.chroma_path, args.collection)
                missing_ids = chroma_result.get("missing_ids") or []
                if missing_ids:
                    warnings.append(
                        f"{args.collection} metadata update skipped missing ids: {', '.join(missing_ids)}"
                    )
                if chroma_result.get("v1_1_rebuild_required"):
                    commands = chroma_result.get("v1_1_rebuild_commands") or [
                        "python3 benchmark/scripts/rebuild_taste_memory_index.py --apply --job-id <job_id>"
                    ]
                    warnings.append(
                        "V1.1 taste_memory records use image/search_text modality ids; "
                        "run rebuild after feedback so search_text documents and both embeddings stay fresh: "
                        + "; ".join(commands)
                    )
            append_jsonl(args.feedback_log, output_rows)
            append_jsonl(args.final_eval_log, output_rows)
            append_jsonl(args.generations_log, output_rows)
            if args.skip_anchor_promotion:
                anchor_promotion_result = {
                    "attempted": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "skipped": 0,
                    "would_promote": 0,
                    "candidate_count": sum(1 for row in candidate_rows if row.get("anchor_promotion") in PROMOTED_VALUES),
                    "reason": "skipped by --skip-anchor-promotion",
                    "results": [],
                }
            else:
                anchor_promotion_result = promote_records(candidate_rows, vault_root=vault_root)
                if anchor_promotion_result.get("failed"):
                    commands = recovery_commands(candidate_rows)
                    command_text = "; ".join(commands) if commands else (
                        "python3 benchmark/scripts/promote_generated_anchors.py --job-id <job_id>"
                    )
                    raise StructuredApplyFeedbackError(
                        f"anchor promotion failed after feedback append; recover with: {command_text}",
                        {
                            "stage": "anchor_promotion_after_append",
                            "failed_image_ids": failed_image_ids(anchor_promotion_result),
                            "recovery_commands": commands,
                            "anchor_promotions": anchor_promotion_result,
                        },
                    )

        print(json.dumps({
            "ok": True,
            "feedback_applied": len(output_rows),
            "duplicates_skipped": len(skipped_duplicates),
            "generations_appended": 0 if args.dry_run else len(output_rows),
            "feedback_log_appended": 0 if args.dry_run else len(output_rows),
            "final_eval_log_appended": 0 if args.dry_run else len(output_rows),
            "image_ids": [row["image_id"] for row in output_rows],
            "skipped_duplicate_image_ids": skipped_duplicates,
            "warnings": warnings,
            "chroma": chroma_result,
            "anchor_promotion_preflight": preflight_result,
            "anchor_promotions": anchor_promotion_result,
        }, indent=2, sort_keys=True))
    except Exception as e:
        payload = {"ok": False, "error": str(e)}
        if isinstance(e, StructuredApplyFeedbackError):
            payload.update(e.detail)
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
