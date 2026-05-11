# 05 - Job Packet And Handoff Contract Plan

## Purpose

Define the Brain-side job packet lifecycle and the handoff contract that Flow Arm will use later. This does not build Flow Arm. It ensures the Brain emits and ingests structured files using the active four-state Brain lifecycle and the separate Flow Arm handoff status contract.

## Track 2.A Final Contract Amendment

Track 2.A finalizes this plan as the V1 packet/handoff contract. The contract has three durable artifacts:

1. **Brain job packet** — authored and owned by Brain in `working/job-packets/`.
2. **Handoff status sidecar** — created by Brain at dispatch, then updated by Flow Arm as audit state in the canonical runtime handoff mount at `/workspace/handoff/jobs/status/` (host path `SeriesAgent/SeriesHandoff/jobs/status/`).
3. **Result manifest** — authored by Flow Arm under `/workspace/handoff/results/incoming/<job_id>/manifest.json`; later parsed by Brain-side ingestion and review-packet scripts.

Folder position remains operational truth for Flow Arm handoff state. The status sidecar is audit truth. `packet_status` remains Brain-only and is never written by Flow Arm.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 2.1, 5.5, 8, 12.4, 13.1, and 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 3, 10, 16, 18, and 20

## Prerequisites

- `01-vault-and-source-pack-plan.md` has created the vault structure.
- `02-brain-sandbox-and-hermes-plan.md` has mounted the handoff folder at `/workspace/handoff`.
- `04-chroma-embeddings-and-anchor-plan.md` has created scoring scripts or Boot Clean-safe placeholders.

## Exact Later Execution Steps

1. Use the full job packet schema. Do not compress it during implementation:

   ```json
   {
     "schema_version": "handoff.v1",
     "packet_type": "series_review_job_packet",
     "job_id": "job-XXX",
     "intent_id": "intent-XXX",
     "objective": "short description",
     "packet_status": "draft",
     "packet_revision": 1,
     "created_at": "ISO8601",
     "last_preflight_at": null,
     "preflight_notes": null,
     "approved_for_dispatch_by_aaron": false,
     "output_resolution": "2k",
     "generations_per_prompt": 4,
     "result_manifest_path": "results/incoming/job-XXX/manifest.json",
     "prompts": [
       {
         "prompt_id": "p01",
         "base_concept": "model-neutral creative intent",
         "world_state": "sacred",
         "tone": "still",
         "targets": [
           {
             "target_id": "p01-t01",
             "model": "nano-banana-pro",
             "model_version": "v1",
             "platform": "google-flow",
             "created_by": "nano-banana-pro",
             "playbook_ref": "prompting/playbooks/nano-banana-pro.md",
             "experiment_ref": "prompting/experiments/nano-banana-pro.md",
             "rendered_prompt": "model-specific prompt"
           },
           {
             "target_id": "p01-t02",
             "model": "gpt-image-2",
             "model_version": "current",
             "platform": "openai-oauth",
             "created_by": "gpt-image-2",
             "playbook_ref": "prompting/playbooks/gpt-image-2.md",
             "experiment_ref": "prompting/experiments/gpt-image-2.md",
             "rendered_prompt": "model-specific prompt"
           }
         ]
       }
     ]
   }
   ```

   `generations_per_prompt` means generations per prompt target. A packet with 1 prompt, 2 targets, and `generations_per_prompt: 2` expects 4 successful assets unless the result manifest is `partial` or `failed` and describes the missing attempts in `failures[]`.

2. Use four Brain-owned lifecycle states:

   ```text
   draft
   ready
   dispatched
   archived
   ```

   `packet_status` is Brain-owned. Flow Arm never writes `packet_status`, and the handoff protocol must never use claimed or completed as Brain packet states. On completion and ingestion, Brain moves or copies the historical vault packet into `working/job-packets/archived/` with `packet_status: "archived"`.

3. Use separate handoff states for Flow Arm:

   ```text
   outgoing
   claimed
   completed
   failed
   ```

   These are represented by handoff folder position and by an audit sidecar at:

   ```text
   /workspace/handoff/jobs/status/<job_id>.status.json
   ```

   Folder position is operational truth. The status sidecar is audit truth. If they disagree, Brain trusts folder position, treats the sidecar as stale, and reports/logs the discrepancy in `#brain-ops-troubleshooting`.

