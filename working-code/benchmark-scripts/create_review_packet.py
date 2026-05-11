"""Create a visual review packet for a completed generation job.

Inputs can be either:
    1. a Flow Arm handoff result manifest (`handoff-result.v1`), or
    2. `benchmark/logs/generations.jsonl` after `ingest_batch.py` has written
       generation rows.

The output is a file-backed packet at `reviews/visual/jobs/<job_id>/`:
    - `review-manifest.json`
    - `aaron-feedback-worksheet.md`
    - copied image files under `images/`

No contact sheets are generated. The manifest keeps enough lineage for
feedback application and lightbox rendering without inventing new evaluation
schema fields. The worksheet is the human-editable review surface for Aaron.
"""

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

COMPATIBLE_EVAL_SCHEMA_VERSION = "v1"
REVIEW_PACKET_SCHEMA_VERSION = "review-packet.v1"
RESULT_MANIFEST_SCHEMA_VERSION = "handoff-result.v1"
DEFAULT_GENERATIONS_LOG = Path("benchmark/logs/generations.jsonl")
DEFAULT_OUTPUT_ROOT = Path("reviews/visual/jobs")
WORKSHEET_FILENAME = "aaron-feedback-worksheet.md"

REVIEW_ITEM_REQUIRED_FIELDS = {
    "packet_item_type",
    "packet_review_status",
    "image_id",
    "filename",
    "source_path",
    "review_image_path",
    "image_origin",
    "created_by",
    "asset_event_timestamp",
    "job_id",
    "intent_id",
    "prompt_id",
    "target_id",
    "asset_id",
    "output_index",
    "model",
    "model_version",
    "platform",
    "generation_model",
    "rendered_prompt",
    "original_file_path",
    "brain_initial_score_raw",
    "brain_initial_gold_similarity",
    "brain_initial_anti_similarity",
    "brain_initial_rank",
}

BRAIN_SCORE_FIELDS = {
    "brain_initial_score_raw",
    "brain_initial_gold_similarity",
    "brain_initial_anti_similarity",
    "brain_initial_rank",
}


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path):
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path}: {e}") from e


def read_jsonl(path):
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
                raise ValueError(f"invalid JSONL in {path} line {line_num}: {e}") from e
            rows.append(row)
    return rows


def image_id_from_file(path, declared_sha256=None):
    digest = declared_sha256
    if not digest and path.exists() and path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest:
        return f"sha256:{digest[:16]}"
    fallback = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return f"sha256:{fallback[:16]}"


def safe_name(value):
    allowed = []
    for char in str(value):
        if char.isalnum() or char in {"-", "_", "."}:
            allowed.append(char)
        else:
            allowed.append("-")
    cleaned = "".join(allowed).strip(".-")
    return cleaned or "image"


def infer_handoff_root(manifest_path, output_root):
    parts = Path(output_root).parts
    manifest_parent = manifest_path.parent
    parent_parts = manifest_parent.parts
    if len(parent_parts) >= len(parts) and parent_parts[-len(parts):] == parts:
        root_parts = parent_parts[:-len(parts)]
        if root_parts:
            return Path(*root_parts)
    return manifest_parent


def resolve_asset_path(asset_file_path, manifest_path, output_root=None):
    raw = Path(asset_file_path)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(Path.cwd() / raw)
        if output_root:
            handoff_root = infer_handoff_root(manifest_path, output_root)
            candidates.append(handoff_root / raw)
        candidates.append(manifest_path.parent / raw.name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return candidates[0].resolve()


def flatten_result_manifest(manifest, manifest_path):
    if manifest.get("schema_version") != RESULT_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"result manifest schema_version must be {RESULT_MANIFEST_SCHEMA_VERSION!r}; "
            f"got {manifest.get('schema_version')!r}"
        )

    job_id = manifest.get("job_id")
    intent_id = manifest.get("intent_id")
    output_root = manifest.get("output_root")
    source_result_created_at = manifest.get("created_at")
    rows = []

    for prompt in manifest.get("prompts_completed", []):
        prompt_id = prompt.get("prompt_id")
        for target in prompt.get("targets_completed", []):
            for asset in target.get("assets", []):
                source_path = resolve_asset_path(asset.get("file_path", ""), manifest_path, output_root)
                image_id = image_id_from_file(source_path, asset.get("sha256"))
                event_timestamp = asset.get("event_timestamp") or manifest.get("completed_at") or utc_now()
                row = {
                    "packet_item_type": "generated_asset",
                    "packet_review_status": "pending",
                    "image_id": image_id,
                    "filename": source_path.name,
                    "source_path": asset.get("file_path"),
                    "file_path": asset.get("file_path"),
                    "_resolved_source_path": str(source_path),
                    "image_origin": asset.get("image_origin") or "generation",
                    "created_by": target.get("created_by") or "unknown",
                    "asset_event_timestamp": event_timestamp,
                    "source_result_created_at": source_result_created_at,
                    "job_id": job_id,
                    "intent_id": intent_id,
                    "prompt_id": prompt_id,
                    "target_id": target.get("target_id"),
                    "asset_id": asset.get("asset_id"),
                    "output_index": asset.get("output_index"),
                    "base_concept": prompt.get("base_concept"),
                    "world_state": prompt.get("world_state"),
                    "tone": prompt.get("tone"),
                    "model": target.get("model"),
                    "model_version": target.get("model_version"),
                    "platform": target.get("platform"),
                    "generation_model": target.get("generation_model") or target.get("model"),
                    "rendered_prompt": target.get("rendered_prompt"),
                    "mime_type": asset.get("mime_type"),
                    "width": asset.get("width"),
                    "height": asset.get("height"),
                    "sha256": asset.get("sha256"),
                    "brain_initial_score_raw": None,
                    "brain_initial_gold_similarity": None,
                    "brain_initial_anti_similarity": None,
                    "brain_initial_rank": None,
                }
                rows.append(row)
    return rows


