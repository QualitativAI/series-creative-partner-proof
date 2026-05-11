"""Create a job-level alignment summary from generation and alignment logs.

The canonical per-image/session alignment log remains
`benchmark/logs/alignment.jsonl`. This script writes a job-facing summary for
visual review folders:

    reviews/visual/jobs/<job_id>/alignment-summary.md
    reviews/visual/jobs/<job_id>/alignment-metrics.json

It can run before Aaron feedback exists. In that case it records pending counts
and explicitly points to the canonical alignment log rather than fabricating
alignment scores.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import compute_alignment
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import compute_alignment  # noqa: E402


DEFAULT_VAULT_ROOT = Path("/workspace/series-vault")
if not DEFAULT_VAULT_ROOT.exists():
    DEFAULT_VAULT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_GENERATIONS_LOG = DEFAULT_VAULT_ROOT / "benchmark" / "logs" / "generations.jsonl"
DEFAULT_ALIGNMENT_LOG = DEFAULT_VAULT_ROOT / "benchmark" / "logs" / "alignment.jsonl"
DEFAULT_OUTPUT_ROOT = DEFAULT_VAULT_ROOT / "reviews" / "visual" / "jobs"
SCORE_FIELDS = (
    "brain_initial_score_raw",
    "brain_initial_gold_similarity",
    "brain_initial_anti_similarity",
    "brain_initial_rank",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def parse_timestamp(value: Any):
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def latest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = {}
    for index, row in enumerate(rows):
        image_id = row.get("image_id")
        if not isinstance(image_id, str):
            continue
        key = (parse_timestamp(row.get("event_timestamp")), index)
        if image_id not in latest or key > latest[image_id][0]:
            latest[image_id] = (key, row)
    return [row for _, row in latest.values()]


def job_rows(rows: list[dict[str, Any]], job_id: str, session_id: str | None) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("job_id") == job_id]
    if session_id:
        selected = [row for row in selected if row.get("session_id") == session_id]
    return selected


def matching_alignment_rows(
    rows: list[dict[str, Any]],
    image_ids: set[str],
    session_id: str | None,
) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("image_id") in image_ids]
    if session_id:
        selected = [row for row in selected if row.get("session_id") == session_id]
    return selected


def score_field_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {field: 0 for field in SCORE_FIELDS}
    taste_matches_raw = 0
    numeric_score_rows = 0
    numeric_raw_with_diagnostics = 0
    diagnostic_equation_passes = 0
    for row in rows:
        for field in SCORE_FIELDS:
            if row.get(field) is not None:
                counts[field] += 1
        raw = row.get("brain_initial_score_raw")
        taste = row.get("taste_alignment")
        gold = row.get("brain_initial_gold_similarity")
        anti = row.get("brain_initial_anti_similarity")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            numeric_score_rows += 1
            if raw == taste:
                taste_matches_raw += 1
            if isinstance(gold, (int, float)) and isinstance(anti, (int, float)):
                numeric_raw_with_diagnostics += 1
                if abs(raw - (gold - anti)) <= 1e-9:
                    diagnostic_equation_passes += 1
    return {
        "non_null_counts": counts,
        "numeric_score_rows": numeric_score_rows,
        "numeric_taste_alignment_matches_brain_initial_score_raw": taste_matches_raw,
        "numeric_raw_with_diagnostics": numeric_raw_with_diagnostics,
        "diagnostic_equation_passes": diagnostic_equation_passes,
        "semantic_rule": "brain_initial_score_raw = taste_alignment = brain_initial_gold_similarity - brain_initial_anti_similarity",
    }


def field_accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {
        "quality_tier": ("brain_initial_quality_tier", "quality_tier"),
        "anchor_promotion": ("brain_initial_anchor_promotion_recommendation", "anchor_promotion"),
        "world_state": ("brain_initial_world_state", "world_state"),
        "tone": ("brain_initial_tone", "tone"),
        "failure_mode": ("brain_initial_failure_mode", "failure_mode"),
    }
    summary = {}
    for label, (pred_field, actual_field) in fields.items():
        compared = 0
        exact = 0
        for row in rows:
            if pred_field not in row or actual_field not in row:
                continue
            compared += 1
            if row.get(pred_field) == row.get(actual_field):
                exact += 1
        summary[label] = {
            "compared": compared,
            "exact": exact,
            "accuracy": exact / compared if compared else None,
        }
    return summary


def generation_alignment_scores(reviewed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = []
    for row in reviewed_rows:
        missing = [
            field for field in (
                "brain_initial_quality_tier",
                "brain_initial_anchor_promotion_recommendation",
                "brain_initial_world_state",
                "brain_initial_tone",
                "brain_initial_failure_mode",
                "brain_initial_tags",
                "quality_tier",
                "anchor_promotion",
                "world_state",
                "tone",
                "failure_mode",
                "feedback_tags",
            )
            if field not in row
        ]
        if missing:
            continue
        score, breakdown = compute_alignment.compute_score(row, row)
        scores.append({
            "image_id": row.get("image_id"),
            "filename": row.get("filename"),
            "alignment_score": score,
            "alignment_breakdown": breakdown,
        })
    return scores


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_metrics(job_id: str, session_id: str | None, generation_rows: list[dict[str, Any]], alignment_rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest = latest_rows(generation_rows)
    reviewed = [
        row for row in latest
        if row.get("event_type") == "final_eval" and row.get("review_status") == "confirmed"
    ]
    pending = [row for row in latest if row not in reviewed]
    reviewed_with_brain_fields = [
        row for row in reviewed
        if all(
            field in row
            for field in (
                "brain_initial_quality_tier",
                "brain_initial_anchor_promotion_recommendation",
                "brain_initial_world_state",
                "brain_initial_tone",
                "brain_initial_failure_mode",
                "brain_initial_tags",
            )
        )
    ]
    computed_scores = generation_alignment_scores(reviewed_with_brain_fields)
    canonical_scores = [
        row.get("alignment_score") for row in alignment_rows
        if isinstance(row.get("alignment_score"), (int, float)) and not isinstance(row.get("alignment_score"), bool)
    ]
    status_counts = Counter(str(row.get("review_status")) for row in latest)
    model_counts = Counter(str(row.get("generation_model") or row.get("model") or "unknown") for row in latest)
    phase_counts = Counter(str(row.get("alignment_phase")) for row in alignment_rows)

    return {
        "ok": True,
        "job_id": job_id,
        "session_id": session_id,
        "created_at": utc_now(),
        "generation_rows_for_job": len(generation_rows),
        "latest_image_count": len(latest),
        "reviewed_image_count": len(reviewed),
        "pending_image_count": len(pending),
        "review_status_counts": dict(sorted(status_counts.items())),
        "generation_model_counts": dict(sorted(model_counts.items())),
        "score_fields": score_field_summary(latest),
        "computed_from_generations": {
            "reviewed_rows_with_brain_pre_eval": len(reviewed_with_brain_fields),
            "reviewed_rows_compared": len(computed_scores),
            "mean_alignment_score": mean([item["alignment_score"] for item in computed_scores]),
            "field_accuracy": field_accuracy(reviewed),
            "per_image": computed_scores,
        },
        "canonical_alignment": {
            "log_path": str(DEFAULT_ALIGNMENT_LOG),
            "matching_rows": len(alignment_rows),
            "mean_alignment_score": mean(canonical_scores),
            "phase_counts": dict(sorted(phase_counts.items())),
        },
        "image_ids": [row.get("image_id") for row in latest],
    }


def write_summary(path: Path, metrics: dict[str, Any]):
    lines = [
        f"# Alignment Summary - {metrics['job_id']}",
        "",
        f"- Created: {metrics['created_at']}",
        f"- Session filter: {metrics['session_id'] or 'all sessions for job'}",
        f"- Latest images: {metrics['latest_image_count']}",
        f"- Reviewed images: {metrics['reviewed_image_count']}",
        f"- Pending images: {metrics['pending_image_count']}",
        f"- Canonical alignment log: `{metrics['canonical_alignment']['log_path']}`",
        f"- Canonical matching rows: {metrics['canonical_alignment']['matching_rows']}",
        f"- Canonical mean alignment: {format_metric(metrics['canonical_alignment']['mean_alignment_score'])}",
        f"- Job mean alignment from reviewed generation rows: {format_metric(metrics['computed_from_generations']['mean_alignment_score'])}",
        "",
        "## Score Semantics",
        "",
        f"`{metrics['score_fields']['semantic_rule']}`",
        "",
        f"- Numeric score rows: {metrics['score_fields']['numeric_score_rows']}",
        f"- Numeric rows where `taste_alignment` matches `brain_initial_score_raw`: {metrics['score_fields']['numeric_taste_alignment_matches_brain_initial_score_raw']}",
        f"- Numeric score rows with gold/anti diagnostics: {metrics['score_fields']['numeric_raw_with_diagnostics']}",
        f"- Diagnostic equation passes: {metrics['score_fields']['diagnostic_equation_passes']}",
        "",
        "## Review Status Counts",
        "",
    ]
    for key, value in metrics["review_status_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Model Counts", ""])
    for key, value in metrics["generation_model_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Field Accuracy", ""])
    for key, item in metrics["computed_from_generations"]["field_accuracy"].items():
        lines.append(f"- {key}: {item['exact']}/{item['compared']} exact ({format_metric(item['accuracy'])})")
    lines.append("")
    path.write_text("\n".join(lines))


def format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.4f}"
    return str(value)


def create_summary(
    job_id: str,
    session_id: str | None = None,
    generations_log: Path = DEFAULT_GENERATIONS_LOG,
    alignment_log: Path = DEFAULT_ALIGNMENT_LOG,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    all_generation_rows = read_jsonl(generations_log)
    selected_generation_rows = job_rows(all_generation_rows, job_id, session_id)
    if not selected_generation_rows:
        raise ValueError(f"no generation rows found for job_id={job_id!r}")
    image_ids = {row["image_id"] for row in selected_generation_rows if isinstance(row.get("image_id"), str)}
    all_alignment_rows = read_jsonl(alignment_log)
    selected_alignment_rows = matching_alignment_rows(all_alignment_rows, image_ids, session_id)
    metrics = build_metrics(job_id, session_id, selected_generation_rows, selected_alignment_rows)

    job_dir = output_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = job_dir / "alignment-metrics.json"
    summary_path = job_dir / "alignment-summary.md"
    metrics["canonical_alignment"]["log_path"] = str(alignment_log)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    write_summary(summary_path, metrics)
    return {
        "ok": True,
        "job_id": job_id,
        "summary_path": str(summary_path),
        "metrics_path": str(metrics_path),
        "latest_image_count": metrics["latest_image_count"],
        "reviewed_image_count": metrics["reviewed_image_count"],
        "canonical_alignment_rows": metrics["canonical_alignment"]["matching_rows"],
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Create a job-level alignment summary.")
    parser.add_argument("job_id")
    parser.add_argument("--session-id", help="Optional session_id filter.")
    parser.add_argument("--generations-log", type=Path, default=DEFAULT_GENERATIONS_LOG)
    parser.add_argument("--alignment-log", type=Path, default=DEFAULT_ALIGNMENT_LOG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = create_summary(
            job_id=args.job_id,
            session_id=args.session_id,
            generations_log=args.generations_log,
            alignment_log=args.alignment_log,
            output_root=args.output_root,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
