"""validate_eval.py — strict deterministic validator for evaluation records.

Per benchmark/SCHEMA.md, validates a single evaluation record against the locked
schema. Modes:

    --mode generation_ingested
                          common + generated-asset lineage fields
    --mode perception        common + Group A required
    --mode pre_eval          common + Group A + Group B required
    --mode final_eval        common + Group A + Group C required (Group B optional)
    --mode embed_ready       final_eval + embed-after-confirm rules + content-hash check
    --mode lifecycle_event   common fields only (for status-bump rows like event_type=embedded)
    --mode auto              route each record by event_type

If --mode is not specified, auto-routes to lifecycle_event when event_type is a
known lifecycle bump (currently {"embedded"}); otherwise errors. Use
`--mode auto` to validate mixed JSONL files such as final_eval_history.jsonl,
which can contain both final_eval rows and embedded status-bump rows.

Input:
    --file <path>     read JSON from a file
    or stdin          pipe a single JSON object via stdin
    or --jsonl <path> validate every line of a JSONL file (each line = one record)

Output (single record):
    JSON to stdout: {"ok": bool, "mode": str, "errors": [{"field": str, "reason": str}]}
    Exit 0 if ok, 1 if any errors.

Output (JSONL):
    One line per record: {"line": int, "ok": bool, "mode": str, "errors": [...]}
    Exit 0 if all ok, 1 if any record has errors.

Does NOT make creative judgments. Vocab compliance + required fields + types
+ consistency rules. That's it.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-fA-F]{16}$")

SCHEMA_VERSION = "v1"

REVIEW_STATUSES = {"pending", "pre_evaluated", "in_review", "confirmed", "embedded"}
QUALITY_TIERS = {"bad", "okay", "great", "aspirational", "approved", "canon"}
BRAIN_QUALITY_TIERS = QUALITY_TIERS - {"canon"}
ANCHOR_PROMOTIONS = {"none", "gold", "anti", "aspirational"}
WORLD_STATES = {"flourishing", "sacred", "broken", "corrupted", "abandoned", "harsh", "neutral", "dna-core"}
TONES = {"hopeful", "awe-filled", "mournful", "eerie", "tense", "oppressive", "still", "neutral"}
FAILURE_MODES = {"execution", "concept", "partial"}
RANKS = {"strong", "promising", "borderline", "likely-miss"}
EVENT_TYPES = {"generation_ingested", "perception", "pre_eval", "final_eval", "embedded", "alignment"}
IMAGE_ORIGINS = {"anchor_seed", "external_inbox", "generation", "holdout_benchmark", "smoke_test"}
CREATED_BY_VALUES = {"midjourney", "nano-banana-pro", "gpt-image-2", "flow-google-veo3", "web", "unknown"}
ALIGNMENT_PHASES = {"baseline", "post_seed", "normal"}
SCENE_FIT_VALUES = {True, False, "n-a"}
LIFECYCLE_BUMP_EVENT_TYPES = {"embedded"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}

COMMON_FIELDS = {
    "schema_version",
    "session_id",
    "image_id",
    "filename",
    "source_path",
    "image_origin",
    "event_type",
    "review_status",
    "event_timestamp",
}

GROUP_A_FIELDS = {
    "perception_model",
    "perception_model_version",
    "perception_prompt_version",
    "perception_timestamp",
    "perception_text",
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

GROUP_B_FIELDS = {
    "brain_initial_score_raw",
    "brain_initial_gold_similarity",
    "brain_initial_anti_similarity",
    "brain_initial_rank",
    "brain_initial_quality_tier",
    "brain_initial_world_state",
    "brain_initial_tone",
    "brain_initial_scene_fit",
    "brain_initial_failure_mode",
    "brain_initial_tags",
    "brain_initial_notes",
    "brain_initial_anchor_promotion_recommendation",
    "brain_initial_canon_candidate",
    "brain_initial_confidence",
    "brain_initial_questions_or_flags",
    "brain_initial_timestamp",
}

GROUP_C_FIELDS = {
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
}
GROUP_C_OPTIONAL = {"aaron_perception_corrections"}

GROUP_D_FIELDS = {
    "pre_eval_timestamp",
    "final_eval_timestamp",
    "alignment_score",
    "alignment_phase",
    "alignment_breakdown",
    "weighting_version",
    "computed_at",
}

GENERATION_INGEST_FIELDS = {
    "job_id",
    "intent_id",
    "prompt_id",
    "target_id",
    "asset_id",
    "output_index",
    "base_concept",
    "model",
    "model_version",
    "platform",
    "generation_model",
    "rendered_prompt",
    "file_path",
    "original_file_path",
    "asset_event_timestamp",
    "sha256",
    "ingested_at",
    "score_status",
    "taste_alignment",
    "brain_initial_score_raw",
    "brain_initial_gold_similarity",
    "brain_initial_anti_similarity",
    "brain_initial_rank",
    "score_error",
}
SCORE_STATUSES = {"not_run", "scored", "unavailable"}

VAULT_CONTAINER_ROOT = Path("/workspace/series-vault")


def err(field: str, reason: str) -> dict:
    return {"field": field, "reason": reason}


def is_iso8601(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def is_valid_image_id(value) -> bool:
    return isinstance(value, str) and bool(IMAGE_ID_RE.match(value))


def is_in_vocab(value, vocab: set, allow_null: bool = False) -> bool:
    if value is None:
        return allow_null
    return value in vocab


def is_number_or_null(value) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def rank_from_score(score):
    if score is None:
        return None
    if score >= 0.82:
        return "strong"
    if score >= 0.72:
        return "promising"
    if score >= 0.62:
        return "borderline"
    return "likely-miss"


def require_string(record, field, errors, allow_empty=False):
    if field not in record:
        return
    val = record[field]
    if not isinstance(val, str):
        errors.append(err(field, f"expected string, got {type(val).__name__}"))
    elif not allow_empty and not val:
        errors.append(err(field, "required string is empty"))


def validate_common(record, errors):
    for field in COMMON_FIELDS:
        if field not in record:
            errors.append(err(field, "required field missing"))

    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(err("schema_version", f"expected '{SCHEMA_VERSION}', got {record.get('schema_version')!r}"))

    if "image_id" in record and not is_valid_image_id(record["image_id"]):
        errors.append(err("image_id", "must be 'sha256:' followed by 16 hex chars"))

    if "session_id" in record and not is_iso8601(record["session_id"]):
        errors.append(err("session_id", "must be ISO 8601 string"))

    if "event_timestamp" in record and not is_iso8601(record["event_timestamp"]):
        errors.append(err("event_timestamp", "must be ISO 8601 string"))

    if "image_origin" in record and not is_in_vocab(record["image_origin"], IMAGE_ORIGINS):
        errors.append(err("image_origin", f"must be one of {sorted(IMAGE_ORIGINS)}"))

    if "created_by" in record and not is_in_vocab(record["created_by"], CREATED_BY_VALUES):
        errors.append(err("created_by", f"must be one of {sorted(CREATED_BY_VALUES)}"))

    if "event_type" in record and not is_in_vocab(record["event_type"], EVENT_TYPES):
        errors.append(err("event_type", f"must be one of {sorted(EVENT_TYPES)}"))

    if "review_status" in record and not is_in_vocab(record["review_status"], REVIEW_STATUSES):
        errors.append(err("review_status", f"must be one of {sorted(REVIEW_STATUSES)}"))

    require_string(record, "filename", errors)
    require_string(record, "source_path", errors)


def require_created_by(record, errors):
    if "created_by" not in record:
        errors.append(err("created_by", "required field missing for production eval/alignment rows"))


def validate_group_a(record, errors):
    for field in GROUP_A_FIELDS:
        if field not in record:
            errors.append(err(field, "required Group A field missing"))

    require_string(record, "perception_model", errors)
    require_string(record, "perception_prompt_version", errors)
    require_string(record, "perception_text", errors)
    require_string(record, "perception_subject", errors)
    require_string(record, "perception_composition", errors)
    require_string(record, "perception_visible_text", errors, allow_empty=True)
    require_string(record, "perception_spatial_layout", errors)
    require_string(record, "perception_atmosphere", errors)
    require_string(record, "perception_notable_details", errors)
    require_string(record, "perception_possible_state_cues", errors)
    require_string(record, "perception_possible_tone_cues", errors)

    if "perception_timestamp" in record and not is_iso8601(record["perception_timestamp"]):
        errors.append(err("perception_timestamp", "must be ISO 8601 string"))

    colors = record.get("perception_dominant_colors")
    if colors is not None:
        if not isinstance(colors, list) or not all(isinstance(c, str) for c in colors):
            errors.append(err("perception_dominant_colors", "must be a list of strings"))


def validate_group_b(record, errors):
    for field in GROUP_B_FIELDS:
        if field not in record:
            errors.append(err(field, "required Group B field missing"))

    score_raw = record.get("brain_initial_score_raw")
    gold_similarity = record.get("brain_initial_gold_similarity")
    anti_similarity = record.get("brain_initial_anti_similarity")
    for field, value in (
        ("brain_initial_score_raw", score_raw),
        ("brain_initial_gold_similarity", gold_similarity),
        ("brain_initial_anti_similarity", anti_similarity),
    ):
        if not is_number_or_null(value):
            errors.append(err(field, "must be number or null (boolean rejected)"))

    if "brain_initial_rank" in record and not is_in_vocab(record["brain_initial_rank"], RANKS, allow_null=True):
        errors.append(err("brain_initial_rank", f"must be one of {sorted(RANKS)} or null"))
    elif "brain_initial_rank" in record and is_number_or_null(score_raw):
        expected_rank = rank_from_score(score_raw)
        if record["brain_initial_rank"] != expected_rank:
            errors.append(err(
                "brain_initial_rank",
                f"must derive from brain_initial_score_raw; expected {expected_rank!r}",
            ))

    if score_raw is None:
        if gold_similarity is not None:
            errors.append(err("brain_initial_gold_similarity", "must be null when brain_initial_score_raw is null"))
        if anti_similarity is not None:
            errors.append(err("brain_initial_anti_similarity", "must be null when brain_initial_score_raw is null"))
    elif is_number_or_null(gold_similarity) and is_number_or_null(anti_similarity):
        if gold_similarity is None or anti_similarity is None:
            errors.append(err(
                "brain_initial_score_raw",
                "gold/anti diagnostic fields must both be numbers when brain_initial_score_raw is a number",
            ))
        else:
            expected = gold_similarity - anti_similarity
            if abs(score_raw - expected) > 1e-9:
                errors.append(err(
                    "brain_initial_score_raw",
                    "must equal brain_initial_gold_similarity - brain_initial_anti_similarity",
                ))

    tier = record.get("brain_initial_quality_tier")
    if tier is not None:
        if not is_in_vocab(tier, BRAIN_QUALITY_TIERS):
            errors.append(err(
                "brain_initial_quality_tier",
                f"must be one of {sorted(BRAIN_QUALITY_TIERS)} (Brain may not assign 'canon')",
            ))

    if "brain_initial_world_state" in record and not is_in_vocab(record["brain_initial_world_state"], WORLD_STATES):
        errors.append(err("brain_initial_world_state", f"must be one of {sorted(WORLD_STATES)}"))

    if "brain_initial_tone" in record and not is_in_vocab(record["brain_initial_tone"], TONES):
        errors.append(err("brain_initial_tone", f"must be one of {sorted(TONES)}"))

    if "brain_initial_scene_fit" in record and record["brain_initial_scene_fit"] not in SCENE_FIT_VALUES:
        errors.append(err("brain_initial_scene_fit", "must be true, false, or 'n-a'"))

    fm = record.get("brain_initial_failure_mode")
    if fm is not None and fm not in FAILURE_MODES:
        errors.append(err("brain_initial_failure_mode", f"must be one of {sorted(FAILURE_MODES)} or null"))

    if "brain_initial_anchor_promotion_recommendation" in record:
        ap = record["brain_initial_anchor_promotion_recommendation"]
        if ap not in ANCHOR_PROMOTIONS:
            errors.append(err(
                "brain_initial_anchor_promotion_recommendation",
                f"must be one of {sorted(ANCHOR_PROMOTIONS)}",
            ))

    if "brain_initial_canon_candidate" in record:
        if not isinstance(record["brain_initial_canon_candidate"], bool):
            errors.append(err("brain_initial_canon_candidate", "must be boolean"))

    confidence = record.get("brain_initial_confidence")
    if confidence is not None:
        if not isinstance(confidence, dict):
            errors.append(err("brain_initial_confidence", "must be object/dict mapping fields to confidence levels"))
        else:
            for k, v in confidence.items():
                if v not in CONFIDENCE_LEVELS:
                    errors.append(err(
                        f"brain_initial_confidence.{k}",
                        f"value must be one of {sorted(CONFIDENCE_LEVELS)}",
                    ))

    if "brain_initial_timestamp" in record and not is_iso8601(record["brain_initial_timestamp"]):
        errors.append(err("brain_initial_timestamp", "must be ISO 8601 string"))

    require_string(record, "brain_initial_tags", errors, allow_empty=True)
    require_string(record, "brain_initial_notes", errors)

    qof = record.get("brain_initial_questions_or_flags")
    if qof is not None and not isinstance(qof, str):
        errors.append(err("brain_initial_questions_or_flags", "must be string or null"))


def validate_group_c(record, errors):
    for field in GROUP_C_FIELDS:
        if field not in record:
            errors.append(err(field, "required Group C field missing"))

    score = record.get("aaron_score")
    if score is not None and not (isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 10):
        errors.append(err("aaron_score", "must be integer in [0, 10]"))

    if "quality_tier" in record and not is_in_vocab(record["quality_tier"], QUALITY_TIERS):
        errors.append(err("quality_tier", f"must be one of {sorted(QUALITY_TIERS)}"))

    if "world_state" in record and not is_in_vocab(record["world_state"], WORLD_STATES):
        errors.append(err("world_state", f"must be one of {sorted(WORLD_STATES)}"))

    if "tone" in record and not is_in_vocab(record["tone"], TONES):
        errors.append(err("tone", f"must be one of {sorted(TONES)}"))

    if "fits_current_scene" in record and record["fits_current_scene"] not in SCENE_FIT_VALUES:
        errors.append(err("fits_current_scene", "must be true, false, or 'n-a'"))

    fm = record.get("failure_mode")
    if fm is not None and fm not in FAILURE_MODES:
        errors.append(err("failure_mode", f"must be one of {sorted(FAILURE_MODES)} or null"))

    if "anchor_promotion" in record and record["anchor_promotion"] not in ANCHOR_PROMOTIONS:
        errors.append(err("anchor_promotion", f"must be one of {sorted(ANCHOR_PROMOTIONS)}"))

    if "canon_candidate" in record and not isinstance(record["canon_candidate"], bool):
        errors.append(err("canon_candidate", "must be boolean"))

    require_string(record, "feedback_tags", errors, allow_empty=True)
    require_string(record, "feedback_text", errors, allow_empty=True)
    require_string(record, "final_notes", errors)

    if "final_eval_timestamp" in record and not is_iso8601(record["final_eval_timestamp"]):
        errors.append(err("final_eval_timestamp", "must be ISO 8601 string"))

    if "aaron_perception_corrections" in record:
        apc = record["aaron_perception_corrections"]
        if not isinstance(apc, list) or not all(isinstance(s, str) for s in apc):
            errors.append(err("aaron_perception_corrections", "must be a list of strings (when present)"))

    apply_anchor_promotion_consistency(record, errors)


def apply_anchor_promotion_consistency(record, errors):
    """Cross-field consistency rules for anchor_promotion vs quality_tier."""
    promo = record.get("anchor_promotion")
    tier = record.get("quality_tier")
    final_notes = record.get("final_notes") or ""

    if promo is None or tier is None:
        return

    if promo == "gold" and tier not in {"great", "approved", "canon"}:
        errors.append(err(
            "anchor_promotion",
            f"gold requires quality_tier in {{great, approved, canon}}; got {tier!r}",
        ))

    if promo == "anti" and tier != "bad":
        errors.append(err(
            "anchor_promotion",
            f"anti requires quality_tier == bad; got {tier!r}",
        ))

    if promo == "aspirational" and tier != "aspirational":
        if "override" not in final_notes.lower():
            errors.append(err(
                "anchor_promotion",
                (
                    f"aspirational anchor_promotion with quality_tier {tier!r} requires explicit override "
                    "recorded in final_notes (include the word 'override' in your notes)"
                ),
            ))


def resolve_source_path(record) -> Path:
    """Resolve source_path against in-container conventions.

    Accepts absolute container paths (/workspace/series-vault/...) and
    vault-relative paths (benchmark/anchors/gold/...).
    """
    raw = record.get("source_path", "")
    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p
    vault_relative = VAULT_CONTAINER_ROOT / raw.lstrip("/")
    return vault_relative


def validate_embed_ready(record, errors):
    """Run final_eval validation, then add embed-after-confirm gates."""
    validate_common(record, errors)
    require_created_by(record, errors)
    validate_group_a(record, errors)
    validate_group_c(record, errors)
    if any(f in record for f in GROUP_B_FIELDS):
        validate_group_b(record, errors)

    if record.get("review_status") != "confirmed":
        errors.append(err("review_status", f"embed requires 'confirmed'; got {record.get('review_status')!r}"))

    promo = record.get("anchor_promotion")
    if promo not in {"gold", "anti", "aspirational"}:
        errors.append(err(
            "anchor_promotion",
            f"embed requires anchor_promotion in {{gold, anti, aspirational}}; got {promo!r}",
        ))

    src = resolve_source_path(record)
    if not src.exists() or not src.is_file():
        errors.append(err("source_path", f"file does not exist or is not a file: {record.get('source_path')!r}"))
        return

    if promo in {"gold", "anti", "aspirational"}:
        expected_folder_part = f"benchmark/anchors/{promo}/"
        if expected_folder_part not in str(src):
            errors.append(err(
                "source_path",
                f"file must be located in benchmark/anchors/{promo}/ for anchor_promotion={promo}",
            ))

    declared = record.get("image_id")
    if declared and is_valid_image_id(declared):
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        computed = f"sha256:{digest[:16]}"
        if declared != computed:
            errors.append(err(
                "image_id",
                f"declared {declared} does not match computed {computed} for {src}",
            ))


def validate_lifecycle_event(record, errors):
    validate_common(record, errors)
    if record.get("event_type") not in LIFECYCLE_BUMP_EVENT_TYPES:
        errors.append(err(
            "event_type",
            f"lifecycle_event mode requires event_type in {sorted(LIFECYCLE_BUMP_EVENT_TYPES)}",
        ))


def validate_generation_ingested(record, errors):
    validate_common(record, errors)
    require_created_by(record, errors)
    for field in GENERATION_INGEST_FIELDS:
        if field not in record:
            errors.append(err(field, "required generation ingest field missing"))

    if record.get("event_type") != "generation_ingested":
        errors.append(err(
            "event_type",
            f"generation_ingested mode requires event_type=='generation_ingested'; got {record.get('event_type')!r}",
        ))
    if record.get("review_status") != "pending":
        errors.append(err("review_status", f"generation ingest requires pending; got {record.get('review_status')!r}"))
    if record.get("image_origin") != "generation":
        errors.append(err("image_origin", f"generation ingest requires image_origin=='generation'; got {record.get('image_origin')!r}"))

    for field in (
        "job_id",
        "intent_id",
        "prompt_id",
        "target_id",
        "asset_id",
        "base_concept",
        "model",
        "model_version",
        "platform",
        "generation_model",
        "rendered_prompt",
        "file_path",
        "original_file_path",
        "sha256",
        "ingested_at",
    ):
        require_string(record, field, errors, allow_empty=field in {"base_concept", "rendered_prompt"})

    if "asset_event_timestamp" in record and not is_iso8601(record["asset_event_timestamp"]):
        errors.append(err("asset_event_timestamp", "must be ISO 8601 string"))
    if "ingested_at" in record and not is_iso8601(record["ingested_at"]):
        errors.append(err("ingested_at", "must be ISO 8601 string"))
    if "output_index" in record and not (isinstance(record["output_index"], int) and not isinstance(record["output_index"], bool)):
        errors.append(err("output_index", "must be integer"))

    for field in ("world_state", "tone"):
        if field in record and record[field] is not None:
            vocab = WORLD_STATES if field == "world_state" else TONES
            if record[field] not in vocab:
                errors.append(err(field, f"must be one of {sorted(vocab)} or null"))

    score_status = record.get("score_status")
    if score_status not in SCORE_STATUSES:
        errors.append(err("score_status", f"must be one of {sorted(SCORE_STATUSES)}"))

    score_raw = record.get("brain_initial_score_raw")
    taste = record.get("taste_alignment")
    gold = record.get("brain_initial_gold_similarity")
    anti = record.get("brain_initial_anti_similarity")
    rank = record.get("brain_initial_rank")
    for field, value in (
        ("taste_alignment", taste),
        ("brain_initial_score_raw", score_raw),
        ("brain_initial_gold_similarity", gold),
        ("brain_initial_anti_similarity", anti),
    ):
        if not is_number_or_null(value):
            errors.append(err(field, "must be number or null (boolean rejected)"))
    if rank is not None and rank not in RANKS:
        errors.append(err("brain_initial_rank", f"must be one of {sorted(RANKS)} or null"))
    if score_status != "scored":
        for field, value in (
            ("taste_alignment", taste),
            ("brain_initial_score_raw", score_raw),
            ("brain_initial_gold_similarity", gold),
            ("brain_initial_anti_similarity", anti),
            ("brain_initial_rank", rank),
        ):
            if value is not None:
                errors.append(err(field, "must be null unless score_status is 'scored'"))
    else:
        if score_raw is None or taste is None or gold is None or anti is None or rank is None:
            errors.append(err("score_status", "scored rows require taste/raw/gold/anti/rank values"))
        else:
            if abs(score_raw - taste) > 1e-9:
                errors.append(err("taste_alignment", "must equal brain_initial_score_raw"))
            if abs(score_raw - (gold - anti)) > 1e-9:
                errors.append(err("brain_initial_score_raw", "must equal brain_initial_gold_similarity - brain_initial_anti_similarity"))
            expected_rank = rank_from_score(score_raw)
            if rank != expected_rank:
                errors.append(err("brain_initial_rank", f"must derive from brain_initial_score_raw; expected {expected_rank!r}"))


def validate_alignment(record, errors):
    validate_common(record, errors)
    for field in GROUP_D_FIELDS:
        if field not in record:
            errors.append(err(field, "required Group D field missing"))

    if record.get("event_type") != "alignment":
        errors.append(err("event_type", f"mode 'alignment' requires event_type=='alignment'; got {record.get('event_type')!r}"))

    if "pre_eval_timestamp" in record and not is_iso8601(record["pre_eval_timestamp"]):
        errors.append(err("pre_eval_timestamp", "must be ISO 8601 string"))
    if "final_eval_timestamp" in record and not is_iso8601(record["final_eval_timestamp"]):
        errors.append(err("final_eval_timestamp", "must be ISO 8601 string"))
    if "computed_at" in record and not is_iso8601(record["computed_at"]):
        errors.append(err("computed_at", "must be ISO 8601 string"))

    score = record.get("alignment_score")
    if not (isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= score <= 1):
        errors.append(err("alignment_score", "must be number in [0, 1]"))

    if "alignment_phase" in record and not is_in_vocab(record["alignment_phase"], ALIGNMENT_PHASES):
        errors.append(err("alignment_phase", f"must be one of {sorted(ALIGNMENT_PHASES)}"))

    if "alignment_breakdown" in record and not isinstance(record["alignment_breakdown"], dict):
        errors.append(err("alignment_breakdown", "must be object/dict"))

    require_string(record, "weighting_version", errors)


MODE_EXPECTED_EVENT_TYPE = {
    "generation_ingested": "generation_ingested",
    "perception": "perception",
    "pre_eval": "pre_eval",
    "final_eval": "final_eval",
    "embed_ready": "final_eval",
    "alignment": "alignment",
}

AUTO_EVENT_TYPE_TO_MODE = {
    "generation_ingested": "generation_ingested",
    "perception": "perception",
    "pre_eval": "pre_eval",
    "final_eval": "final_eval",
    "embedded": "lifecycle_event",
    "alignment": "alignment",
}


def enforce_mode_event_type(record, mode, errors):
    expected = MODE_EXPECTED_EVENT_TYPE.get(mode)
    if expected is None:
        return
    actual = record.get("event_type")
    if actual != expected:
        errors.append(err(
            "event_type",
            f"mode {mode!r} requires event_type=={expected!r}; got {actual!r}",
        ))


def validate_record(record, mode):
    errors = []

    if mode == "auto":
        event_type = record.get("event_type")
        mode = AUTO_EVENT_TYPE_TO_MODE.get(event_type)
        if mode is None:
            errors.append(err("_mode", f"cannot auto-route unknown event_type {event_type!r}"))
            return {"ok": False, "mode": "auto", "errors": errors}

    if mode is None:
        et = record.get("event_type")
        if et in LIFECYCLE_BUMP_EVENT_TYPES:
            mode = "lifecycle_event"
        else:
            errors.append(err(
                "_mode",
                "no --mode specified and event_type is not a known lifecycle bump; "
                "specify --mode {auto, generation_ingested, perception, pre_eval, final_eval, embed_ready, lifecycle_event, alignment}",
            ))
            return {"ok": False, "mode": None, "errors": errors}

    if mode == "generation_ingested":
        validate_generation_ingested(record, errors)
    elif mode == "perception":
        validate_common(record, errors)
        enforce_mode_event_type(record, mode, errors)
        validate_group_a(record, errors)
    elif mode == "pre_eval":
        validate_common(record, errors)
        require_created_by(record, errors)
        enforce_mode_event_type(record, mode, errors)
        validate_group_a(record, errors)
        validate_group_b(record, errors)
    elif mode == "final_eval":
        validate_common(record, errors)
        require_created_by(record, errors)
        enforce_mode_event_type(record, mode, errors)
        validate_group_a(record, errors)
        validate_group_c(record, errors)
        if any(f in record for f in GROUP_B_FIELDS):
            validate_group_b(record, errors)
    elif mode == "embed_ready":
        enforce_mode_event_type(record, mode, errors)
        validate_embed_ready(record, errors)
    elif mode == "lifecycle_event":
        validate_lifecycle_event(record, errors)
    elif mode == "alignment":
        require_created_by(record, errors)
        validate_alignment(record, errors)
    else:
        errors.append(err("_mode", f"unknown mode {mode!r}"))

    return {"ok": len(errors) == 0, "mode": mode, "errors": errors}


def unique_event_key(record):
    return {
        "event_type": record.get("event_type"),
        "session_id": record.get("session_id"),
        "image_id": record.get("image_id"),
    }


def same_event_key(existing, key):
    return (
        existing.get("event_type") == key["event_type"]
        and existing.get("session_id") == key["session_id"]
        and existing.get("image_id") == key["image_id"]
    )


def append_unique_jsonl(record, path):
    """Append a validated record once per (event_type, session_id, image_id).

    Logs remain append-only, but retries should not create duplicate lock-event
    rows. Malformed existing lines are ignored here because validation/reporting
    of the full log is handled by --jsonl.
    """
    path = Path(path)
    key = unique_event_key(record)
    if not all(key.values()):
        return {
            "path": str(path),
            "status": "error",
            "key": key,
            "error": "record must have event_type, session_id, and image_id for idempotent append",
        }

    if path.exists():
        with path.open() as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if same_event_key(existing, key):
                    return {
                        "path": str(path),
                        "status": "skipped_duplicate",
                        "key": key,
                        "existing_line": line_num,
                    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return {"path": str(path), "status": "appended", "key": key}


def main():
    parser = argparse.ArgumentParser(description="Validate evaluation records against benchmark/SCHEMA.md.")
    parser.add_argument(
        "--mode",
        choices=[
            "auto",
            "generation_ingested",
            "perception",
            "pre_eval",
            "final_eval",
            "embed_ready",
            "lifecycle_event",
            "alignment",
        ],
        default=None,
        help="Validation mode (`auto` routes each record by event_type; omitted mode only auto-detects lifecycle bumps)",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", help="Read a single JSON record from this file")
    src.add_argument("--jsonl", help="Validate every line of this JSONL file")
    parser.add_argument(
        "--append-jsonl",
        help=(
            "After validating a single record, append it idempotently to this JSONL path. "
            "Skips instead of appending when event_type + session_id + image_id already exists."
        ),
    )
    args = parser.parse_args()

    if args.append_jsonl and args.jsonl:
        parser.error("--append-jsonl can only be used with a single record from --file or stdin, not --jsonl")

    if args.jsonl:
        any_errors = False
        with open(args.jsonl) as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    print(json.dumps({"line": line_num, "ok": False, "errors": [err("_json", str(e))]}))
                    any_errors = True
                    continue
                result = validate_record(record, args.mode)
                result["line"] = line_num
                print(json.dumps(result))
                if not result["ok"]:
                    any_errors = True
        sys.exit(1 if any_errors else 0)

    if args.file:
        raw = Path(args.file).read_text()
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        print(json.dumps({"ok": False, "mode": args.mode, "errors": [err("_input", "empty input")]}))
        sys.exit(1)

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "mode": args.mode, "errors": [err("_json", str(e))]}))
        sys.exit(1)

    result = validate_record(record, args.mode)
    if result["ok"] and args.append_jsonl:
        result["append"] = append_unique_jsonl(record, args.append_jsonl)
        if result["append"].get("status") == "error":
            result["ok"] = False
            result["errors"].append(err("_append", result["append"]["error"]))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
