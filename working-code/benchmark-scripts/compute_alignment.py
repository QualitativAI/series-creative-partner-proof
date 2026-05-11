"""compute_alignment.py - join pre_eval and final_eval logs into alignment rows.

V1 alignment compares Brain's pre-eval fields with Aaron's confirmed final
fields, writes benchmark/logs/alignment.jsonl, and renders:
- benchmark/charts/alignment_score_by_session.png
- benchmark/charts/promotion_precision_recall.png

Holdout benchmark rows intentionally use a cross-session join: every
holdout_benchmark pre_eval row joins to the latest confirmed final_eval row for
the same image_id, regardless of session_id. Non-holdout rows join by
(image_id, session_id). Rows with no confirmed final_eval are skipped and
reported.
"""

import argparse
import json
import os
import struct
import sys
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import validate_eval
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import validate_eval  # noqa: E402

SCHEMA_VERSION = "v1"
WEIGHTING_VERSION = "v1"

DEFAULT_VAULT_ROOT = Path("/workspace/series-vault")
if not DEFAULT_VAULT_ROOT.exists():
    DEFAULT_VAULT_ROOT = Path(__file__).resolve().parents[2]

LOGS_DIR = DEFAULT_VAULT_ROOT / "benchmark" / "logs"
CHARTS_DIR = DEFAULT_VAULT_ROOT / "benchmark" / "charts"
PRE_EVAL_LOG = LOGS_DIR / "pre_eval_history.jsonl"
FINAL_EVAL_LOG = LOGS_DIR / "final_eval_history.jsonl"
ALIGNMENT_LOG = LOGS_DIR / "alignment.jsonl"
ALIGNMENT_CHART = CHARTS_DIR / "alignment_score_by_session.png"
PROMOTION_CHART = CHARTS_DIR / "promotion_precision_recall.png"

QUALITY_ORDER = ["bad", "okay", "great", "aspirational", "approved", "canon"]
WEIGHTS = {
    "quality_tier": 0.30,
    "anchor_promotion": 0.25,
    "world_state": 0.20,
    "tone": 0.10,
    "failure_mode": 0.10,
    "tags": 0.05,
}
PROMOTION_LABELS = ["gold", "anti", "aspirational"]
EXTERNAL_HOLDOUT_WEIGHTING_VERSION = "v1-promotion-only"


def parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def read_jsonl(path: Path):
    rows = []
    malformed = 0
    if not path.exists():
        return rows, malformed
    with path.open() as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                malformed += 1
                print(f"WARNING: {path.name}:{line_num} invalid JSON: {e}", file=sys.stderr)
    return rows, malformed


def latest_by_timestamp(rows):
    latest = {}
    for row in rows:
        ts = parse_timestamp(row.get("final_eval_timestamp") or row.get("event_timestamp"))
        if ts is None:
            continue
        key = row["image_id"]
        if key not in latest or ts > latest[key][0]:
            latest[key] = (ts, row)
    return {key: value for key, (_, value) in latest.items()}


def build_final_indexes(final_rows):
    confirmed = [
        row for row in final_rows
        if row.get("event_type") == "final_eval" and row.get("review_status") == "confirmed"
    ]
    by_image_session = {}
    grouped = defaultdict(list)
    for row in confirmed:
        grouped[(row.get("image_id"), row.get("session_id"))].append(row)
    for key, rows in grouped.items():
        by_image_session[key] = latest_by_timestamp(rows).get(key[0])
    return by_image_session, latest_by_timestamp(confirmed)


def read_external_holdout_truth(path):
    """Read holdout truth from an external JSON/JSONL file.

    This supports the worksheet extract generated outside the vault:
    [
      {"filename": "holdout_001.png", "aaron_final_label": "anti", ...}
    ]

    The file intentionally lives outside /workspace/series-vault so Brain can
    rerun blind holdout predictions without seeing Aaron's answer key.
    """
    if not path:
        return {}, {}
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"holdout truth file not found: {path}")

    text = path.read_text().strip()
    if not text:
        return {}, {}

    if text.startswith("["):
        raw_rows = json.loads(text)
    else:
        raw_rows = [json.loads(line) for line in text.splitlines() if line.strip()]

    by_filename = {}
    by_image_id = {}
    for row in raw_rows:
        label = row.get("aaron_final_label") or row.get("anchor_promotion")
        if label not in validate_eval.ANCHOR_PROMOTIONS:
            continue
        normalized = {
            "filename": row.get("filename"),
            "image_id": row.get("image_id"),
            "anchor_promotion": label,
            "aaron_score": row.get("aaron_score"),
            "feedback_text": row.get("aaron_reason", ""),
            "final_notes": "External holdout truth; not stored in Brain-readable vault logs.",
        }
        if normalized["filename"]:
            by_filename[normalized["filename"]] = normalized
        if normalized["image_id"]:
            by_image_id[normalized["image_id"]] = normalized
    return by_filename, by_image_id


