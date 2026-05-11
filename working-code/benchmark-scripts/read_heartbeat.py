"""Normalize Flow Arm heartbeat/status sidecar files.

Reads the richer `heartbeat.json` shape first, falling back to `status.json`.
The default path is the Brain container handoff mount, but tests can point the
reader at a fixture directory or one explicit JSON file.

Usage:
    python benchmark/scripts/read_heartbeat.py
    python benchmark/scripts/read_heartbeat.py --status-dir /tmp/flowarm-status
    python benchmark/scripts/read_heartbeat.py --file /tmp/heartbeat.json
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATUS_DIR = Path("/workspace/handoff/flowarm-status")

# Plan 06 requires an age_seconds/stuck normalization, but the active corpus does
# not yet define the V1 threshold. Keep the default visible and overrideable so
# Plan 08/Aaron can ratify or adjust it without changing the sidecar contract.
DEFAULT_STUCK_AFTER_SECONDS = 15 * 60

# Flow Arm Plan 04 status values are idle, claimed, working, complete, error.
# Only in-progress states are eligible for stale-heartbeat detection.
ACTIVE_STATUSES = {"claimed", "working"}


def parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_seconds(timestamp, now=None):
    if timestamp is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, int((now - timestamp).total_seconds()))


def normalize_sidecar(data, stuck_after_seconds=DEFAULT_STUCK_AFTER_SECONDS):
    timestamp = data.get("timestamp")
    parsed_timestamp = parse_timestamp(timestamp)
    age = age_seconds(parsed_timestamp)
    raw_status = data.get("status")
    status = raw_status if isinstance(raw_status, str) else "unknown"

    return {
        "timestamp": timestamp,
        "status": status,
        "profile": data.get("profile"),
        "current_job": data.get("current_job"),
        "current_prompt": data.get("current_prompt"),
        "progress": data.get("progress"),
        "note": data.get("note"),
        "age_seconds": age,
        "stuck": bool(status in ACTIVE_STATUSES and age is not None and age > stuck_after_seconds),
    }


def candidate_files(status_dir):
    return [
        status_dir / "heartbeat.json",
        status_dir / "status.json",
    ]


def missing_result():
    return {"status": "no_heartbeat_file", "stuck": False}


def invalid_result(note):
    return {
        "timestamp": None,
        "status": "invalid_heartbeat_file",
        "profile": None,
        "current_job": None,
        "current_prompt": None,
        "progress": None,
        "note": note,
        "age_seconds": None,
        "stuck": False,
    }


def read_first_available(paths, stuck_after_seconds=DEFAULT_STUCK_AFTER_SECONDS):
    for path in paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return invalid_result(f"invalid JSON in {path}: {e}")
        if not isinstance(data, dict):
            return invalid_result(f"sidecar root must be a JSON object in {path}")
        return normalize_sidecar(data, stuck_after_seconds)
    return missing_result()


def main():
    parser = argparse.ArgumentParser(description="Read and normalize Flow Arm heartbeat/status sidecars.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--status-dir", default=str(DEFAULT_STATUS_DIR), help="Directory containing heartbeat.json/status.json")
    source.add_argument("--file", help="Read one explicit heartbeat or status JSON file")
    parser.add_argument(
        "--stuck-after-seconds",
        type=int,
        default=DEFAULT_STUCK_AFTER_SECONDS,
        help="Mark active statuses stuck when timestamp age exceeds this threshold",
    )
    args = parser.parse_args()

    if args.stuck_after_seconds < 0:
        parser.error("--stuck-after-seconds must be >= 0")

    paths = [Path(args.file)] if args.file else candidate_files(Path(args.status_dir))
    print(json.dumps(read_first_available(paths, args.stuck_after_seconds), indent=2))


if __name__ == "__main__":
    main()
