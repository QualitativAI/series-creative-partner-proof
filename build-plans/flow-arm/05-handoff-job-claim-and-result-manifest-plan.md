# 05 - Handoff Job Claim And Result Manifest Plan

## Purpose

Define how Flow Arm claims handoff job packets, stages images, writes result manifests, updates machine-readable status, and returns completed work to Brain through the shared handoff folder. This file preserves the handoff contract without giving Flow Arm creative authority.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 2.1, 5.5, 12.17, 13.1, 13.2, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 10.1, 10.2, 16.6, 16.7, 18.1, 18.2, 20

## Prerequisites

- `04-workspace-heartbeat-status-plan.md` has been executed.
- `/workspace/handoff/jobs/outgoing` is visible.
- `/workspace/handoff/jobs/claimed`, `/workspace/handoff/jobs/completed`, `/workspace/handoff/jobs/failed`, and `/workspace/handoff/jobs/status` are visible.
- `/workspace/handoff/results/incoming` is visible.
- Flow Arm has no access to `/workspace/series-vault`.

## Exact Later Execution Steps

1. Job discovery:

   - Flow Arm watches or lists:

     ```text
     /workspace/handoff/jobs/outgoing/
     ```

   - Flow Arm reads the outgoing handoff packet.
   - Flow Arm never writes Brain-owned `packet_status`.

2. Job claim:

   When Aaron types `@FlowArm claim <job_id>` in `#flow-arm-log`, Flow Arm must:

   - Validate that `/workspace/handoff/jobs/outgoing/<job_id>.json` exists.
   - Refuse duplicate claim if the same job exists in `claimed/`, `completed/`, or `failed/`.
   - Move, not copy, the handoff packet:

     ```text
     /workspace/handoff/jobs/outgoing/<job_id>.json
     -> /workspace/handoff/jobs/claimed/<job_id>.json
     ```

   - Do not edit the packet's `packet_status`.
   - Update `/workspace/handoff/jobs/status/<job_id>.status.json`:

     ```json
     {
       "handoff_status": "claimed",
       "claimed_at": "ISO8601Z",
       "last_updated_at": "ISO8601Z",
       "last_updated_by": "flowarm"
     }
     ```

     Preserve existing fields in the status sidecar.

   - Write heartbeat/status:

     ```text
     status: claimed
     current_job: <job_id>
     ```

   - Post in `#flow-arm-log`: `Claimed <job_id>. Beginning execution.`

3. Job packet interpretation:

   - Read `job_id`, `intent_id`, `output_resolution`, `generations_per_prompt`, and `prompts` from `/workspace/handoff/jobs/claimed/<job_id>.json`.
   - For Flow Arm, execute only targets where:

     ```json
     "model": "nano-banana-pro"
     ```

   - Use `rendered_prompt` from the matching target.
   - Preserve `prompt_id`.
   - Do not reinterpret creative intent or rewrite prompts.

4. Staging:

   - For each prompt, stage outputs under:

     ```text
     /workspace/flowarm/staging/<job_id>/prompt-<prompt_id>/
     ```

   - Recommended filename:

     ```text
     nano-banana-pro_<job_id>_<prompt_id>_imgNN_YYYYMMDD.png
     ```

5. Result manifest:

   - Create:

     ```text
     /workspace/flowarm/staging/<job_id>/manifest.json
     ```

   - Required shape:

     ```json
     {
       "job_id": "job-001",
       "model": "nano-banana-pro",
       "platform": "google-flow",
       "completed_at": "ISO8601Z",
       "prompts_completed": [
         {
           "prompt_id": "p01",
           "file_paths": [
             "prompt-p01/nano-banana-pro_job-001_p01_img01_YYYYMMDD.png"
           ]
         }
       ],
       "errors": []
     }
     ```

   - The manifest does not need to duplicate `rendered_prompt`, `world_state`, or `tone`; Brain pulls those from the original job packet.

6. Return result packet:

   - Copy the whole job staging folder to:

     ```text
     /workspace/handoff/results/incoming/<job_id>/
     ```

   - Write heartbeat/status:

     ```text
     status: complete
     current_job: <job_id>
     note: manifest written
     ```

   - Move the handoff packet:

     ```text
     /workspace/handoff/jobs/claimed/<job_id>.json
     -> /workspace/handoff/jobs/completed/<job_id>.json
     ```

   - Update `/workspace/handoff/jobs/status/<job_id>.status.json`:

     ```json
     {
       "handoff_status": "completed",
       "completed_at": "ISO8601Z",
       "last_updated_at": "ISO8601Z",
       "last_updated_by": "flowarm",
       "result_manifest_path": "results/incoming/<job_id>/manifest.json",
       "error": null
     }
     ```

   - Post in `#flow-arm-log`: `<job_id> complete. N images written. Manifest at SeriesHandoff/results/incoming/<job_id>/manifest.json.`

