"""create_lightbox.py - build a reviewable HTML lightbox from latest image rows.

Reads latest generation rows, applies review filters, copies source images into
a lightbox folder, and writes:

- reviews/visual/lightboxes/<date>-<slug>/index.html
- reviews/visual/lightboxes/<date>-<slug>/lightbox-manifest.json

The rendered diagnostics use Track 1.A's raw score and gold/anti diagnostic
fields. When both --image-ids and --image-ids-file are provided, inline IDs
are ordered first and file IDs append after order-preserving de-duplication.
"""

import argparse
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_VAULT_ROOT = Path("/workspace/series-vault")
if not DEFAULT_VAULT_ROOT.exists():
    DEFAULT_VAULT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_LOGS_DIR = DEFAULT_VAULT_ROOT / "benchmark" / "logs"
DEFAULT_OUTPUT_ROOT = DEFAULT_VAULT_ROOT / "reviews" / "visual" / "lightboxes"
WORKSPACE_ROOT = Path("/workspace/series-vault")
DEFAULT_GENERATIONS_LOG = "generations.jsonl"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def parse_args():
    parser = argparse.ArgumentParser(description="Create an HTML lightbox from latest benchmark rows.")
    parser.add_argument("--slug", required=True, help="Short slug used in the output folder name.")
    parser.add_argument("--description", default="", help="Human-readable lightbox description.")
    parser.add_argument("--logs-dir", type=Path, default=DEFAULT_LOGS_DIR)
    parser.add_argument(
        "--source-jsonl",
        type=Path,
        action="append",
        default=[],
        help="Verification override; production default reads benchmark/logs/generations.jsonl.",
    )
    parser.add_argument("--vault-root", type=Path, default=DEFAULT_VAULT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--date", default=None, help="Override output date prefix, YYYY-MM-DD.")
    parser.add_argument("--limit", type=positive_int, default=100)
    parser.add_argument("--image-ids", help="Comma-separated explicit image IDs to include.")
    parser.add_argument(
        "--image-ids-file",
        type=Path,
        help="File containing either a JSON object with image_ids or newline-delimited image IDs.",
    )
    parser.add_argument("--tier", help="Filter by final quality_tier, falling back to Brain's initial tier.")
    parser.add_argument("--tags", help="Comma-separated tags; at least one must match feedback or Brain tags.")
    parser.add_argument("--state", help="Filter by final world_state, falling back to Brain's initial state.")
    parser.add_argument("--tone", help="Filter by final tone, falling back to Brain's initial tone.")
    parser.add_argument("--model", help="Filter by generation_model, perception_model, or created_by.")
    parser.add_argument("--score-min", type=float, help="Minimum primary score.")
    parser.add_argument("--score-max", type=float, help="Maximum primary score.")
    parser.add_argument("--scene-fit", choices=["true", "false", "n-a"], help="Filter scene-fit value.")
    parser.add_argument("--failure-mode", choices=["execution", "concept", "partial", "none"])
    parser.add_argument("--promotion", choices=["none", "gold", "anti", "aspirational"])
    parser.add_argument("--review-status", choices=["pending", "pre_evaluated", "in_review", "confirmed", "embedded"])
    return parser.parse_args()


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("must be an integer") from e
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def read_jsonl(path):
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
                row = json.loads(line)
            except json.JSONDecodeError as e:
                malformed += 1
                print(f"WARNING: {path}:{line_num} invalid JSON: {e}", file=sys.stderr)
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                malformed += 1
                print(f"WARNING: {path}:{line_num} JSON root is not an object", file=sys.stderr)
    return rows, malformed


def ordered_unique(values):
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_image_ids(values, source):
    image_ids = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{source} item {index} must be a non-empty string")
        image_ids.append(value.strip())
    return image_ids


def parse_image_ids_file(path):
    try:
        text = path.read_text()
    except OSError as e:
        raise ValueError(f"could not read {path}: {e}") from e

    stripped = text.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return normalize_image_ids(lines, str(path))

    if not isinstance(parsed, dict):
        raise ValueError(
            f"{path} JSON root must be an object containing an image_ids array; "
            "bare JSON arrays are not accepted, or use a newline-delimited ID file"
        )
    image_ids = parsed.get("image_ids")
    if not isinstance(image_ids, list):
        raise ValueError(f"{path} JSON object must contain an image_ids array")
    return normalize_image_ids(image_ids, f"{path} image_ids")


def explicit_image_ids(args):
    image_ids = []
    if args.image_ids:
        inline = [part.strip() for part in args.image_ids.split(",") if part.strip()]
        image_ids.extend(normalize_image_ids(inline, "--image-ids"))
    if args.image_ids_file:
        image_ids.extend(parse_image_ids_file(args.image_ids_file))
    return ordered_unique(image_ids)


def has_explicit_image_id_input(args):
    return args.image_ids is not None or args.image_ids_file is not None


def parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def row_timestamp(row):
    parsed = parse_timestamp(row.get("event_timestamp"))
    if parsed is not None:
        return parsed
    return datetime.min.replace(tzinfo=timezone.utc)


def load_rows(logs_dir, source_jsonls):
    rows = []
    malformed = 0
    paths = source_jsonls or [logs_dir / DEFAULT_GENERATIONS_LOG]
    seen = set()
    for path in paths:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        loaded, count = read_jsonl(path)
        rows.extend(loaded)
        malformed += count
    return rows, malformed


def latest_rows(rows):
    by_image = {}
    for append_order, row in enumerate(rows):
        image_id = row.get("image_id")
        if not isinstance(image_id, str):
            continue
        candidate_key = (row_timestamp(row), append_order)
        if image_id not in by_image or candidate_key >= by_image[image_id][0]:
            by_image[image_id] = (candidate_key, dict(row))
    return [row for _, row in by_image.values()]


def split_csv(value):
    if not isinstance(value, str):
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def lower_or_none(value):
    return value.lower() if isinstance(value, str) else None


def first_present(row, *fields):
    for field in fields:
        value = row.get(field)
        if value is not None:
            return value
    return None


def primary_score(row):
    for field in ("taste_alignment", "brain_initial_score_raw", "alignment_score"):
        value = row.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def row_matches(row, args):
    if args.tier and first_present(row, "quality_tier", "brain_initial_quality_tier") != args.tier:
        return False
    if args.state and first_present(row, "world_state", "brain_initial_world_state") != args.state:
        return False
    if args.tone and first_present(row, "tone", "brain_initial_tone") != args.tone:
        return False
    if args.model:
        models = {
            lower_or_none(row.get("generation_model")),
            lower_or_none(row.get("perception_model")),
            lower_or_none(row.get("created_by")),
        }
        if args.model.lower() not in models:
            return False
    if args.scene_fit:
        scene_fit = first_present(row, "fits_current_scene", "brain_initial_scene_fit")
        if isinstance(scene_fit, bool):
            scene_fit = "true" if scene_fit else "false"
        if scene_fit != args.scene_fit:
            return False
    if args.failure_mode:
        failure_mode = first_present(row, "failure_mode", "brain_initial_failure_mode")
        if args.failure_mode == "none":
            if failure_mode is not None:
                return False
        elif failure_mode != args.failure_mode:
            return False
    if args.promotion and row.get("anchor_promotion") != args.promotion:
        return False
    if args.review_status and row.get("review_status") != args.review_status:
        return False
    if args.tags:
        wanted = split_csv(args.tags)
        available = split_csv(row.get("feedback_tags")) | split_csv(row.get("brain_initial_tags"))
        if wanted and not (wanted & available):
            return False
    score = primary_score(row)
    if args.score_min is not None and (score is None or score < args.score_min):
        return False
    if args.score_max is not None and (score is None or score > args.score_max):
        return False
    return True


def sort_key(row):
    score = primary_score(row)
    score_key = score if score is not None else float("-inf")
    return (score_key, row_timestamp(row))


def select_explicit_rows(latest, image_ids):
    by_image_id = {row.get("image_id"): row for row in latest if isinstance(row.get("image_id"), str)}
    selected = []
    missing = []
    for image_id in image_ids:
        row = by_image_id.get(image_id)
        if row is None:
            missing.append(image_id)
        else:
            selected.append(row)
    return selected, missing


def safe_slug(value):
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "lightbox"


def resolve_source_path(value, vault_root):
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        try:
            relative = path.relative_to(WORKSPACE_ROOT)
            return vault_root / relative
        except ValueError:
            return path
    return vault_root / path


def copy_image(row, output_images_dir, vault_root):
    source = resolve_source_path(row.get("source_path"), vault_root)
    if source is None or not source.exists() or not source.is_file():
        return None, f"missing image: {row.get('source_path')}"
    suffix = source.suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        return None, f"unsupported image extension: {source}"
    image_id = safe_slug(str(row.get("image_id", "image")).replace(":", "-"))
    filename = safe_slug(Path(row.get("filename") or source.name).stem) + suffix
    destination = output_images_dir / f"{image_id}-{filename}"
    shutil.copy2(source, destination)
    return destination.name, None


def display_value(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def field(row, key):
    return html.escape(display_value(row.get(key)))


def render_badges(row):
    badges = [
        ("review", row.get("review_status")),
        ("tier", first_present(row, "quality_tier", "brain_initial_quality_tier")),
        ("promotion", row.get("anchor_promotion")),
        ("phase", row.get("alignment_phase")),
        ("origin", row.get("image_origin")),
    ]
    return "\n".join(
        f'<span class="badge"><span>{html.escape(label)}</span>{html.escape(display_value(value))}</span>'
        for label, value in badges
        if value is not None
    )


def render_card(item):
    row = item["row"]
    alt_text = html.escape(display_value(row.get("filename") or "lightbox image"))
    heading = html.escape(display_value(first_present(row, "filename", "image_id") or "untitled"))
    image_id = html.escape(display_value(row.get("image_id") or ""))
    image_html = (
        f'<img src="images/{html.escape(item["image_file"])}" alt="{alt_text}">'
        if item.get("image_file")
        else '<div class="missing-image">Image file missing</div>'
    )
    score_rows = [
        ("taste / raw", row.get("brain_initial_score_raw")),
        ("gold similarity", row.get("brain_initial_gold_similarity")),
        ("anti similarity", row.get("brain_initial_anti_similarity")),
        ("initial rank", row.get("brain_initial_rank")),
        ("alignment score", row.get("alignment_score")),
        ("alignment phase", row.get("alignment_phase")),
        ("Aaron score", row.get("aaron_score")),
    ]
    score_html = "\n".join(
        f"<dt>{html.escape(label)}</dt><dd>{html.escape(display_value(value))}</dd>"
        for label, value in score_rows
        if value is not None
    )
    diagnostics = score_html or "<dt>scores</dt><dd>no diagnostics</dd>"
    return f"""
    <article class="card">
      <div class="media">{image_html}</div>
      <div class="body">
        <header>
          <h2>{heading}</h2>
          <p>{image_id}</p>
        </header>
        <div class="badges">{render_badges(row)}</div>
        <dl class="scores">{diagnostics}</dl>
        <dl class="details">
          <dt>world</dt><dd>{html.escape(display_value(first_present(row, "world_state", "brain_initial_world_state")))}</dd>
          <dt>tone</dt><dd>{html.escape(display_value(first_present(row, "tone", "brain_initial_tone")))}</dd>
          <dt>scene fit</dt><dd>{html.escape(display_value(first_present(row, "fits_current_scene", "brain_initial_scene_fit")))}</dd>
          <dt>failure</dt><dd>{html.escape(display_value(first_present(row, "failure_mode", "brain_initial_failure_mode")))}</dd>
          <dt>Brain promotion</dt><dd>{field(row, "brain_initial_anchor_promotion_recommendation")}</dd>
          <dt>created by</dt><dd>{field(row, "created_by")}</dd>
        </dl>
        <section>
          <h3>Notes</h3>
          <p>{html.escape(display_value(first_present(row, "final_notes", "brain_initial_notes", "feedback_text")))}</p>
        </section>
      </div>
    </article>
    """


def render_html(description, items, manifest):
    cards = "\n".join(render_card(item) for item in items)
    if not cards:
        cards = '<p class="empty">No images matched the filters.</p>'
    title = f"Series lightbox - {manifest['slug']}"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f5f2;
      color: #171717;
    }}
    body {{ margin: 0; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 32px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; font-weight: 720; letter-spacing: 0; }}
    .summary {{ color: #525252; margin: 0 0 24px; max-width: 900px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 18px; }}
    .card {{ background: #ffffff; border: 1px solid #dedbd2; border-radius: 8px; overflow: hidden; }}
    .media {{ aspect-ratio: 4 / 3; background: #1f2933; display: grid; place-items: center; }}
    img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
    .missing-image {{ color: #f6f5f2; font-weight: 650; }}
    .body {{ padding: 16px; }}
    header h2 {{ font-size: 17px; margin: 0; word-break: break-word; }}
    header p {{ font-size: 12px; color: #737373; margin: 4px 0 12px; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }}
    .badge {{ border: 1px solid #c8c3b8; border-radius: 999px; padding: 4px 8px; font-size: 12px; background: #f8f7f4; }}
    .badge span {{ color: #737373; margin-right: 5px; }}
    dl {{ display: grid; grid-template-columns: minmax(120px, 0.7fr) minmax(0, 1fr); gap: 6px 10px; margin: 0 0 14px; }}
    dt {{ color: #737373; font-size: 12px; }}
    dd {{ margin: 0; font-size: 13px; word-break: break-word; }}
    .scores {{ padding: 12px; border: 1px solid #e5e2dc; border-radius: 8px; background: #fbfaf8; }}
    h3 {{ font-size: 13px; margin: 0 0 6px; color: #525252; }}
    section p {{ margin: 0; font-size: 13px; line-height: 1.45; }}
    .empty {{ padding: 24px; border: 1px dashed #c8c3b8; border-radius: 8px; background: #fff; }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    <p class="summary">{html.escape(description or "Generated Series visual review lightbox.")}</p>
    <p class="summary">Created {html.escape(manifest["created_at"])}. {manifest["item_count"]} image(s). Manifest: lightbox-manifest.json.</p>
    <section class="grid">
      {cards}
    </section>
  </main>
</body>
</html>
"""


def manifest_item(row, image_file, warning):
    keys = [
        "image_id",
        "filename",
        "source_path",
        "image_origin",
        "created_by",
        "review_status",
        "quality_tier",
        "anchor_promotion",
        "brain_initial_anchor_promotion_recommendation",
        "brain_initial_score_raw",
        "brain_initial_gold_similarity",
        "brain_initial_anti_similarity",
        "brain_initial_rank",
        "alignment_score",
        "alignment_phase",
        "aaron_score",
        "world_state",
        "tone",
        "fits_current_scene",
        "failure_mode",
        "feedback_tags",
        "brain_initial_tags",
        "event_timestamp",
        "session_id",
    ]
    data = {key: row.get(key) for key in keys if key in row}
    data["copied_image"] = f"images/{image_file}" if image_file else None
    if warning:
        data["warning"] = warning
    return data


def choose_output_dir(base_dir):
    if not base_dir.exists():
        return base_dir
    for suffix in range(2, 1000):
        candidate = base_dir.with_name(f"{base_dir.name}-{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find unused output directory for {base_dir}")


def main():
    args = parse_args()
    slug = safe_slug(args.slug)
    date_prefix = args.date or datetime.now().strftime("%Y-%m-%d")
    try:
        selected_image_ids = explicit_image_ids(args)
    except ValueError as e:
        print(json.dumps({"ok": False, "stage": "parse_image_ids", "error": str(e)}), file=sys.stderr)
        return 2

    missing_image_ids = []
    explicit_mode = has_explicit_image_id_input(args)
    if explicit_mode and not selected_image_ids:
        print(
            json.dumps({"ok": False, "stage": "parse_image_ids", "error": "explicit image-id input was empty"}),
            file=sys.stderr,
        )
        return 2

    output_dir = choose_output_dir(args.output_root / f"{date_prefix}-{slug}")
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    rows, malformed = load_rows(args.logs_dir, args.source_jsonl)
    latest = latest_rows(rows)
    if explicit_mode:
        filtered, missing_image_ids = select_explicit_rows(latest, selected_image_ids)
    else:
        filtered = [row for row in latest if row_matches(row, args)]
        filtered = sorted(filtered, key=sort_key, reverse=True)[:args.limit]

    items = []
    warnings = []
    for image_id in missing_image_ids:
        warnings.append({"image_id": image_id, "warning": "image_id not found in latest rows"})
    for row in filtered:
        image_file, warning = copy_image(row, images_dir, args.vault_root)
        if warning:
            warnings.append({"image_id": row.get("image_id"), "warning": warning})
        items.append({"row": row, "image_file": image_file, "warning": warning})

    manifest = {
        "schema_version": "v1",
        "slug": slug,
        "description": args.description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_logs_dir": str(args.logs_dir),
        "production_source": str(args.logs_dir / DEFAULT_GENERATIONS_LOG),
        "source_jsonl": [str(path) for path in args.source_jsonl],
        "selection_mode": "explicit_image_ids" if explicit_mode else "structured_filters",
        "explicit_image_ids": selected_image_ids,
        "image_ids_file": str(args.image_ids_file) if args.image_ids_file else None,
        "missing_image_ids": missing_image_ids,
        "filters": {
            "tier": args.tier,
            "tags": args.tags,
            "state": args.state,
            "tone": args.tone,
            "model": args.model,
            "score_min": args.score_min,
            "score_max": args.score_max,
            "scene_fit": args.scene_fit,
            "failure_mode": args.failure_mode,
            "promotion": args.promotion,
            "review_status": args.review_status,
            "limit": args.limit,
        },
        "input_row_count": len(rows),
        "malformed_row_count": malformed,
        "latest_image_count": len(latest),
        "item_count": len(items),
        "warnings": warnings,
        "items": [manifest_item(item["row"], item["image_file"], item["warning"]) for item in items],
    }

    manifest_path = output_dir / "lightbox-manifest.json"
    html_path = output_dir / "index.html"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n")
    html_path.write_text(render_html(args.description, items, manifest))

    print(json.dumps({
        "ok": True,
        "output_dir": str(output_dir),
        "html": str(html_path),
        "manifest": str(manifest_path),
        "item_count": len(items),
        "warning_count": len(warnings),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
