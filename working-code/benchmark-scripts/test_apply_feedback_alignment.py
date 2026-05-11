"""Regression tests for apply_feedback.py -> compute_alignment.py routing.

These tests pin the Track 3.C integration contract:
- confirmed feedback is appended to feedback.jsonl, final_eval_history.jsonl,
  and generations.jsonl;
- compute_alignment.py can see the final_eval_history row;
- reruns are idempotent;
- partial duplicate state across the three feedback sinks fails loudly.

Run:
    python3 benchmark/scripts/test_apply_feedback_alignment.py
"""

import json
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import apply_feedback
import compute_alignment
import promote_generated_anchors


SCRIPT_DIR = Path(__file__).resolve().parent
APPLY_FEEDBACK = SCRIPT_DIR / "apply_feedback.py"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def write_manifest(vault: Path, anchors: dict | None = None) -> None:
    manifest = vault / "benchmark" / "anchors" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"schema_version": "v1", "anchors": anchors or {}}, indent=2) + "\n")


def build_pre_eval(image_id: str = "sha256:abcdef1234567890") -> dict:
    return {
        "schema_version": "v1",
        "session_id": "2026-05-01T21:41:54Z",
        "image_id": image_id,
        "filename": "test4c.jpeg",
        "source_path": "assets/images/generated/jobs/test/test4c.jpeg",
        "image_origin": "generation",
        "created_by": "nano-banana-pro",
        "event_type": "pre_eval",
        "review_status": "pre_evaluated",
        "event_timestamp": "2026-05-01T22:37:32Z",
        "perception_model": "gemini-3-flash-preview",
        "perception_model_version": None,
        "perception_prompt_version": "v1",
        "perception_timestamp": "2026-05-01T22:37:25Z",
        "perception_text": "test perception",
        "perception_subject": "test subject",
        "perception_composition": "test composition",
        "perception_dominant_colors": ["green", "grey"],
        "perception_visible_text": "",
        "perception_spatial_layout": "test layout",
        "perception_atmosphere": "test atmosphere",
        "perception_notable_details": "test details",
        "perception_possible_state_cues": "test state cues",
        "perception_possible_tone_cues": "test tone cues",
        "taste_alignment": 0.12,
        "brain_initial_score_raw": 0.12,
        "brain_initial_gold_similarity": 0.61,
        "brain_initial_anti_similarity": 0.49,
        "brain_initial_rank": "likely-miss",
        "score_status": "scored",
        "score_error": None,
        "brain_initial_timestamp": "2026-05-01T22:37:32Z",
        "brain_initial_quality_tier": "approved",
        "brain_initial_world_state": "sacred",
        "brain_initial_tone": "awe-filled",
        "brain_initial_scene_fit": True,
        "brain_initial_failure_mode": None,
        "brain_initial_tags": "test, gold",
        "brain_initial_notes": "test pre-eval",
        "brain_initial_anchor_promotion_recommendation": "gold",
        "brain_initial_canon_candidate": False,
        "brain_initial_confidence": {
            "quality_tier": "high",
            "world_state": "high",
            "tone": "high",
            "anchor_promotion": "high",
        },
        "brain_initial_questions_or_flags": None,
    }


def build_feedback(image_id: str) -> dict:
    return {
        "feedback": [
            {
                "image_id": image_id,
                "aaron_score": 9,
                "quality_tier": "approved",
                "world_state": "sacred",
                "tone": "awe-filled",
                "fits_current_scene": True,
                "failure_mode": None,
                "feedback_tags": ["test", "gold"],
                "feedback_text": "Confirmed in regression test.",
                "anchor_promotion": "gold",
                "canon_candidate": False,
                "final_notes": "Regression test final notes.",
                "event_timestamp": "2026-05-01T23:00:00Z",
            }
        ]
    }


