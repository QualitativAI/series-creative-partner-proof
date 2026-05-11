#!/usr/bin/env python3
"""Promote confirmed generated outputs into visual anchors.

Confirmed feedback rows with anchor_promotion in {gold, anti, aspirational}
are decisions to make those images reference anchors. Generated job outputs
need one extra materialization step before embed_anchors.py can accept them:
copy the generated asset into benchmark/anchors/<promotion>/ and run the
existing embed path against that anchor-copy record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import validate_eval


PROMOTED_VALUES = {"gold", "anti", "aspirational"}
SCRIPT_DIR = Path(__file__).resolve().parent
EMBED_ANCHORS = SCRIPT_DIR / "embed_anchors.py"


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
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


def latest_confirmed_rows(rows: list[dict]) -> list[dict]:
    latest = {}
    for index, row in enumerate(rows):
        if row.get("event_type") != "final_eval" or row.get("review_status") != "confirmed":
            continue
        image_id = row.get("image_id")
        if not isinstance(image_id, str):
            continue
        key = (parse_timestamp(row.get("final_eval_timestamp") or row.get("event_timestamp")), index)
        current = latest.get(image_id)
        if current is None or key > current[0]:
            latest[image_id] = (key, row)
    return [row for _, row in latest.values()]


def resolve_vault_path(vault_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        if path.exists():
            return path
        workspace_root = Path("/workspace/series-vault")
        try:
            rel = path.relative_to(workspace_root)
        except ValueError:
            return path
        return vault_root / rel
    return vault_root / raw_path


def vault_relative(vault_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(vault_root))
    except ValueError:
        return str(path)


def short_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def manifest_anchor_ids(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    data = json.loads(manifest_path.read_text())
    anchors = data.get("anchors", {})
    return set(anchors) if isinstance(anchors, dict) else set()


def preflight_manifest_anchor_ids(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found at {manifest_path}")
    data = json.loads(manifest_path.read_text())
    anchors = data.get("anchors")
    if not isinstance(anchors, dict):
        raise ValueError("manifest.json missing or malformed 'anchors' object")
    return set(anchors)


def unique_anchor_destination(anchor_dir: Path, filename: str, image_id: str) -> Path:
    dest = anchor_dir / filename
    if not dest.exists():
        return dest
    expected_short = image_id.split(":", 1)[-1]
    try:
        if short_hash(dest) == expected_short:
            return dest
    except OSError:
        pass
    stem = dest.stem
    suffix = dest.suffix
    return anchor_dir / f"{stem}-{expected_short}{suffix}"


def planned_anchor_copy(record: dict, vault_root: Path, anchor_root: Path) -> tuple[dict, dict]:
    promo = record.get("anchor_promotion")
    image_id = record.get("image_id")
    if promo not in PROMOTED_VALUES:
        return dict(record), {"copied": False, "reason": "not_promoted"}
    if record.get("image_origin") == "holdout_benchmark":
        return dict(record), {"copied": False, "reason": "holdout_benchmark"}

    source = resolve_vault_path(vault_root, record.get("source_path", ""))
    anchor_dir = anchor_root / promo

    expected_folder = f"benchmark/anchors/{promo}/"
    if expected_folder in str(source):
        promoted = dict(record)
        promoted["source_path"] = vault_relative(vault_root, source)
        promoted["filename"] = source.name
        return promoted, {"copied": False, "reason": "already_in_anchor_folder", "anchor_path": str(source)}

    base_dest = anchor_dir / (record.get("filename") or source.name)
    dest = unique_anchor_destination(anchor_dir, record.get("filename") or source.name, image_id)
    expected_short = image_id.split(":", 1)[-1]
    if base_dest.exists() and short_hash(base_dest) != expected_short:
        raise FileExistsError(
            f"{image_id}: destination filename exists with different content: {base_dest}"
        )

    if not source.exists() or not source.is_file():
        if dest.exists():
            if short_hash(dest) != image_id.split(":", 1)[-1]:
                raise FileExistsError(f"{image_id}: destination exists with different content: {dest}")
            promoted = dict(record)
            promoted["source_path"] = vault_relative(vault_root, dest)
            promoted["filename"] = dest.name
            return promoted, {
                "copied": False,
                "reason": "destination_already_present",
                "source_path": str(source),
                "source_exists": False,
                "anchor_path": str(dest),
            }
        raise FileNotFoundError(f"{image_id}: source file not found for anchor promotion: {source}")

    if dest.exists():
        if short_hash(dest) != image_id.split(":", 1)[-1]:
            raise FileExistsError(f"{image_id}: destination exists with different content: {dest}")
        reason = "destination_already_present"
    else:
        reason = "would_copy"

    promoted = dict(record)
    promoted["source_path"] = vault_relative(vault_root, dest)
    promoted["filename"] = dest.name
    return promoted, {
        "copied": False,
        "reason": reason,
        "source_path": str(source),
        "source_exists": True,
        "anchor_path": str(dest),
    }


def anchor_copy_record(record: dict, vault_root: Path, anchor_root: Path, dry_run: bool = False) -> tuple[dict, dict]:
    promoted, copy_plan = planned_anchor_copy(record, vault_root, anchor_root)
    if copy_plan.get("reason") != "would_copy":
        return promoted, copy_plan
    if dry_run:
        dry_result = dict(copy_plan)
        dry_result["reason"] = "dry_run"
        return promoted, dry_result

    source = Path(copy_plan["source_path"])
    dest = Path(copy_plan["anchor_path"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    result = dict(copy_plan)
    result["copied"] = True
    result["reason"] = "copied"
    return promoted, result


def validate_promoted_record_preflight(promoted: dict, source: Path | None, vault_root: Path) -> dict:
    previous_root = validate_eval.VAULT_CONTAINER_ROOT
    validate_eval.VAULT_CONTAINER_ROOT = vault_root
    try:
        final_eval_validation = validate_eval.validate_record(promoted, "final_eval")
        errors = list(final_eval_validation.get("errors", []))
        dest = resolve_vault_path(vault_root, promoted.get("source_path", ""))
        dest_exists = dest.exists() and dest.is_file()
        if dest_exists:
            embed_ready_validation = validate_eval.validate_record(promoted, "embed_ready")
            errors.extend(embed_ready_validation.get("errors", []))
            embed_ready_mode = "full"
        else:
            promo = promoted.get("anchor_promotion")
            expected_folder_part = f"benchmark/anchors/{promo}/"
            if expected_folder_part not in str(dest):
                errors.append({
                    "field": "source_path",
                    "reason": f"planned destination must be in benchmark/anchors/{promo}/",
                })
            declared = promoted.get("image_id")
            if source is None or not source.exists() or not source.is_file():
                errors.append({"field": "source_path", "reason": "source file does not exist for planned copy"})
            elif declared and validate_eval.is_valid_image_id(declared):
                computed = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()[:16]
                if declared != computed:
                    errors.append({
                        "field": "image_id",
                        "reason": f"declared {declared} does not match computed {computed} for {source}",
                    })
            embed_ready_mode = "pre_copy"
        return {
            "ok": not errors,
            "final_eval_validation": final_eval_validation,
            "embed_ready_mode": embed_ready_mode,
            "errors": errors,
        }
    finally:
        validate_eval.VAULT_CONTAINER_ROOT = previous_root


def preflight_records(records: list[dict], vault_root: Path | None = None) -> dict:
    vault_root = vault_root or default_vault_root()
    anchor_root = vault_root / "benchmark" / "anchors"
    manifest_path = anchor_root / "manifest.json"
    candidates = [
        row for row in records
        if row.get("anchor_promotion") in PROMOTED_VALUES
        and row.get("review_status") == "confirmed"
        and row.get("event_type") == "final_eval"
    ]
    if not candidates:
        return {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "would_promote": 0,
            "candidate_count": 0,
            "results": [],
        }

    try:
        existing_anchor_ids = preflight_manifest_anchor_ids(manifest_path)
    except Exception as e:
        return {
            "attempted": 0,
            "succeeded": 0,
            "failed": 1,
            "skipped": 0,
            "would_promote": 0,
            "candidate_count": 0,
            "results": [{
                "ok": False,
                "stage": "manifest_read",
                "error": f"{type(e).__name__}: {e}",
                "manifest_path": str(manifest_path),
            }],
        }

    results = []
    attempted = failed = skipped = would_promote = 0
    for record in candidates:
        image_id = record.get("image_id")
        promo = record.get("anchor_promotion")
        if record.get("image_origin") == "holdout_benchmark":
            skipped += 1
            results.append({"image_id": image_id, "anchor_promotion": promo, "ok": True, "skipped": "holdout_benchmark"})
            continue
        if image_id in existing_anchor_ids:
            skipped += 1
            results.append({"image_id": image_id, "anchor_promotion": promo, "ok": True, "skipped": "already_in_manifest"})
            continue

        attempted += 1
        try:
            promoted, copy_plan = planned_anchor_copy(record, vault_root, anchor_root)
            source = Path(copy_plan["source_path"]) if copy_plan.get("source_path") else None
            validation = validate_promoted_record_preflight(promoted, source, vault_root)
            result = {
                "ok": validation["ok"],
                "stage": "preflight",
                "image_id": image_id,
                "anchor_promotion": promo,
                "copy": copy_plan,
                "promoted_source_path": promoted.get("source_path"),
                "promoted_filename": promoted.get("filename"),
                "embed_ready_mode": validation["embed_ready_mode"],
            }
            if not validation["ok"]:
                result["errors"] = validation["errors"]
        except Exception as e:
            result = {
                "ok": False,
                "stage": "preflight",
                "image_id": image_id,
                "anchor_promotion": promo,
                "error": f"{type(e).__name__}: {e}",
            }

        results.append(result)
        if result.get("ok"):
            would_promote += 1
        else:
            failed += 1

    return {
        "attempted": attempted,
        "succeeded": 0,
        "failed": failed,
        "skipped": skipped,
        "would_promote": would_promote,
        "candidate_count": len(candidates),
        "results": results,
    }


def run_embed(record: dict, vault_root: Path, work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    image_id = record["image_id"].replace(":", "-")
    record_file = work_dir / f"{image_id}.json"
    record_file.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    env = dict(os.environ)
    env["SERIES_VAULT_ROOT"] = str(vault_root)
    proc = subprocess.run(
        [sys.executable, str(EMBED_ANCHORS), "--record-file", str(record_file)],
        cwd=str(vault_root),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        result = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        result = {"ok": False, "stage": "embed_output_parse", "stdout": proc.stdout}
    result["returncode"] = proc.returncode
    if proc.stderr:
        result["stderr"] = proc.stderr
    return result


def promote_records(records: list[dict], vault_root: Path | None = None, dry_run: bool = False) -> dict:
    vault_root = vault_root or default_vault_root()
    if dry_run:
        result = preflight_records(records, vault_root=vault_root)
        result["dry_run"] = True
        return result

    anchor_root = vault_root / "benchmark" / "anchors"
    manifest_path = anchor_root / "manifest.json"
    work_dir = vault_root / "benchmark" / "tmp" / "generated_anchor_promotions"
    existing_anchor_ids = manifest_anchor_ids(manifest_path)

    candidates = [
        row for row in records
        if row.get("anchor_promotion") in PROMOTED_VALUES
        and row.get("review_status") == "confirmed"
        and row.get("event_type") == "final_eval"
    ]
    results = []
    attempted = succeeded = failed = skipped = would_promote = 0
    for record in candidates:
        image_id = record.get("image_id")
        promo = record.get("anchor_promotion")
        if record.get("image_origin") == "holdout_benchmark":
            skipped += 1
            results.append({"image_id": image_id, "anchor_promotion": promo, "ok": True, "skipped": "holdout_benchmark"})
            continue
        if image_id in existing_anchor_ids:
            skipped += 1
            results.append({"image_id": image_id, "anchor_promotion": promo, "ok": True, "skipped": "already_in_manifest"})
            continue

        attempted += 1
        try:
            anchor_record, copy_result = anchor_copy_record(record, vault_root, anchor_root, dry_run=dry_run)
            if dry_run:
                would_promote += 1
                result = {"ok": True, "dry_run": True, "copy": copy_result}
            else:
                result = run_embed(anchor_record, vault_root, work_dir)
                result["copy"] = copy_result
        except Exception as e:
            result = {"ok": False, "stage": "promote_generated_anchor", "error": f"{type(e).__name__}: {e}"}

        result.setdefault("image_id", image_id)
        result.setdefault("anchor_promotion", promo)
        results.append(result)
        if result.get("ok") and not result.get("dry_run"):
            succeeded += 1
            existing_anchor_ids.add(image_id)
        elif not result.get("ok"):
            failed += 1

    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "would_promote": would_promote,
        "candidate_count": len(candidates),
        "results": results,
    }


def main() -> int:
    vault_root = default_vault_root()
    parser = argparse.ArgumentParser(description="Promote confirmed generated outputs into visual anchors.")
    parser.add_argument("--final-eval-log", type=Path, default=vault_root / "benchmark" / "logs" / "final_eval_history.jsonl")
    parser.add_argument("--job-id", help="Only promote confirmed rows whose job_id matches this value.")
    parser.add_argument("--image-id", action="append", default=[], help="Only promote this image_id. Can be repeated.")
    parser.add_argument("--preflight", action="store_true", help="Check promotion readiness without copying, logging, manifest, or Chroma writes.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = latest_confirmed_rows(load_jsonl(args.final_eval_log))
    if args.job_id:
        rows = [row for row in rows if row.get("job_id") == args.job_id or args.job_id in str(row.get("source_path", ""))]
    if args.image_id:
        wanted = set(args.image_id)
        rows = [row for row in rows if row.get("image_id") in wanted]
    result = preflight_records(rows, vault_root=vault_root) if args.preflight else promote_records(
        rows,
        vault_root=vault_root,
        dry_run=args.dry_run,
    )
    print(json.dumps({"ok": result["failed"] == 0, **result}, indent=2, sort_keys=True))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