def quality_match(predicted, actual):
    if predicted == actual:
        return 1.0
    if predicted in QUALITY_ORDER and actual in QUALITY_ORDER:
        if abs(QUALITY_ORDER.index(predicted) - QUALITY_ORDER.index(actual)) == 1:
            return 0.5
    return 0.0


def exact_match(predicted, actual):
    return 1.0 if predicted == actual else 0.0


def split_tags(value):
    if not isinstance(value, str) or not value.strip():
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def tag_match(predicted, actual):
    pred = split_tags(predicted)
    act = split_tags(actual)
    if not pred and not act:
        return 1.0
    if not pred or not act:
        return 0.0
    return len(pred & act) / len(pred | act)


def compute_score(pre, final):
    breakdown = {
        "quality_tier": quality_match(pre.get("brain_initial_quality_tier"), final.get("quality_tier")),
        "anchor_promotion": exact_match(
            pre.get("brain_initial_anchor_promotion_recommendation"),
            final.get("anchor_promotion"),
        ),
        "world_state": exact_match(pre.get("brain_initial_world_state"), final.get("world_state")),
        "tone": exact_match(pre.get("brain_initial_tone"), final.get("tone")),
        "failure_mode": exact_match(pre.get("brain_initial_failure_mode"), final.get("failure_mode")),
        "tags": tag_match(pre.get("brain_initial_tags"), final.get("feedback_tags")),
    }
    score = sum(WEIGHTS[key] * value for key, value in breakdown.items())
    return round(score, 6), breakdown


def compute_external_holdout_score(pre, truth):
    predicted = pre.get("brain_initial_anchor_promotion_recommendation")
    actual = truth.get("anchor_promotion")
    score = 1.0 if predicted == actual else 0.0
    return score, {
        "scoring_scope": "external_holdout_promotion_only",
        "brain_initial_anchor_promotion_recommendation": predicted,
        "anchor_promotion": actual,
        "aaron_score": truth.get("aaron_score"),
    }


def derive_alignment_phase(pre, holdout_seen):
    if pre.get("image_origin") != "holdout_benchmark":
        return "normal"
    image_id = pre.get("image_id")
    if image_id not in holdout_seen:
        holdout_seen.add(image_id)
        return "baseline"
    return "post_seed"


def build_alignment_row(pre, final, alignment_score, breakdown, phase):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": pre["session_id"],
        "image_id": pre["image_id"],
        "filename": pre["filename"],
        "source_path": pre["source_path"],
        "image_origin": pre["image_origin"],
        "created_by": pre.get("created_by", final.get("created_by", "unknown")),
        "event_type": "alignment",
        "review_status": final.get("review_status", "confirmed"),
        "event_timestamp": now,
        "pre_eval_timestamp": pre.get("brain_initial_timestamp") or pre.get("event_timestamp"),
        "final_eval_timestamp": final.get("final_eval_timestamp") or final.get("event_timestamp"),
        "alignment_score": alignment_score,
        "alignment_phase": phase,
        "alignment_breakdown": breakdown,
        "weighting_version": WEIGHTING_VERSION,
        "computed_at": now,
    }


def session_sort_key(session_id):
    return parse_timestamp(session_id) or datetime.min.replace(tzinfo=timezone.utc)


def render_charts(rows):
    if not rows:
        print("No alignment rows yet.")
        return

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        render_charts_basic_png(rows)
        return

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    by_session = defaultdict(list)
    phase_by_session = defaultdict(Counter)
    for row in rows:
        by_session[row["session_id"]].append(row["alignment_score"])
        phase_by_session[row["session_id"]][row["alignment_phase"]] += 1

    sessions = sorted(by_session, key=session_sort_key)
    means = [sum(by_session[s]) / len(by_session[s]) for s in sessions]
    labels = [s.replace("T", "\n") for s in sessions]
    colors = []
    for session in sessions:
        phase = phase_by_session[session].most_common(1)[0][0]
        colors.append({"baseline": "#6b7280", "post_seed": "#2563eb", "normal": "#059669"}[phase])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(range(len(sessions)), means, color="#111827", linewidth=1.5)
    ax.scatter(range(len(sessions)), means, c=colors, s=70)
    ax.set_xticks(range(len(sessions)), labels)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Session")
    ax.set_ylabel("Mean alignment score")
    ax.set_title("Alignment score by session")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(ALIGNMENT_CHART)
    plt.close(fig)

    metrics = promotion_metrics(rows)
    labels = ["promoted"] + PROMOTION_LABELS
    precision = [metrics[label]["precision"] for label in labels]
    recall = [metrics[label]["recall"] for label in labels]
    x = list(range(len(labels)))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([i - width / 2 for i in x], precision, width, label="precision")
    ax.bar([i + width / 2 for i in x], recall, width, label="recall")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.set_title("Anchor promotion precision / recall")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(PROMOTION_CHART)
    plt.close(fig)


