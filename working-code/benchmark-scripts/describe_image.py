"""describe_image.py — visual perception layer (Group A schema fields).

Calls Gemini 3 Flash (default) to produce a structured visual observation report.
Does NOT assign rubric vocabulary tags. Brain (GPT-5.5) interprets perception
into world_state / tone / quality_tier / anchor_promotion. This script reports
what is visible, not what it means.

Per benchmark/SCHEMA.md:
- schema_version: v1
- perception_prompt_version: v1
- perception_model: gemini-3-flash-preview (locked 2026-04-29 after benchmark
  research: ~2.3x faster TTFT vs 3.1 Pro Preview, ~5x cheaper, 80% vs 82% on
  MMMU Pro visual reasoning. --model override flag available for per-image
  fallback to gemini-3.1-pro-preview if Flash misses small details.)

Usage:
    python describe_image.py <image_path>
    python describe_image.py <image_path> --session-id 2026-04-28T22:00:00Z
    python describe_image.py <image_path> --origin smoke_test --no-log
    python describe_image.py <image_path> --model gemini-3.1-pro-preview --no-log

Output: prints the full perception record (JSON) to stdout. Unless --no-log,
also appends the record to benchmark/logs/perception_history.jsonl.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_eval  # noqa: E402

SCHEMA_VERSION = "v1"
PERCEPTION_PROMPT_VERSION = "v1"
PERCEPTION_MODEL = "gemini-3-flash-preview"
LOG_PATH = Path("/workspace/series-vault/benchmark/logs/perception_history.jsonl")

WORLD_STATES = ["flourishing", "sacred", "broken", "corrupted", "abandoned", "harsh", "neutral", "dna-core"]
TONES = ["hopeful", "awe-filled", "mournful", "eerie", "tense", "oppressive", "still", "neutral"]

EXPECTED_PERCEPTION_KEYS = {
    "perception_subject",
    "perception_composition",
    "perception_dominant_colors",
    "perception_visible_text",
    "perception_spatial_layout",
    "perception_atmosphere",
    "perception_notable_details",
    "perception_possible_state_cues",
    "perception_possible_tone_cues",
}

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

PERCEPTION_PROMPT = f"""You are the visual perception layer for a creative-AI system. Your job is to produce a rich, structured visual observation of the image you see. A separate creative-AI system (the "brain") will read your observations and apply rubric vocabulary to interpret them. You are the eyes; you are not the judge.

CRITICAL RULES:
- Describe what you SEE. Do not interpret, evaluate, or judge.
- Do NOT assign concrete values from these locked vocabularies. The brain owns these decisions:
    world_state vocabulary: {WORLD_STATES}
    tone vocabulary: {TONES}
- You MAY mention "visual cues that might suggest a [free-text descriptor]" but never output a final tag.
- Be concrete and grounded in what is actually visible. If something is not visible, do not speculate about it.
- Transcribe any visible text verbatim, including stylized titles.
- Catch small details. A small creature, a partial figure, an unusual material, a subtle color band — flag them in `perception_notable_details`.

Return your response as a JSON object with these exact keys (no additional keys, no missing keys):