7. Error handling:

   - If a prompt fails, include an `errors` entry with prompt ID and reason.
   - Write status `error`.
   - Preserve partial outputs if any exist.
   - Write `/workspace/handoff/jobs/failed/<job_id>.error.json`.
   - Move the handoff packet from `claimed/` to `failed/` if it has already been claimed.
   - If failure happens before the move to `claimed/`, leave the packet in `outgoing/` and report why the claim did not start.
   - Update `/workspace/handoff/jobs/status/<job_id>.status.json` with `handoff_status: "failed"`, `failed_at`, `last_updated_at`, `last_updated_by: "flowarm"`, and `error`.
   - Post the failure reason in `#flow-arm-log`.

8. Truth and recovery:

   - Folder position is operational truth.
   - `/workspace/handoff/jobs/status/<job_id>.status.json` is audit truth.
   - If folder position and sidecar disagree, trust folder position and report/log the discrepancy for Brain in `#brain-ops-troubleshooting`.
   - Do not repair by guessing. If a repair is needed, ask Aaron or Brain for the intended state.

## Files And Folders Expected

```text
/workspace/handoff/jobs/outgoing/<job_id>.json
/workspace/handoff/jobs/claimed/<job_id>.json
/workspace/handoff/jobs/completed/<job_id>.json
/workspace/handoff/jobs/failed/<job_id>.json
/workspace/handoff/jobs/failed/<job_id>.error.json
/workspace/handoff/jobs/status/<job_id>.status.json
/workspace/flowarm/staging/<job_id>/manifest.json
/workspace/handoff/results/incoming/<job_id>/manifest.json
/workspace/handoff/results/incoming/<job_id>/prompt-<prompt_id>/<image files>
```

## Aaron Manual Stop Points

- Aaron should be notified if a job packet has no `nano-banana-pro` target.
- Aaron should be notified if Google Flow/Nano Banana Pro fails for a prompt.
- Aaron should be notified when a job is complete and returned to handoff.

## Validation Commands

Inside `flowchat`, after Brain places a fake job:

```text
List /workspace/handoff/jobs/outgoing and /workspace/handoff/jobs/status. Summarize job-001.json and job-001.status.json without editing packet_status.
```

After fake Flow Arm output:

```text
Run: find /workspace/handoff/jobs -maxdepth 2 -type f | sort
Run: find /workspace/handoff/results/incoming/job-001 -maxdepth 3 -type f | sort
Run: cat /workspace/handoff/jobs/status/job-001.status.json
Run: cat /workspace/handoff/results/incoming/job-001/manifest.json
```

Expected:

- `jobs/completed/job-001.json` exists after completion
- `jobs/outgoing/job-001.json` no longer exists after claim
- status sidecar says `handoff_status: "completed"`
- original packet does not use claimed or completed as `packet_status` values
- manifest includes:

```text
job_id
model
platform
prompts_completed
prompt_id
file_paths
```

## Expected Outputs

- Flow Arm can claim/read handoff jobs without Brain vault access.
- Flow Arm can update machine-readable status without changing Brain `packet_status`.
- Brain can ingest returned result manifests.
- Prompt lineage remains intact through `prompt_id` and job packet lookup.

## Failure Handling

- If result files are missing, do not write `complete` or `handoff_status: "completed"`.
- If manifest paths do not match actual files, fix before notifying Brain.
- If sync is delayed, wait and verify before rerunning the job.
- If a job is malformed, write an error status and notify Aaron/Brain.
- If status sidecar is missing at claim time, stop and ask Brain/Aaron to repair dispatch instead of inventing a fresh job record, unless Aaron explicitly approves Flow Arm creating a recovery sidecar.

## Explicit Do Not Do Notes

- Do not edit Brain job packets in place.
- Do not write `packet_status`.
- Do not rewrite prompts.
- Do not write Chroma metadata.
- Do not decide quality tiers.
- Do not mark canon or promote anchors.