def write_png(path, width, height, pixels):
    """Write an RGB PNG with only stdlib dependencies."""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start:start + stride])

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join([
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
        chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
        chunk(b"IEND", b""),
    ])
    path.write_bytes(data)


def blank_canvas(width, height, color=(255, 255, 255)):
    return bytearray(color * (width * height))


def put_pixel(pixels, width, height, x, y, color):
    if 0 <= x < width and 0 <= y < height:
        idx = (y * width + x) * 3
        pixels[idx:idx + 3] = bytes(color)


def draw_rect(pixels, width, height, x0, y0, x1, y1, color):
    x0, x1 = sorted((max(0, x0), min(width - 1, x1)))
    y0, y1 = sorted((max(0, y0), min(height - 1, y1)))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put_pixel(pixels, width, height, x, y, color)


def draw_line(pixels, width, height, x0, y0, x1, y1, color):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        put_pixel(pixels, width, height, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def render_charts_basic_png(rows):
    """Fallback charts when matplotlib is unavailable.

    These are intentionally simple but valid PNGs. They preserve the core visual
    signal for verification: phase-colored alignment points and promotion
    precision/recall bars.
    """
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    width, height = 900, 450
    left, right, top, bottom = 70, 40, 35, 70
    by_session = defaultdict(list)
    phase_by_session = defaultdict(Counter)
    for row in rows:
        by_session[row["session_id"]].append(row["alignment_score"])
        phase_by_session[row["session_id"]][row["alignment_phase"]] += 1

    sessions = sorted(by_session, key=session_sort_key)
    means = [sum(by_session[s]) / len(by_session[s]) for s in sessions]
    colors_by_phase = {"baseline": (107, 114, 128), "post_seed": (37, 99, 235), "normal": (5, 150, 105)}

    pixels = blank_canvas(width, height)
    axis = (31, 41, 55)
    grid = (229, 231, 235)
    draw_line(pixels, width, height, left, top, left, height - bottom, axis)
    draw_line(pixels, width, height, left, height - bottom, width - right, height - bottom, axis)
    for i in range(1, 5):
        y = height - bottom - int((height - top - bottom) * i / 5)
        draw_line(pixels, width, height, left, y, width - right, y, grid)

    points = []
    denom = max(1, len(sessions) - 1)
    for idx, (session, mean) in enumerate(zip(sessions, means)):
        x = left + int((width - left - right) * idx / denom)
        y = height - bottom - int((height - top - bottom) * mean)
        phase = phase_by_session[session].most_common(1)[0][0]
        points.append((x, y, colors_by_phase[phase]))
    for (x0, y0, _), (x1, y1, _) in zip(points, points[1:]):
        draw_line(pixels, width, height, x0, y0, x1, y1, (17, 24, 39))
    for x, y, color in points:
        draw_rect(pixels, width, height, x - 5, y - 5, x + 5, y + 5, color)
    write_png(ALIGNMENT_CHART, width, height, pixels)

    metrics = promotion_metrics(rows)
    labels = ["promoted"] + PROMOTION_LABELS
    pixels = blank_canvas(width, height)
    draw_line(pixels, width, height, left, top, left, height - bottom, axis)
    draw_line(pixels, width, height, left, height - bottom, width - right, height - bottom, axis)
    group_w = (width - left - right) // len(labels)
    for i, label in enumerate(labels):
        base_x = left + i * group_w + group_w // 2
        precision_h = int((height - top - bottom) * metrics[label]["precision"])
        recall_h = int((height - top - bottom) * metrics[label]["recall"])
        draw_rect(pixels, width, height, base_x - 18, height - bottom - precision_h, base_x - 4, height - bottom, (37, 99, 235))
        draw_rect(pixels, width, height, base_x + 4, height - bottom - recall_h, base_x + 18, height - bottom, (5, 150, 105))
    write_png(PROMOTION_CHART, width, height, pixels)


def promotion_metrics(rows):
    stats = {}
    labels = ["promoted"] + PROMOTION_LABELS
    for label in labels:
        tp = fp = fn = 0
        for row in rows:
            breakdown = row.get("alignment_breakdown", {})
            pred = breakdown.get("brain_initial_anchor_promotion_recommendation")
            actual = breakdown.get("anchor_promotion")
            if pred is None or actual is None:
                continue
            if label == "promoted":
                pred_positive = pred in PROMOTION_LABELS
                actual_positive = actual in PROMOTION_LABELS
            else:
                pred_positive = pred == label
                actual_positive = actual == label
            if pred_positive and actual_positive:
                tp += 1
            elif pred_positive and not actual_positive:
                fp += 1
            elif not pred_positive and actual_positive:
                fn += 1
        stats[label] = {
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    return stats


def add_promotion_details(row, pre, final):
    row["alignment_breakdown"].setdefault(
        "brain_initial_anchor_promotion_recommendation",
        pre.get("brain_initial_anchor_promotion_recommendation"),
    )
    row["alignment_breakdown"].setdefault("anchor_promotion", final.get("anchor_promotion"))


def compute_alignment(holdout_truth_path=None):
    pre_rows, pre_malformed = read_jsonl(PRE_EVAL_LOG)
    final_rows, final_malformed = read_jsonl(FINAL_EVAL_LOG)
    by_image_session, latest_confirmed_by_image = build_final_indexes(final_rows)
    holdout_truth_by_filename, holdout_truth_by_image_id = read_external_holdout_truth(holdout_truth_path)

    eligible_pre = [
        row for row in pre_rows
        if row.get("event_type") == "pre_eval" and row.get("image_origin") != "smoke_test"
    ]
    eligible_pre.sort(key=lambda row: parse_timestamp(row.get("event_timestamp")) or datetime.min.replace(tzinfo=timezone.utc))

    rows = []
    skipped = Counter()
    holdout_seen = set()
    for pre in eligible_pre:
        uses_external_holdout_truth = False
        if pre.get("image_origin") == "holdout_benchmark":
            truth = (
                holdout_truth_by_image_id.get(pre.get("image_id"))
                or holdout_truth_by_filename.get(pre.get("filename"))
            )
            if truth:
                final = {
                    "review_status": "confirmed",
                    "anchor_promotion": truth["anchor_promotion"],
                    "final_eval_timestamp": truth.get("final_eval_timestamp") or pre.get("event_timestamp"),
                    "created_by": pre.get("created_by", "unknown"),
                }
                uses_external_holdout_truth = True
            else:
                final = latest_confirmed_by_image.get(pre.get("image_id"))
        else:
            final = by_image_session.get((pre.get("image_id"), pre.get("session_id")))
        if final is None:
            skipped["missing_ground_truth"] += 1
            continue
        if final.get("image_origin") == "smoke_test":
            skipped["smoke_test"] += 1
            continue

        if uses_external_holdout_truth:
            alignment_score, breakdown = compute_external_holdout_score(pre, truth)
        else:
            alignment_score, breakdown = compute_score(pre, final)
        phase = derive_alignment_phase(pre, holdout_seen)
        row = build_alignment_row(pre, final, alignment_score, breakdown, phase)
        if uses_external_holdout_truth:
            row["weighting_version"] = EXTERNAL_HOLDOUT_WEIGHTING_VERSION
        add_promotion_details(row, pre, final)
        validation = validate_eval.validate_record(row, "alignment")
        if not validation["ok"]:
            skipped["invalid_alignment_row"] += 1
            print(json.dumps({"image_id": row.get("image_id"), "errors": validation["errors"]}), file=sys.stderr)
            continue
        rows.append(row)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with ALIGNMENT_LOG.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    render_charts(rows)
    return {
        "ok": True,
        "alignment_rows": len(rows),
        "wrote": str(ALIGNMENT_LOG),
        "charts": [str(ALIGNMENT_CHART), str(PROMOTION_CHART)] if rows else [],
        "skipped": {
            "missing_ground_truth": skipped["missing_ground_truth"],
            "smoke_test": skipped["smoke_test"],
            "invalid_alignment_row": skipped["invalid_alignment_row"],
            "malformed_pre_eval_rows": pre_malformed,
            "malformed_final_eval_rows": final_malformed,
        },
        "holdout_truth_source": str(holdout_truth_path) if holdout_truth_path else None,
        "holdout_truth_rows": len(holdout_truth_by_filename) if holdout_truth_path else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute alignment rows and charts.")
    parser.add_argument(
        "--holdout-truth",
        default=os.environ.get("SERIES_HOLDOUT_TRUTH_PATH"),
        help=(
            "Optional external holdout truth JSON/JSONL path outside the Brain-readable vault. "
            "When provided, holdout_benchmark rows are scored against this file instead of final_eval_history.jsonl."
        ),
    )
    args = parser.parse_args()
    result = compute_alignment(holdout_truth_path=args.holdout_truth)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