{{
  "perception_subject": "what's in the foreground / primary subject — concrete description",
  "perception_composition": "spatial layout, framing, focal points",
  "perception_dominant_colors": ["color descriptor 1", "color descriptor 2", "color descriptor 3"],
  "perception_visible_text": "any text rendered in the image, transcribed verbatim, or empty string if none",
  "perception_spatial_layout": "relationships between elements, depth cues, foreground/midground/background",
  "perception_atmosphere": "felt-quality observations — light, mist, weight, stillness, tension, etc.",
  "perception_notable_details": "specific elements worth flagging — small creatures, unusual objects, materiality cues, partial figures",
  "perception_possible_state_cues": "free-text suggestions about what kind of place is depicted, in your own words. DO NOT use the locked vocabulary words. Example acceptable: 'cues that might suggest a contemplative or reverent space'. Example forbidden: 'state: sacred'.",
  "perception_possible_tone_cues": "free-text suggestions about felt-quality, in your own words. DO NOT use the locked vocabulary words. Example acceptable: 'the atmosphere reads as still and patient'. Example forbidden: 'tone: still'."
}}
"""


def compute_image_id(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest[:16]}"


def perceive(image_path: Path, model: str = PERCEPTION_MODEL) -> dict:
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("ERROR: GEMINI_API_KEY not set in container env. Check docker_forward_env in profile config.")

    image_bytes = image_path.read_bytes()
    mime = MIME_BY_SUFFIX.get(image_path.suffix.lower(), "image/jpeg")

    client = genai.Client()

    response = client.models.generate_content(
        model=model,
        contents=[
            PERCEPTION_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type=mime),
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    raw_text = response.text or ""

    try:
        structured = json.loads(raw_text)
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: Gemini response was not valid JSON: {e}\nRaw response:\n{raw_text}")

    missing = EXPECTED_PERCEPTION_KEYS - set(structured.keys())
    if missing:
        sys.exit(f"ERROR: Gemini response missing expected keys: {sorted(missing)}\nRaw response:\n{raw_text}")

    extra = set(structured.keys()) - EXPECTED_PERCEPTION_KEYS
    if extra:
        print(f"WARNING: Gemini returned extra keys (ignored): {sorted(extra)}", file=sys.stderr)

    return {"raw_text": raw_text, "structured": structured}


def build_record(image_path: Path, perception: dict, session_id: str, origin: str, model: str = PERCEPTION_MODEL) -> dict:
    image_id = compute_image_id(image_path)
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "image_id": image_id,
        "filename": image_path.name,
        "source_path": str(image_path),
        "image_origin": origin,
        "event_type": "perception",
        "review_status": "pending",
        "event_timestamp": now,
        "perception_model": model,
        "perception_model_version": None,
        "perception_prompt_version": PERCEPTION_PROMPT_VERSION,
        "perception_timestamp": now,
        "perception_text": perception["raw_text"],
    }
    for key in EXPECTED_PERCEPTION_KEYS:
        record[key] = perception["structured"][key]

    return record


def append_log(record: dict, log_path: Path) -> None:
    result = validate_eval.append_unique_jsonl(record, log_path)
    if result["status"] == "skipped_duplicate":
        print(
            "INFO: perception row already exists for "
            f"event_type={record['event_type']} session_id={record['session_id']} image_id={record['image_id']}; "
            f"skipped append at {log_path}",
            file=sys.stderr,
        )
    elif result["status"] != "appended":
        sys.exit(f"ERROR: failed to append perception record: {json.dumps(result)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Describe an image via Gemini perception (default: {PERCEPTION_MODEL}).")
    parser.add_argument("image_path", help="Container path to the image (e.g., /workspace/series-vault/...)")
    parser.add_argument("--session-id", default=None, help="ISO 8601 session identifier (defaults to now)")
    parser.add_argument(
        "--origin",
        default="anchor_seed",
        choices=["anchor_seed", "external_inbox", "generation", "holdout_benchmark", "smoke_test"],
    )
    parser.add_argument("--no-log", action="store_true", help="Skip appending to perception_history.jsonl")
    parser.add_argument(
        "--model",
        default=PERCEPTION_MODEL,
        help=f"Override perception model id (default: {PERCEPTION_MODEL}). Use for A/B tests with --no-log.",
    )
    args = parser.parse_args()

    image_path = Path(args.image_path)
    if not image_path.exists():
        sys.exit(f"ERROR: image not found at {image_path}")
    if not image_path.is_file():
        sys.exit(f"ERROR: path is not a file: {image_path}")

    session_id = args.session_id or datetime.now(timezone.utc).isoformat()

    perception = perceive(image_path, model=args.model)
    record = build_record(image_path, perception, session_id, args.origin, model=args.model)

    validation = validate_eval.validate_record(record, "perception")
    if not validation["ok"]:
        sys.stderr.write("ERROR: built record failed validate_eval --mode perception:\n")
        sys.stderr.write(json.dumps(validation, indent=2) + "\n")
        sys.exit(2)

    if not args.no_log:
        append_log(record, LOG_PATH)

    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
