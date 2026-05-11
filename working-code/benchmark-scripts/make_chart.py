"""make_chart.py - render benchmark charts from JSONL logs.

Per benchmark/SCHEMA.md and plan 04 step 12.

Reads `benchmark/logs/generations.jsonl` and writes two PNGs to `benchmark/charts/`:
- `taste_score_over_time.png` — per-image taste_alignment plotted by event_timestamp
- `taste_score_by_model.png`  — per-generation_model mean taste_alignment (bar chart)

Reads `benchmark/logs/alignment.jsonl` when present and writes:
- `alignment_score_by_session.png`
- `promotion_precision_recall.png`

Boot Clean path (plan 04 contract):
- If chartable logs are missing or empty, print "No entries yet." and exit 0.
- No matplotlib import attempted on the empty path, so the script runs cleanly
  on a host without matplotlib installed.

Plan 04 only verifies the empty path. Real chart rendering is exercised in plan
06 once generation review starts populating generations.jsonl.

Generation log row contract (locked here so plan 06 ingest_batch.py must conform —
also recorded in benchmark/SCHEMA.md "generations.jsonl row" section):
    event_timestamp     ISO 8601 UTC string
    taste_alignment     number — score.py output for this image vs visual_anchors
    generation_model    string — provider+model id (e.g. "nano-banana-pro",
                        "gpt-image-2", "flow-google-veo3")

Rows missing any of those fields are skipped with aggregate skip counts reported
to stderr (separate counts for smoke-test rows and malformed rows). Records with
`image_origin == "smoke_test"` are excluded per SCHEMA.md.

Usage:
    python make_chart.py
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("/workspace/series-vault/benchmark/logs/generations.jsonl")
ALIGNMENT_LOG_PATH = Path("/workspace/series-vault/benchmark/logs/alignment.jsonl")
CHARTS_DIR = Path("/workspace/series-vault/benchmark/charts")
CHART_OVER_TIME = CHARTS_DIR / "taste_score_over_time.png"
CHART_BY_MODEL = CHARTS_DIR / "taste_score_by_model.png"
ALIGNMENT_CHART = CHARTS_DIR / "alignment_score_by_session.png"
PROMOTION_CHART = CHARTS_DIR / "promotion_precision_recall.png"
PROMOTION_LABELS = ["gold", "anti", "aspirational"]


def parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def load_rows(log_path: Path):
    rows = []
    with log_path.open() as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"WARNING: line {line_num} not valid JSON: {e}", file=sys.stderr)
                continue
            rows.append(row)
    return rows


def filter_rows(rows):
    """Apply schema-required filters: drop smoke-test rows, drop rows missing required fields.

    Returns (kept, skipped_smoke, skipped_malformed). Counts let main() print a
    summary so plan 06 ingestion bugs are visible rather than silent.
    """
    kept = []
    skipped_smoke = 0
    skipped_malformed = 0
    for row in rows:
        if row.get("image_origin") == "smoke_test":
            skipped_smoke += 1
            continue
        ts = parse_timestamp(row.get("event_timestamp"))
        score = row.get("taste_alignment")
        model = row.get("generation_model")
        if ts is None or not isinstance(score, (int, float)) or isinstance(score, bool) or not isinstance(model, str):
            skipped_malformed += 1
            continue
        kept.append({"timestamp": ts, "score": float(score), "model": model})
    return kept, skipped_smoke, skipped_malformed


def filter_alignment_rows(rows):
    kept = []
    skipped_smoke = 0
    skipped_malformed = 0
    for row in rows:
        if row.get("image_origin") == "smoke_test":
            skipped_smoke += 1
            continue
        score = row.get("alignment_score")
        session_id = row.get("session_id")
        phase = row.get("alignment_phase")
        breakdown = row.get("alignment_breakdown")
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not isinstance(session_id, str)
            or phase not in {"baseline", "post_seed", "normal"}
            or not isinstance(breakdown, dict)
        ):
            skipped_malformed += 1
            continue
        kept.append({
            "session_id": session_id,
            "score": float(score),
            "phase": phase,
            "breakdown": breakdown,
        })
    return kept, skipped_smoke, skipped_malformed


def render_generation_charts(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    rows_sorted = sorted(rows, key=lambda r: r["timestamp"])
    times = [r["timestamp"] for r in rows_sorted]
    scores = [r["score"] for r in rows_sorted]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(times, scores, marker="o", linestyle="-")
    ax.set_xlabel("Event timestamp (UTC)")
    ax.set_ylabel("Taste alignment")
    ax.set_title("Taste alignment over time")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_OVER_TIME)
    plt.close(fig)

    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r["score"])
    models = sorted(by_model.keys())
    means = [sum(by_model[m]) / len(by_model[m]) for m in models]
    counts = [len(by_model[m]) for m in models]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(models, means)
    ax.set_xlabel("Generation model")
    ax.set_ylabel("Mean taste alignment")
    ax.set_title("Mean taste alignment by generation model")
    ax.grid(True, axis="y", alpha=0.3)
    for i, (m, c) in enumerate(zip(models, counts)):
        ax.text(i, means[i], f"n={c}", ha="center", va="bottom", fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_BY_MODEL)
    plt.close(fig)


def session_sort_key(session_id):
    parsed = parse_timestamp(session_id)
    return parsed.isoformat() if parsed else session_id


def promotion_metrics(rows):
    stats = {}
    labels = ["promoted"] + PROMOTION_LABELS
    for label in labels:
        tp = fp = fn = 0
        for row in rows:
            breakdown = row["breakdown"]
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
        }
    return stats


def render_alignment_charts(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    by_session = defaultdict(list)
    phase_by_session = defaultdict(Counter)
    for row in rows:
        by_session[row["session_id"]].append(row["score"])
        phase_by_session[row["session_id"]][row["phase"]] += 1

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
    metric_labels = ["promoted"] + PROMOTION_LABELS
    precision = [metrics[label]["precision"] for label in metric_labels]
    recall = [metrics[label]["recall"] for label in metric_labels]
    x = list(range(len(metric_labels)))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([i - width / 2 for i in x], precision, width, label="precision")
    ax.bar([i + width / 2 for i in x], recall, width, label="recall")
    ax.set_xticks(x, metric_labels)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.set_title("Anchor promotion precision / recall")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(PROMOTION_CHART)
    plt.close(fig)


def main():
    wrote_any = False

    usable = []
    if LOG_PATH.exists():
        rows = load_rows(LOG_PATH)
        usable, skipped_smoke, skipped_malformed = filter_rows(rows)

        if skipped_smoke or skipped_malformed:
            print(
                f"Skipped {skipped_smoke} smoke-test generation rows and {skipped_malformed} "
                f"generation rows missing required fields (event_timestamp + taste_alignment + generation_model).",
                file=sys.stderr,
            )

    alignment_usable = []
    if ALIGNMENT_LOG_PATH.exists():
        alignment_rows = load_rows(ALIGNMENT_LOG_PATH)
        alignment_usable, skipped_smoke, skipped_malformed = filter_alignment_rows(alignment_rows)

        if skipped_smoke or skipped_malformed:
            print(
                f"Skipped {skipped_smoke} smoke-test alignment rows and {skipped_malformed} "
                f"alignment rows missing required fields.",
                file=sys.stderr,
            )

    if not usable and not alignment_usable:
        print("No entries yet.")
        return 0

    if usable:
        try:
            render_generation_charts(usable)
        except Exception as e:
            print(f"ERROR: generation chart rendering failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        wrote_any = True
        print(f"Wrote {CHART_OVER_TIME}")
        print(f"Wrote {CHART_BY_MODEL}")
        print(f"Plotted {len(usable)} generation rows across {len(set(r['model'] for r in usable))} models.")

    if alignment_usable:
        try:
            render_alignment_charts(alignment_usable)
        except Exception as e:
            print(f"ERROR: alignment chart rendering failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        wrote_any = True
        print(f"Wrote {ALIGNMENT_CHART}")
        print(f"Wrote {PROMOTION_CHART}")
        print(f"Plotted {len(alignment_usable)} alignment rows across {len(set(r['session_id'] for r in alignment_usable))} sessions.")

    return 0 if wrote_any else 1


if __name__ == "__main__":
    sys.exit(main())