4. Brain queue folders:

   ```text
   working/job-packets/drafts/
   working/job-packets/ready/
   working/job-packets/dispatched/
   working/job-packets/archived/
   ```

5. Draft behavior:

   - Brain creates a draft in `working/job-packets/drafts/`.
   - `packet_status` is `draft`.
   - `approved_for_dispatch_by_aaron` is `false`.
   - Brain does not dispatch automatically.

6. Ready behavior:

   - Aaron approves the draft for preflight.
   - Brain moves the file to `working/job-packets/ready/`.
   - `packet_status` becomes `ready`.
   - `approved_for_dispatch_by_aaron` can become `true` only if Aaron explicitly approved.

7. Preflight protocol:

   - Read the ready packet.
   - Read `prompting/playbooks/<model>.md` for each target model.
   - Read `prompting/experiments/<model>.md` for each target model.
   - Check relevant recent feedback from logs.
   - Preserve `base_concept`.
   - Update only target-specific `rendered_prompt` fields if current evidence justifies it.
   - Increment `packet_revision`.
   - Update `last_preflight_at`.
   - Write `preflight_notes` explaining changes or stating why no changes were made.
   - Ask Aaron for explicit dispatch approval.

8. Dispatch behavior:

   - After Aaron approves dispatch, Brain moves the packet to:

     ```text
     working/job-packets/dispatched/
     ```

   - Brain also copies the same dispatched packet to:

     ```text
     /workspace/handoff/jobs/outgoing/
     ```

   - This dual-location rule is mandatory. The in-vault dispatched copy preserves Brain history; the handoff copy is what Flow Arm claims later.
   - Brain also creates the handoff status skeleton:

     ```text
     /workspace/handoff/jobs/status/<job_id>.status.json
     ```

     Required shape:

     ```json
     {
       "schema_version": "handoff-status.v1",
       "job_id": "job-XXX",
       "handoff_status": "outgoing",
       "created_at": "ISO8601",
       "dispatched_at": "ISO8601",
       "claimed_at": null,
       "completed_at": null,
       "failed_at": null,
       "last_updated_at": "ISO8601",
       "last_updated_by": "brain",
       "result_manifest_path": "results/incoming/job-XXX/manifest.json",
       "error": null
     }
     ```

9. Archive behavior:

   - After ingestion, review packet creation, feedback application as applicable, and alignment summary, Brain moves or copies final historical packet into `working/job-packets/archived/`.
   - Set `packet_status: "archived"`.
   - Do not create a separate `completed/` folder.

10. Incoming result manifest contract for Flow Arm:

   Flow Arm writes the result manifest after generation files have been placed under:

   ```text
   /workspace/handoff/results/incoming/<job_id>/
   ```

   The manifest path is the same path Brain wrote into the job packet and status sidecar:

   ```text
   /workspace/handoff/results/incoming/<job_id>/manifest.json
   ```

   Required shape:

   ```json
   {
     "schema_version": "handoff-result.v1",
     "manifest_type": "series_flowarm_result",
     "job_id": "job-XXX",
     "intent_id": "intent-XXX",
     "packet_revision": 2,
     "source_packet_path": "jobs/completed/job-XXX.json",
     "handoff_status": "completed",
     "result_status": "success",
     "created_at": "ISO8601",
     "dispatched_at": "ISO8601",
     "claimed_at": "ISO8601",
     "completed_at": "ISO8601",
     "completed_by": "flowarm",
     "output_root": "results/incoming/job-XXX",
     "prompts_completed": [
       {
         "prompt_id": "p01",
         "base_concept": "model-neutral creative intent",
         "world_state": "sacred",
         "tone": "still",
         "targets_completed": [
           {
             "target_id": "p01-t01",
             "model": "nano-banana-pro",
             "model_version": "v1",
             "platform": "google-flow",
             "created_by": "nano-banana-pro",
             "generation_model": "nano-banana-pro",
             "rendered_prompt": "model-specific prompt",
             "assets": [
               {
                 "asset_id": "job-XXX_p01_t01_img01",
                 "output_index": 1,
                 "file_path": "results/incoming/job-XXX/prompt-p01/nano-banana-pro/job-XXX_p01_t01_img01.png",
                 "mime_type": "image/png",
                 "width": 2048,
                 "height": 2048,
                 "image_origin": "generation",
                 "event_timestamp": "ISO8601",
                 "sha256": null
               }
             ]
           }
         ]
       }
     ],
     "failures": [],
     "warnings": []
   }
   ```

   The result manifest is intentionally richer than a bare `file_paths` list. Track 1.C `ingest_batch.py` must be able to flatten every `targets_completed[].assets[]` entry into one generated-image record with at least:

   ```text
   job_id
   intent_id
   prompt_id
   target_id
   base_concept
   world_state
   tone
   model
   model_version
   platform
   created_by
   generation_model
   rendered_prompt
   output_index
   file_path
   image_origin
   event_timestamp
   ```

   Ingest computes `image_id` from file bytes, calls the perception/pre-eval/scoring flow, and writes `taste_alignment` after scoring. Flow Arm does not write `image_id`, `taste_alignment`, Brain evaluation fields, Aaron evaluation fields, or `packet_status`.

   `result_status` values:

   ```text
   success
   partial
   failed
   ```

   A partial manifest is valid only when successful assets are listed and the failed target or asset attempts are described in `failures[]`.