def run_apply_feedback(tmp_path: Path, pending_path: Path) -> subprocess.CompletedProcess:
    logs = tmp_path / "benchmark" / "logs"
    return subprocess.run(
        [
            sys.executable,
            str(APPLY_FEEDBACK),
            str(pending_path),
            "--generations-log",
            str(logs / "generations.jsonl"),
            "--feedback-log",
            str(logs / "feedback.jsonl"),
            "--final-eval-log",
            str(logs / "final_eval_history.jsonl"),
            "--skip-chroma",
            "--skip-anchor-promotion",
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def run_apply_feedback_with_anchor_preflight(tmp_path: Path, pending_path: Path) -> subprocess.CompletedProcess:
    logs = tmp_path / "benchmark" / "logs"
    env = dict(os.environ)
    env["SERIES_VAULT_ROOT"] = str(tmp_path)
    return subprocess.run(
        [
            sys.executable,
            str(APPLY_FEEDBACK),
            str(pending_path),
            "--generations-log",
            str(logs / "generations.jsonl"),
            "--feedback-log",
            str(logs / "feedback.jsonl"),
            "--final-eval-log",
            str(logs / "final_eval_history.jsonl"),
            "--skip-chroma",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text().splitlines())


class ApplyFeedbackAlignmentTests(unittest.TestCase):
    def test_non_promoted_feedback_does_not_require_manifest_preflight(self):
        with tempfile.TemporaryDirectory(prefix="series-anchor-preflight-none-") as temp_dir:
            tmp_path = Path(temp_dir)
            logs = tmp_path / "benchmark" / "logs"
            pre = build_pre_eval("sha256:abcdef1234567893")
            feedback = build_feedback(pre["image_id"])
            feedback["feedback"][0]["anchor_promotion"] = "none"
            write_jsonl(logs / "generations.jsonl", [pre])
            write_jsonl(logs / "feedback.jsonl", [])
            write_jsonl(logs / "final_eval_history.jsonl", [])
            pending = tmp_path / "pending-feedback.json"
            pending.write_text(json.dumps(feedback, indent=2) + "\n")

            result = run_apply_feedback_with_anchor_preflight(tmp_path, pending)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["anchor_promotion_preflight"]["candidate_count"], 0)
            self.assertEqual(summary["feedback_applied"], 1)
            self.assertEqual(line_count(logs / "feedback.jsonl"), 1)
            self.assertEqual(line_count(logs / "final_eval_history.jsonl"), 1)
            self.assertEqual(line_count(logs / "generations.jsonl"), 2)

    def test_anchor_preflight_source_missing_prevents_any_jsonl_append(self):
        with tempfile.TemporaryDirectory(prefix="series-anchor-preflight-missing-") as temp_dir:
            tmp_path = Path(temp_dir)
            logs = tmp_path / "benchmark" / "logs"
            write_manifest(tmp_path)
            pre = build_pre_eval("sha256:abcdef1234567892")
            write_jsonl(logs / "generations.jsonl", [pre])
            write_jsonl(logs / "feedback.jsonl", [])
            write_jsonl(logs / "final_eval_history.jsonl", [])
            pending = tmp_path / "pending-feedback.json"
            pending.write_text(json.dumps(build_feedback(pre["image_id"]), indent=2) + "\n")

            result = run_apply_feedback_with_anchor_preflight(tmp_path, pending)
            self.assertNotEqual(result.returncode, 0)
            error = json.loads(result.stderr)
            self.assertEqual(error["stage"], "anchor_promotion_preflight")
            self.assertEqual(error["failed_image_ids"], [pre["image_id"]])
            self.assertIn("no JSONL rows were appended", error["error"])
            self.assertEqual(line_count(logs / "feedback.jsonl"), 0)
            self.assertEqual(line_count(logs / "final_eval_history.jsonl"), 0)
            self.assertEqual(line_count(logs / "generations.jsonl"), 1)

    def test_generated_anchor_preflight_dry_run_does_not_create_anchor_dirs_or_files(self):
        with tempfile.TemporaryDirectory(prefix="series-anchor-dry-run-") as temp_dir:
            vault = Path(temp_dir)
            write_manifest(vault)
            source = vault / "assets/images/generated/jobs/test/test4c.jpeg"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"generated gold anchor fixture")
            image_id = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()[:16]
            record = build_pre_eval(image_id)
            record.update(
                {
                    "event_type": "final_eval",
                    "review_status": "confirmed",
                    "source_path": "assets/images/generated/jobs/test/test4c.jpeg",
                    "event_timestamp": "2026-05-01T23:00:00Z",
                    "final_eval_timestamp": "2026-05-01T23:00:00Z",
                    "aaron_score": 9,
                    "quality_tier": "approved",
                    "world_state": "sacred",
                    "tone": "awe-filled",
                    "fits_current_scene": True,
                    "failure_mode": None,
                    "feedback_tags": "test, gold",
                    "feedback_text": "Confirmed in regression test.",
                    "anchor_promotion": "gold",
                    "canon_candidate": False,
                    "final_notes": "Confirmed gold.",
                }
            )

            result = promote_generated_anchors.promote_records([record], vault_root=vault, dry_run=True)
            self.assertEqual(result["failed"], 0, result)
            self.assertEqual(result["would_promote"], 1)
            self.assertFalse((vault / "benchmark/anchors/gold").exists())
            self.assertFalse((vault / "benchmark/anchors/gold/test4c.jpeg").exists())

    def test_anchor_preflight_destination_collision_with_mismatched_content_fails(self):
        with tempfile.TemporaryDirectory(prefix="series-anchor-collision-") as temp_dir:
            vault = Path(temp_dir)
            write_manifest(vault)
            source = vault / "assets/images/generated/jobs/test/test4c.jpeg"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"generated gold anchor fixture")
            image_id = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()[:16]
            conflicting_dest = vault / "benchmark/anchors/gold/test4c.jpeg"
            conflicting_dest.parent.mkdir(parents=True, exist_ok=True)
            conflicting_dest.write_bytes(b"different already-promoted fixture")
            record = build_pre_eval(image_id)
            record.update(
                {
                    "event_type": "final_eval",
                    "review_status": "confirmed",
                    "source_path": "assets/images/generated/jobs/test/test4c.jpeg",
                    "event_timestamp": "2026-05-01T23:00:00Z",
                    "final_eval_timestamp": "2026-05-01T23:00:00Z",
                    "aaron_score": 9,
                    "quality_tier": "approved",
                    "world_state": "sacred",
                    "tone": "awe-filled",
                    "fits_current_scene": True,
                    "failure_mode": None,
                    "feedback_tags": "test, gold",
                    "feedback_text": "Confirmed in regression test.",
                    "anchor_promotion": "gold",
                    "canon_candidate": False,
                    "final_notes": "Confirmed gold.",
                }
            )

            result = promote_generated_anchors.preflight_records([record], vault_root=vault)
            self.assertEqual(result["failed"], 1, result)
            self.assertEqual(result["results"][0]["image_id"], image_id)
            self.assertIn("destination filename exists with different content", result["results"][0]["error"])
            self.assertEqual(list((vault / "benchmark/anchors/gold").glob("*")), [conflicting_dest])

    def test_feedback_routes_to_final_eval_history_and_alignment(self):
        with tempfile.TemporaryDirectory(prefix="series-feedback-alignment-") as temp_dir:
            tmp_path = Path(temp_dir)
            logs = tmp_path / "benchmark" / "logs"
            charts = tmp_path / "benchmark" / "charts"
            pre = build_pre_eval()
            write_jsonl(logs / "generations.jsonl", [pre])
            write_jsonl(logs / "pre_eval_history.jsonl", [pre])
            write_jsonl(logs / "final_eval_history.jsonl", [])
            pending = tmp_path / "pending-feedback.json"
            pending.write_text(json.dumps(build_feedback(pre["image_id"]), indent=2) + "\n")

            result = run_apply_feedback(tmp_path, pending)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["feedback_applied"], 1)
            self.assertEqual(summary["feedback_log_appended"], 1)
            self.assertEqual(summary["final_eval_log_appended"], 1)
            self.assertEqual(summary["generations_appended"], 1)

            compute_alignment.PRE_EVAL_LOG = logs / "pre_eval_history.jsonl"
            compute_alignment.FINAL_EVAL_LOG = logs / "final_eval_history.jsonl"
            compute_alignment.ALIGNMENT_LOG = logs / "alignment.jsonl"
            compute_alignment.CHARTS_DIR = charts
            compute_alignment.ALIGNMENT_CHART = charts / "alignment_score_by_session.png"
            compute_alignment.PROMOTION_CHART = charts / "promotion_precision_recall.png"
            alignment = compute_alignment.compute_alignment()
            self.assertTrue(alignment["ok"])
            self.assertEqual(alignment["alignment_rows"], 1)
            self.assertEqual(alignment["skipped"]["missing_ground_truth"], 0)

            rerun = run_apply_feedback(tmp_path, pending)
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            rerun_summary = json.loads(rerun.stdout)
            self.assertEqual(rerun_summary["duplicates_skipped"], 1)
            self.assertEqual(rerun_summary["feedback_applied"], 0)
            self.assertEqual(line_count(logs / "feedback.jsonl"), 1)
            self.assertEqual(line_count(logs / "final_eval_history.jsonl"), 1)
            self.assertEqual(line_count(logs / "generations.jsonl"), 2)
            self.assertEqual(line_count(logs / "alignment.jsonl"), 1)

    def test_partial_duplicate_state_fails(self):
        with tempfile.TemporaryDirectory(prefix="series-feedback-partial-") as temp_dir:
            tmp_path = Path(temp_dir)
            logs = tmp_path / "benchmark" / "logs"
            pre = build_pre_eval("sha256:abcdef1234567891")
            final = dict(pre)
            final.update(
                {
                    "event_type": "final_eval",
                    "review_status": "confirmed",
                    "event_timestamp": "2026-05-01T23:00:00Z",
                    "final_eval_timestamp": "2026-05-01T23:00:00Z",
                    "aaron_score": 9,
                    "quality_tier": "approved",
                    "world_state": "sacred",
                    "tone": "awe-filled",
                    "fits_current_scene": True,
                    "failure_mode": None,
                    "feedback_tags": "test, gold",
                    "feedback_text": "Confirmed in regression test.",
                    "anchor_promotion": "gold",
                    "canon_candidate": False,
                    "final_notes": "Regression test final notes.",
                }
            )
            write_jsonl(logs / "generations.jsonl", [pre, final])
            write_jsonl(logs / "feedback.jsonl", [final])
            write_jsonl(logs / "final_eval_history.jsonl", [])
            pending = tmp_path / "pending-feedback.json"
            pending.write_text(json.dumps(build_feedback(pre["image_id"]), indent=2) + "\n")

            result = run_apply_feedback(tmp_path, pending)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("partial duplicate state", result.stderr)

    def test_chroma_metadata_update_reports_missing_ids_truthfully(self):
        class FakeCollection:
            def __init__(self):
                self.ids = {"sha256:abcdef1234567890"}
                self.updated = []

            def get(self, ids):
                return {"ids": [image_id for image_id in ids if image_id in self.ids]}

            def update(self, ids, metadatas):
                self.updated.extend(ids)

        existing = build_pre_eval("sha256:abcdef1234567890")
        missing = build_pre_eval("sha256:abcdef1234567891")
        result = apply_feedback.update_existing_chroma_metadata(FakeCollection(), [existing, missing])
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["updated_ids"], ["sha256:abcdef1234567890"])
        self.assertEqual(result["missing_ids"], ["sha256:abcdef1234567891"])

    def test_generated_promoted_anchor_is_copied_to_matching_anchor_folder(self):
        with tempfile.TemporaryDirectory(prefix="series-generated-anchor-") as temp_dir:
            vault = Path(temp_dir)
            source = vault / "assets/images/generated/jobs/test/test4c.jpeg"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"generated anti anchor fixture")
            image_id = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()[:16]
            record = build_pre_eval(image_id)
            record.update(
                {
                    "event_type": "final_eval",
                    "review_status": "confirmed",
                    "source_path": "assets/images/generated/jobs/test/test4c.jpeg",
                    "event_timestamp": "2026-05-01T23:00:00Z",
                    "final_eval_timestamp": "2026-05-01T23:00:00Z",
                    "aaron_score": 1,
                    "quality_tier": "bad",
                    "world_state": "sacred",
                    "tone": "still",
                    "fits_current_scene": False,
                    "failure_mode": "execution",
                    "feedback_tags": "too-real",
                    "feedback_text": "Too realistic.",
                    "anchor_promotion": "anti",
                    "canon_candidate": False,
                    "final_notes": "Confirmed anti.",
                }
            )

            promoted, copy_result = promote_generated_anchors.anchor_copy_record(
                record,
                vault,
                vault / "benchmark/anchors",
            )
            dest = vault / promoted["source_path"]
            self.assertTrue(dest.exists())
            self.assertEqual(dest.parent, vault / "benchmark/anchors/anti")
            self.assertEqual(copy_result["reason"], "copied")
            self.assertEqual(promoted["image_id"], image_id)
            self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest()[:16], image_id.split(":", 1)[1])


if __name__ == "__main__":
    unittest.main()