def latest_rows_for_job(rows, job_id):
    latest = {}
    for index, row in enumerate(rows):
        if row.get("job_id") != job_id:
            continue
        image_id = row.get("image_id")
        if not image_id:
            continue
        latest[image_id] = (index, row)
    return [row for _, row in sorted(latest.values(), key=lambda pair: pair[0])]


def rows_from_generations_log(job_id, generations_log):
    rows = latest_rows_for_job(read_jsonl(generations_log), job_id)
    if not rows:
        raise ValueError(f"no rows found for job_id={job_id!r} in {generations_log}")
    return rows


def source_path_for_row(row):
    for key in ("_resolved_source_path", "source_path", "file_path", "original_file_path"):
        value = row.get(key)
        if value:
            path = Path(value)
            if not path.is_absolute():
                path = Path.cwd() / path
            return path.resolve()
    raise ValueError(f"row for image_id={row.get('image_id')!r} has no source_path/file_path")


def copy_image(row, images_dir):
    source = source_path_for_row(row)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"image source not found for {row.get('image_id')}: {source}")

    asset_id = row.get("asset_id") or row.get("image_id") or source.stem
    suffix = source.suffix or ".png"
    dest_name = f"{safe_name(asset_id)}{suffix}"
    dest = images_dir / dest_name
    shutil.copy2(source, dest)
    return dest


def build_review_item(row, review_job_dir, images_dir):
    original_source = source_path_for_row(row)
    copied = copy_image(row, images_dir)
    relative_image_path = copied.relative_to(review_job_dir).as_posix()
    item = dict(row)
    item["source_path"] = row.get("source_path") or row.get("file_path")
    item["asset_event_timestamp"] = row.get("asset_event_timestamp") or row.get("event_timestamp")
    item["packet_item_type"] = row.get("packet_item_type") or "generated_asset"
    item["packet_review_status"] = row.get("packet_review_status") or row.get("review_status") or "pending"
    for borrowed_key in (
        "_resolved_source_path",
        "file_path",
        "schema_version",
        "session_id",
        "event_type",
        "review_status",
        "event_timestamp",
    ):
        item.pop(borrowed_key, None)
    item["review_image_path"] = relative_image_path
    item["original_file_path"] = str(original_source)
    item["schema_field_check"] = schema_field_check(item)
    return item


def schema_field_check(item):
    missing = sorted(field for field in REVIEW_ITEM_REQUIRED_FIELDS if field not in item)
    score_fields_present = sorted(field for field in BRAIN_SCORE_FIELDS if field in item)
    return {
        "required_review_item_fields_present": not missing,
        "missing_required_review_item_fields": missing,
        "score_fields_present": score_fields_present,
    }


