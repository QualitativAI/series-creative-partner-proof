#!/usr/bin/env python3
"""Reseat visual anchors after Aaron revises anchor labels.

This is intentionally a Brain-side operator script. It should be run in the
Series Brain runtime, where chromadb is already installed and where the original
visual_anchors collection was created.

Default input is the corrected anchor worksheet:
    benchmark/anchors/manifest.draft.md

The script compares Aaron's corrected labels against manifest.json and then:
- moves files between benchmark/anchors/{gold,anti,aspirational,inbox}
- appends revision final_eval rows with a stable relabel session_id
- updates manifest.json
- updates or deletes Chroma visual_anchors entries

It does not re-embed unchanged pixels. Anchor-to-anchor changes are metadata
updates; anchor-to-none changes delete from Chroma.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


LABELS = {"none", "gold", "anti", "aspirational"}
ANCHOR_LABELS = {"gold", "anti", "aspirational"}
WORLD_STATES = {"flourishing", "sacred", "broken", "corrupted", "abandoned", "harsh", "neutral", "dna-core"}
TONES = {"hopeful", "awe-filled", "mournful", "eerie", "tense", "oppressive", "still", "neutral"}
DEFAULT_RELABEL_SESSION_ID = "2026-05-01T18:00:00Z"


def default_root() -> Path:
    if Path("/workspace/series-vault").exists():
        return Path("/workspace/series-vault")
    return Path(__file__).resolve().parents[2]


ROOT = default_root()
SCRIPTS = ROOT / "benchmark" / "scripts"
ANCHORS = ROOT / "benchmark" / "anchors"
DRAFT_MD = ANCHORS / "manifest.draft.md"
DRAFT_JSONL = ANCHORS / "manifest.draft.jsonl"
MANIFEST = ANCHORS / "manifest.json"
FINAL_LOG = ROOT / "benchmark" / "logs" / "final_eval_history.jsonl"
TMP = ROOT / "benchmark" / "tmp" / "anchor_relabel"
CHROMA_PATH = ROOT / "benchmark" / "chroma_data"
COLLECTION_NAME = "visual_anchors"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def clean_block(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.strip() == ">":
            continue
        if line.lstrip().startswith(">"):
            line = line.lstrip()[1:].lstrip()
        out.append(line.rstrip())
    return "\n".join(out).strip()


def parse_worksheet(path: Path) -> dict[str, dict]:
    text = path.read_text()
    sections = re.split(r"(?m)^## ", text)[1:]
    parsed = {}
    for sec in sections:
        lines = sec.splitlines()
        filename = lines[0].strip()
        image_id_m = re.search(r"Image ID:\s*`([^`]+)`", sec)
        if not image_id_m:
            raise ValueError(f"{filename}: missing Image ID")
        image_id = image_id_m.group(1)

        def grab_until(label: str, next_labels: list[str]) -> str:
            alternatives = "|".join(re.escape(x) for x in next_labels + ["Brain baseline prediction:"])
            pat = re.compile(re.escape(label) + r"\s*(.*?)(?=\n(?:" + alternatives + r")|\Z)", re.S)
            m = pat.search(sec)
            return m.group(1).strip() if m else ""

        final_label = grab_until(
            "Aaron final label:",
            ["Aaron score 0-10:", "Aaron reason / why this label is right:", "Aaron response to Brain, optional:"],
        )
        final_label = final_label.splitlines()[0].strip().lower() if final_label else ""
        score_raw = grab_until(
            "Aaron score 0-10:",
            ["Aaron reason / why this label is right:", "Aaron response to Brain, optional:"],
        )
        score_raw = score_raw.splitlines()[0].strip() if score_raw else ""
        reason = clean_block(grab_until("Aaron reason / why this label is right:", ["Aaron response to Brain, optional:"]))
        response = clean_block(grab_until("Aaron response to Brain, optional:", []))

        if final_label not in LABELS:
            raise ValueError(f"{filename}: final label {final_label!r} not one of {sorted(LABELS)}")
        try:
            score = int(score_raw)
        except Exception as e:
            raise ValueError(f"{filename}: invalid score {score_raw!r}") from e
        if not (0 <= score <= 10):
            raise ValueError(f"{filename}: score out of range {score}")
        if not reason:
            raise ValueError(f"{filename}: missing Aaron reason")

        parsed[image_id] = {
            "filename": filename,
            "image_id": image_id,
            "label": final_label,
            "score": score,
            "reason": reason,
            "response": response,
        }
    return parsed


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"anchors": {}}
    manifest = json.loads(MANIFEST.read_text())
    manifest.setdefault("anchors", {})
    return manifest


def latest_final_eval_rows() -> dict[str, dict]:
    latest = {}
    for row in read_jsonl(FINAL_LOG):
        if row.get("event_type") == "final_eval" and row.get("review_status") == "confirmed":
            latest[row.get("image_id")] = row
    return latest


def preeval_rows() -> dict[str, dict]:
    rows = {}
    for row in read_jsonl(DRAFT_JSONL):
        rows[row["image_id"]] = row
    return rows


def quality_from_label_score(label: str, score: int) -> str:
    if label == "anti":
        return "bad"
    if label == "aspirational":
        return "aspirational"
    if label == "gold":
        return "approved" if score >= 9 else "great"
    if score <= 3:
        return "bad"
    if score <= 6:
        return "okay"
    if score == 7:
        return "great"
    return "approved"


def infer_world_tone(base: dict, reason: str, response: str) -> tuple[str, str]:
    text = f"{reason}\n{response}".lower()
    world = base.get("world_state") or base.get("brain_initial_world_state")
    tone = base.get("tone") or base.get("brain_initial_tone")
    if world not in WORLD_STATES:
        world = "neutral"
    if tone not in TONES:
        tone = "neutral"
    for candidate in WORLD_STATES:
        if re.search(r"\b" + re.escape(candidate) + r"\b", text):
            world = candidate
            break
    for candidate in TONES:
        if re.search(r"\b" + re.escape(candidate) + r"\b", text):
            tone = candidate
            break
    return world, tone


def failure_from_label_quality(label: str, quality: str, reason: str) -> str | None:
    low = reason.lower()
    if quality in {"great", "approved", "aspirational", "canon"}:
        return None
    if any(word in low for word in ("execution", "artifact", "hands", "anatomy")):
        return "execution"
    if label == "anti" or quality == "bad":
        return "concept"
    return "partial"


def tags_from_feedback(label: str, reason: str, response: str) -> str:
    low = f"{reason}\n{response}".lower()
    tags = []

    def add(condition: bool, tag: str) -> None:
        if condition and tag not in tags:
            tags.append(tag)

    add(label == "anti", "feels-grafted")
    add(label == "gold", "feels-native")
    add(label == "aspirational", "resonance-strong")
    add("anime" in low or "animated" in low, "reading-anime")
    add("modern" in low or "real world" in low, "too-real-world")
    add("composition" in low or "framing" in low or "depth" in low, "composition-strong")
    add("lighting" in low or "light" in low, "lighting-signal")
    add("detail" in low or "texture" in low or "material" in low, "materiality-tactile")
    add("generic" in low, "reading-generic-fantasy")
    add("color" in low or "palette" in low, "palette-signal")
    return ", ".join(tags[:10])


def feedback_text(item: dict) -> str:
    if item["response"]:
        return (
            "Aaron reason / why this label is right:\n"
            f"{item['reason']}\n\nAaron response to Brain, optional:\n{item['response']}"
        )
    return item["reason"]


def final_notes(item: dict, old_label: str | None) -> str:
    prefix = f"Anchor relabel revision. Previous anchor_promotion: {old_label or 'none'}."
    body = item["reason"] if not item["response"] else f"{item['reason']}\n\nAaron response to Brain: {item['response']}"
    return f"{prefix}\n\n{body}"


def vault_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def find_current_file(filename: str) -> Path | None:
    for folder in ("gold", "anti", "aspirational", "inbox"):
        candidate = ANCHORS / folder / filename
        if candidate.exists():
            return candidate
    return None


def move_file(filename: str, target_label: str, dry_run: bool) -> tuple[str | None, str]:
    current = find_current_file(filename)
    if current is None:
        raise FileNotFoundError(f"{filename}: not found in anchor folders or inbox")
    target_folder = "inbox" if target_label == "none" else target_label
    target = ANCHORS / target_folder / filename
    if current == target:
        return None, str(target)
    if target.exists():
        raise FileExistsError(f"{filename}: target already exists: {target}")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(target))
    return f"{current} -> {target}", str(target)


def build_revision_record(
    base: dict,
    item: dict,
    old_label: str | None,
    new_source_path: str,
    session_id: str,
) -> dict:
    label = item["label"]
    quality = quality_from_label_score(label, item["score"])
    world, tone = infer_world_tone(base, item["reason"], item["response"])
    now = utc_now()
    record = dict(base)
    record.update(
        {
            "schema_version": "v1",
            "session_id": session_id,
            "event_type": "final_eval",
            "review_status": "confirmed",
            "event_timestamp": now,
            "final_eval_timestamp": now,
            "filename": item["filename"],
            "source_path": new_source_path,
            "image_origin": "anchor_seed",
            "created_by": record.get("created_by") or "midjourney",
            "aaron_score": item["score"],
            "quality_tier": quality,
            "world_state": world,
            "tone": tone,
            "fits_current_scene": False if label == "aspirational" else ("n-a" if label in {"anti", "none"} else True),
            "failure_mode": failure_from_label_quality(label, quality, item["reason"]),
            "feedback_tags": tags_from_feedback(label, item["reason"], item["response"]),
            "feedback_text": feedback_text(item),
            "anchor_promotion": label,
            "canon_candidate": False,
            "final_notes": final_notes(item, old_label),
        }
    )
    return record


def manifest_entry(record: dict) -> dict:
    return {
        "image_id": record["image_id"],
        "filename": record["filename"],
        "source_path": record["source_path"].replace(str(ROOT) + "/", ""),
        "anchor_type": record["anchor_promotion"],
        "created_by": record.get("created_by", "unknown"),
        "image_origin": record.get("image_origin", "anchor_seed"),
        "world_state": record["world_state"],
        "tone": record["tone"],
        "quality_tier": record["quality_tier"],
        "aaron_score": int(record["aaron_score"]),
        "notes": record["final_notes"],
        "session_id": record["session_id"],
        "final_eval_timestamp": record["final_eval_timestamp"],
        "schema_version": record["schema_version"],
    }


def chroma_metadata(entry: dict) -> dict:
    return {
        "image_id": entry["image_id"],
        "filename": entry["filename"],
        "source_path": entry["source_path"],
        "anchor_type": entry["anchor_type"],
        "created_by": entry.get("created_by", "unknown"),
        "image_origin": entry.get("image_origin", "anchor_seed"),
        "world_state": entry["world_state"],
        "tone": entry["tone"],
        "quality_tier": entry["quality_tier"],
        "aaron_score": int(entry["aaron_score"]),
        "session_id": entry["session_id"],
        "final_eval_timestamp": entry["final_eval_timestamp"],
        "schema_version": entry["schema_version"],
    }


def validate_append(record: dict, dry_run: bool) -> str:
    TMP.mkdir(parents=True, exist_ok=True)
    fp = TMP / f"{Path(record['filename']).stem}.relabel.json"
    if not dry_run:
        fp.write_text(json.dumps(record, indent=2, ensure_ascii=True) + "\n")
    else:
        fp.write_text(json.dumps(record, indent=2, ensure_ascii=True) + "\n")
    cmd = [
        sys.executable,
        str(SCRIPTS / "validate_eval.py"),
        "--mode",
        "final_eval",
        "--file",
        str(fp),
    ]
    if not dry_run:
        cmd += ["--append-jsonl", str(FINAL_LOG)]
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    try:
        payload = json.loads(proc.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"validate_eval emitted non-json for {record['filename']}: {proc.stdout}\n{proc.stderr}") from e
    if proc.returncode != 0 or not payload.get("ok"):
        raise RuntimeError(f"validation failed for {record['filename']}: {json.dumps(payload, indent=2)}\n{proc.stderr}")
    if dry_run:
        return "validated"
    return payload.get("append", {}).get("status", "appended")


def current_chroma_summary(collection) -> dict:
    count = collection.count()
    data = collection.get(include=["metadatas"])
    metadatas = data.get("metadatas") or []
    by_type = Counter(m.get("anchor_type") for m in metadatas)
    holdouts = [m.get("image_id") for m in metadatas if m.get("image_origin") == "holdout_benchmark"]
    return {"count": count, "by_type": dict(by_type), "holdout_metadata_ids": holdouts}


def build_operations(manifest: dict, worksheet: dict) -> list[dict]:
    operations = []
    anchors = manifest.get("anchors", {})
    for image_id, entry in sorted(anchors.items(), key=lambda kv: kv[1].get("filename", kv[0])):
        item = worksheet.get(image_id)
        if not item:
            continue
        current = entry.get("anchor_type")
        target = item["label"]
        if current != target:
            operations.append(
                {
                    "image_id": image_id,
                    "filename": item["filename"],
                    "old_label": current,
                    "target_label": target,
                }
            )
    return operations


def main() -> int:
    parser = argparse.ArgumentParser(description="Reseat visual anchors after corrected Aaron labels.")
    parser.add_argument("--apply", action="store_true", help="Perform file, manifest, log, and Chroma writes.")
    parser.add_argument("--session-id", default=DEFAULT_RELABEL_SESSION_ID, help="Stable ISO session_id for revision final_eval rows.")
    parser.add_argument("--skip-chroma", action="store_true", help="For local dry-runs only; never use with --apply.")
    args = parser.parse_args()

    if args.apply and args.skip_chroma:
        raise SystemExit("--skip-chroma is only allowed for dry-run checks")

    worksheet = parse_worksheet(DRAFT_MD)
    preevals = preeval_rows()
    latest_final = latest_final_eval_rows()
    manifest = load_manifest()
    operations = build_operations(manifest, worksheet)
    dry_run = not args.apply

    chroma_client = None
    collection = None
    before_chroma = None
    if not args.skip_chroma:
        import chromadb

        chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = chroma_client.get_collection(COLLECTION_NAME)
        before_chroma = current_chroma_summary(collection)

    summary = {
        "ok": True,
        "dry_run": dry_run,
        "session_id": args.session_id,
        "operation_count": len(operations),
        "operations": [],
        "manifest_before": dict(Counter(e.get("anchor_type") for e in manifest.get("anchors", {}).values())),
        "chroma_before": before_chroma,
    }

    for op in operations:
        image_id = op["image_id"]
        item = worksheet[image_id]
        base = latest_final.get(image_id) or preevals.get(image_id)
        if not base:
            raise RuntimeError(f"{item['filename']}: no final_eval or pre_eval base row found")

        moved, target_abs = move_file(item["filename"], item["label"], dry_run=dry_run)
        new_source_path = str(target_abs) if str(target_abs).startswith("/workspace/") else vault_relative(Path(target_abs))
        if not new_source_path.startswith("/workspace/") and Path(target_abs).is_absolute():
            new_source_path = vault_relative(Path(target_abs))
        record = build_revision_record(base, item, op["old_label"], new_source_path, args.session_id)
        append_status = validate_append(record, dry_run=dry_run)

        manifest_update = "unchanged"
        chroma_update = "skipped"
        if not dry_run:
            if item["label"] == "none":
                manifest["anchors"].pop(image_id, None)
                manifest_update = "removed"
                collection.delete(ids=[image_id])
                chroma_update = "deleted"
            else:
                entry = manifest_entry(record)
                manifest["anchors"][image_id] = entry
                manifest_update = "updated"
                collection.update(ids=[image_id], metadatas=[chroma_metadata(entry)])
                chroma_update = "metadata_updated"

        summary["operations"].append(
            {
                **op,
                "file_move": moved,
                "append_status": append_status,
                "manifest_update": manifest_update,
                "chroma_update": chroma_update,
            }
        )

    if not dry_run:
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n")

    after_manifest = load_manifest() if not dry_run else manifest
    summary["manifest_after"] = dict(Counter(e.get("anchor_type") for e in after_manifest.get("anchors", {}).values()))
    summary["manifest_anchor_count"] = len(after_manifest.get("anchors", {}))
    if collection is not None:
        summary["chroma_after"] = current_chroma_summary(collection)
    else:
        summary["chroma_after"] = None

    folder_counts = {}
    for folder in ("anti", "gold", "aspirational", "inbox"):
        folder_counts[folder] = len(list((ANCHORS / folder).glob("seed_*.png")))
    summary["folder_counts"] = folder_counts
    summary["expected_after"] = "omitted from compact proof snapshot"

    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