11. Downstream artifact: `review-packet.v1`

   After Brain has a result manifest or ingested generated-image rows, `create_review_packet.py` writes a Brain-internal visual review packet at:

   ```text
   reviews/visual/jobs/<job_id>/review-manifest.json
   reviews/visual/jobs/<job_id>/images/
   ```

   This artifact is downstream of the dispatch/handoff contract. It is not a JSONL eval-history log and must not masquerade as one. Packet items use packet-native field names for packet state and asset timing; eval-history fields such as `event_type`, `review_status`, `event_timestamp`, `session_id`, and per-item `schema_version` are not written into `review-packet.v1` items.

   Required top-level shape:

   ```json
   {
     "schema_version": "review-packet.v1",
     "compatible_eval_schema_version": "v1",
     "manifest_type": "series_visual_review_packet",
     "job_id": "job-XXX",
     "intent_id": "intent-XXX",
     "created_at": "ISO8601",
     "source_type": "result_manifest",
     "source_path": "path/to/source/manifest-or-log",
     "image_count": 1,
     "image_dir": "images",
     "packet_review_status_counts": {"pending": 1},
     "schema_field_summary": {
       "required_review_item_fields_present": true,
       "missing_by_image": {},
       "uses_reconciled_score_fields": true
     },
     "items": []
   }
   ```

   Each item represents one generated asset copied into the review packet:

   ```json
   {
     "packet_item_type": "generated_asset",
     "packet_review_status": "pending",
     "image_id": "sha256:<first 16 hex chars>",
     "filename": "job-XXX_p01_t01_img01.png",
     "source_path": "results/incoming/job-XXX/prompt-p01/nano-banana-pro/job-XXX_p01_t01_img01.png",
     "review_image_path": "images/job-XXX_p01_t01_img01.png",
     "original_file_path": "/absolute/path/resolved/by/Brain",
     "image_origin": "generation",
     "asset_event_timestamp": "ISO8601",
     "source_result_created_at": "ISO8601",
     "job_id": "job-XXX",
     "intent_id": "intent-XXX",
     "prompt_id": "p01",
     "target_id": "p01-t01",
     "asset_id": "job-XXX_p01_t01_img01",
     "output_index": 1,
     "base_concept": "model-neutral creative intent",
     "world_state": "sacred",
     "tone": "still",
     "model": "nano-banana-pro",
     "model_version": "v1",
     "platform": "google-flow",
     "created_by": "nano-banana-pro",
     "generation_model": "nano-banana-pro",
     "rendered_prompt": "model-specific prompt",
     "mime_type": "image/png",
     "width": 2048,
     "height": 2048,
     "sha256": "full asset hash when available",
     "brain_initial_score_raw": null,
     "brain_initial_gold_similarity": null,
     "brain_initial_anti_similarity": null,
     "brain_initial_rank": null
   }
   ```

   The packet keeps full job/prompt/target/model lineage and the reconciled Brain score field names. Feedback application and lightbox generation remain owned by their own scripts and logs; `review-packet.v1` does not include speculative `pending_feedback`, `feedback_contract`, `lightbox_fields`, or `lightbox_contract` structures unless those downstream scripts are explicitly changed to consume them.