def build_manifest(job_id, rows, source_type, source_path, output_root, overwrite=False):
    review_job_dir = output_root / job_id
    images_dir = review_job_dir / "images"
    if images_dir.exists() and overwrite:
        shutil.rmtree(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    items = [build_review_item(row, review_job_dir, images_dir) for row in rows]
    counts = Counter(item.get("packet_review_status") or "unknown" for item in items)
    missing_by_image = {
        item["image_id"]: item["schema_field_check"]["missing_required_review_item_fields"]
        for item in items
        if item["schema_field_check"]["missing_required_review_item_fields"]
    }

    manifest = {
        "schema_version": REVIEW_PACKET_SCHEMA_VERSION,
        "compatible_eval_schema_version": COMPATIBLE_EVAL_SCHEMA_VERSION,
        "manifest_type": "series_visual_review_packet",
        "job_id": job_id,
        "intent_id": first_non_empty(row.get("intent_id") for row in rows),
        "created_at": utc_now(),
        "source_type": source_type,
        "source_path": str(source_path) if source_path else None,
        "image_count": len(items),
        "image_dir": "images",
        "packet_review_status_counts": dict(sorted(counts.items())),
        "schema_field_summary": {
            "required_review_item_fields_present": not missing_by_image,
            "missing_by_image": missing_by_image,
            "uses_reconciled_score_fields": all(
                BRAIN_SCORE_FIELDS.issubset(set(item["schema_field_check"]["score_fields_present"]))
                for item in items
            ),
        },
        "items": items,
    }

    output_path = review_job_dir / "review-manifest.json"
    output_path.write_text(json.dumps(manifest, indent=2) + "\n")
    worksheet_path = review_job_dir / WORKSHEET_FILENAME
    worksheet_path.write_text(render_feedback_worksheet(manifest))
    return output_path, worksheet_path, manifest


def render_feedback_worksheet(manifest):
    """Render Aaron's inline Markdown review worksheet.

    Image embeds intentionally use review-packet-relative paths such as
    `images/foo.jpeg`. Obsidian resolves those reliably when this worksheet is
    opened from the review job folder; absolute host paths are brittle across
    devices and vault mounts.
    """
    job_id = manifest.get("job_id", "unknown-job")
    lines = [
        f"# Aaron Feedback Worksheet - {job_id}",
        "",
        "Fill this in directly. The lightbox is for viewing; this worksheet is the inline review surface Brain should parse into pending feedback for `apply_feedback.py`.",
        "",
        "Recommended order for each image:",
        "1. Look at the image.",
        "2. Write your final label, score, and reason in the Aaron fields.",
        "3. Then compare against Brain's prediction/notes below and add a response if useful.",
        "",
        "Aaron only needs to fill the compact fields. Brain/parser expands this into the full structured feedback payload afterward.",
        "",
        "Label values: `none`, `gold`, `anti`, `aspirational`.",
        "",
    ]

    for index, item in enumerate(manifest.get("items", []), start=1):
        filename = item.get("filename", "image")
        review_image_path = item.get("review_image_path") or ""
        lines.extend([
            f"## {index}. {filename}",
            "",
            f"![{filename}]({review_image_path})",
            "",
            f"- Image ID: `{item.get('image_id')}`",
            f"- Prompt ID: `{item.get('prompt_id')}`",
            f"- Base concept: {item.get('base_concept') or ''}",
            f"- Rendered prompt: {item.get('rendered_prompt') or ''}",
            "",
            "Aaron final label: ",
            "",
            "Aaron score 0-10: ",
            "",
            "Aaron reason / why this label is right: ",
            "",
            ">",
            "",
            "Aaron response to Brain, optional:",
            "",
            ">",
            "",
            "Optional structured corrections, only if you care:",
            "- world_state override: ",
            "- tone override: ",
            "- scene fit override: ",
            "- failure mode override: ",
            "- canon candidate override: ",
            "- perception corrections: ",
            "",
            "Brain pre-eval:",
            f"- Promotion: `{item.get('brain_initial_anchor_promotion_recommendation')}`",
            f"- Quality tier: `{item.get('brain_initial_quality_tier')}`",
            f"- World state: `{item.get('brain_initial_world_state')}`",
            f"- Tone: `{item.get('brain_initial_tone')}`",
            f"- Scene fit: `{str(item.get('brain_initial_scene_fit')).lower()}`",
            f"- Failure mode: `{str(item.get('brain_initial_failure_mode')).lower()}`",
            f"- Score raw: `{item.get('brain_initial_score_raw')}`",
            f"- Gold similarity: `{item.get('brain_initial_gold_similarity')}`",
            f"- Anti similarity: `{item.get('brain_initial_anti_similarity')}`",
            f"- Tags: `{item.get('brain_initial_tags') or ''}`",
            f"- Notes: {item.get('brain_initial_notes') or ''}",
            "",
            "---",
            "",
        ])
    return "\n".join(lines)


def first_non_empty(values):
    for value in values:
        if value:
            return value
    return None


def load_rows(args):
    if args.result_manifest:
        manifest_path = Path(args.result_manifest)
        manifest = read_json(manifest_path)
        rows = flatten_result_manifest(manifest, manifest_path.resolve())
        source_job_id = manifest.get("job_id")
        if source_job_id and source_job_id != args.job_id:
            raise ValueError(f"job_id argument {args.job_id!r} does not match manifest job_id {source_job_id!r}")
        return rows, "result_manifest", manifest_path.resolve()

    generations_log = Path(args.generations_log)
    return rows_from_generations_log(args.job_id, generations_log), "generations_jsonl", generations_log.resolve()


def parse_args():
    parser = argparse.ArgumentParser(description="Create a visual review packet for a generation job.")
    parser.add_argument("job_id", help="Job ID to packetize")
    parser.add_argument(
        "--result-manifest",
        help="Flow Arm handoff result manifest. If omitted, reads --generations-log.",
    )
    parser.add_argument(
        "--generations-log",
        default=str(DEFAULT_GENERATIONS_LOG),
        help="JSONL generation log used when --result-manifest is omitted.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Review packet output root.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output images directory before writing the packet.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        rows, source_type, source_path = load_rows(args)
        if not rows:
            raise ValueError(f"no reviewable images found for job_id={args.job_id!r}")
        output_path, worksheet_path, manifest = build_manifest(
            args.job_id,
            rows,
            source_type,
            source_path,
            Path(args.output_root),
            overwrite=args.overwrite,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)

    result = {
        "ok": True,
        "job_id": args.job_id,
        "review_manifest_path": str(output_path),
        "feedback_worksheet_path": str(worksheet_path),
        "image_count": manifest["image_count"],
        "required_review_item_fields_present": manifest["schema_field_summary"][
            "required_review_item_fields_present"
        ],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