12. Fake validation job:

    - Create a complete fake job packet with the full schema above.
    - Use only four lifecycle states.
    - Use exact state/tone vocabulary.
    - Simulate Flow Arm result files under `/workspace/handoff/results/incoming/job-001/`.
    - Use fake images, not real generation, for the first pipeline test.
    - Track 2.A example files live under non-operational examples folders:

      ```text
      working/job-packets/examples/round-trip/
      working/job-packets/examples/round-trip/handoff/
      ```

      These examples mirror live queue paths without placing fake work in operational queues.
      The `handoff/` subfolder is documentation-only and stands in for the canonical runtime handoff mount (`/workspace/handoff`, host path `SeriesAgent/SeriesHandoff/`). Do not create a vault-level operational `SeriesHandoff/` folder.

## Files And Folders Expected

In vault:

```text
working/job-packets/drafts/
working/job-packets/ready/
working/job-packets/dispatched/
working/job-packets/archived/
```

In handoff:

```text
/workspace/handoff/jobs/outgoing/
/workspace/handoff/jobs/claimed/
/workspace/handoff/jobs/completed/
/workspace/handoff/jobs/failed/
/workspace/handoff/jobs/status/
/workspace/handoff/results/incoming/
/workspace/handoff/flowarm-status/
```

Dual status folders:

```text
/workspace/series-vault/flowarm-status/
/workspace/handoff/flowarm-status/
```

## Aaron Manual Stop Points

- Aaron must approve moving a real draft packet to ready.
- Aaron must approve dispatch after preflight.
- Aaron must decide whether a job uses only Flow Arm, only GPT Image 2, or both.
- Aaron must confirm archive/completion semantics if they ever need to change; default is `packet_status: "archived"`.

## Validation Commands

Confirm queues:

```text
Run: find /workspace/series-vault/working/job-packets -maxdepth 2 -type d | sort
```

Confirm handoff:

```text
Run: find /workspace/handoff -maxdepth 3 -type d | sort
```

Confirm dispatched dual-location after fake dispatch:

```text
Run: ls /workspace/series-vault/working/job-packets/dispatched/job-001.json
Run: ls /workspace/handoff/jobs/outgoing/job-001.json
Run: cat /workspace/handoff/jobs/status/job-001.status.json
```

Expected status sidecar: `handoff_status` is `outgoing`, `last_updated_by` is `brain`, and `result_manifest_path` points to `results/incoming/job-001/manifest.json`.

Confirm archived convention after fake completion:

```text
Run: python - <<'PY'
import json
from pathlib import Path
p = Path('/workspace/series-vault/working/job-packets/archived/job-001.json')
data = json.loads(p.read_text())
print(data.get('packet_status'))
PY
```

Expected: `archived`.

## Expected Outputs

- Every packet has full lineage fields needed by ingestion.
- Flow Arm can claim jobs from `/workspace/handoff/jobs/outgoing/`.
- Brain keeps its own dispatched/archive history inside the vault.
- No one needs to infer whether `completed` is a Brain state or a Flow Arm state; Brain uses `archived`, Flow Arm uses handoff folder/status state.

## Failure Handling

- If Flow Arm cannot see a job, verify the copy to `/workspace/handoff/jobs/outgoing/` and the skeleton at `/workspace/handoff/jobs/status/<job_id>.status.json`.
- If ingestion cannot find prompt metadata, verify the full packet schema was used.
- If a future agent adds `completed` to Brain `packet_status`, revert to the deliberate four-state convention unless Aaron explicitly changes it.

## Explicit Do Not Do Notes

- Do not dispatch without Aaron approval.
- Do not mutate `base_concept` during preflight.
- Do not use a compressed fake packet that omits required lineage fields.
- Do not create `working/job-packets/completed/`.
- Do not let Flow Arm write `packet_status`.
- Do not build Flow Arm here.
