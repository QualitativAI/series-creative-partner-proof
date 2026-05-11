# Flow Arm Handoff Result Manifest Update

Date: 2026-05-01

Audience: Flow Arm agent on the MacBook Pro

Purpose: update the completed Track 4.B validation job result manifests to the finalized Track 2.A `handoff-result.v1` contract, without regenerating images.

---

## Summary

The Flow Arm execution path worked:

- Jobs were claimed.
- Images were generated and written to `SeriesHandoff/results/incoming/`.
- Packets moved to `SeriesHandoff/jobs/completed/`.
- Status sidecars were updated to `handoff_status: "completed"`.

The remaining issue is only the result manifest shape.

The manifests currently use the older minimal Flow Arm shape:

```json
{
  "job_id": "job-4b-flowarm-validation-001",
  "model": "nano-banana-pro",
  "platform": "google-flow",
  "completed_at": "2026-05-01T08:18:19Z",
  "prompts_completed": [
    {
      "prompt_id": "p01",
      "file_paths": [
        "prompt-p01/nano-banana-pro_job-4b-flowarm-validation-001_p01_img01_20260501.jpeg"
      ]
    }
  ],
  "errors": []
}
```

Track 2.A finalized a richer result manifest contract after the older Flow Arm-side instructions were written. Brain ingestion now expects `handoff-result.v1`.

Do not regenerate images. Rewrite only the existing `manifest.json` files.

---

## Jobs To Repair

Repair both of these jobs:

```text
job-4b-flowarm-validation-001
job-4b-flowarm-validation-002
```

Aaron intentionally ran two jobs. The second job exists because the first generation was not recorded on video, so `job-4b-flowarm-validation-002` was run as a recording pass. Treat both as intentional completed validation jobs.

---

## Files To Read For Each Job

For each `<job_id>`, read:

```text
/workspace/handoff/jobs/completed/<job_id>.json
/workspace/handoff/jobs/status/<job_id>.status.json
/workspace/handoff/results/incoming/<job_id>/manifest.json
/workspace/handoff/results/incoming/<job_id>/prompt-p01/<image-file>
```

On the Mac Studio host, these same files correspond to:

```text
SeriesAgent/SeriesHandoff/jobs/completed/<job_id>.json
SeriesAgent/SeriesHandoff/jobs/status/<job_id>.status.json
SeriesAgent/SeriesHandoff/results/incoming/<job_id>/manifest.json
SeriesAgent/SeriesHandoff/results/incoming/<job_id>/prompt-p01/<image-file>
```

---

## Files To Rewrite

Rewrite these files in place:

```text
/workspace/handoff/results/incoming/job-4b-flowarm-validation-001/manifest.json
/workspace/handoff/results/incoming/job-4b-flowarm-validation-002/manifest.json
```

Do not move the job packets again.

Do not edit `packet_status`.

Do not regenerate images.

---

## Why This Is Missing

The MacBook Pro Flow Arm side was working from the older Flow Arm Plan 05 result-manifest contract. That older contract returned a minimal manifest with top-level `model`, `platform`, `prompts_completed[].file_paths`, and `errors`.

Track 2.A finalized a richer Brain/Flow Arm handoff contract so Brain-side ingestion can preserve:

- job lineage
- packet revision
- prompt lineage
- target lineage
- model and platform metadata
- rendered prompt text
- asset dimensions
- asset MIME type
- asset hash
- success / partial / failure state

Without the richer shape, Brain has to guess too much during ingestion.

---

## Required Final Manifest Shape

Each repaired manifest must use this shape:

```json
{
  "schema_version": "handoff-result.v1",
  "manifest_type": "series_flowarm_result",
  "job_id": "<job_id>",
  "intent_id": "<from completed packet>",
  "packet_revision": 2,
  "source_packet_path": "jobs/completed/<job_id>.json",
  "handoff_status": "completed",
  "result_status": "success",
  "created_at": "<manifest repair/write time, ISO8601Z>",
  "dispatched_at": "<from status sidecar>",
  "claimed_at": "<from status sidecar>",
  "completed_at": "<from status sidecar>",
  "completed_by": "flowarm",
  "output_root": "results/incoming/<job_id>",
  "prompts_completed": [
    {
      "prompt_id": "p01",
      "base_concept": "<from completed packet prompt>",
      "world_state": "<from completed packet prompt>",
      "tone": "<from completed packet prompt>",
      "targets_completed": [
        {
          "target_id": "p01-t01",
          "model": "nano-banana-pro",
          "model_version": "<from completed packet target>",
          "platform": "google-flow",
          "created_by": "nano-banana-pro",
          "generation_model": "nano-banana-pro",
          "rendered_prompt": "<from completed packet target>",
          "assets": [
            {
              "asset_id": "<job_id>_p01_t01_img01",
              "output_index": 1,
              "file_path": "results/incoming/<job_id>/prompt-p01/<image-file>",
              "mime_type": "image/jpeg",
              "width": 2752,
              "height": 1536,
              "image_origin": "generation",
              "event_timestamp": "<status completed_at or exact capture time>",
              "sha256": "<sha256 hash of image file>"
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

---

## Field Mapping

Use this mapping when rewriting each manifest:

| New field | Source |
| --- | --- |
| `schema_version` | Literal `handoff-result.v1` |
| `manifest_type` | Literal `series_flowarm_result` |
| `job_id` | Completed packet or old manifest |
| `intent_id` | `jobs/completed/<job_id>.json` |
| `packet_revision` | `jobs/completed/<job_id>.json` |
| `source_packet_path` | Literal `jobs/completed/<job_id>.json` |
| `handoff_status` | Literal `completed` |
| `result_status` | `success` if all requested images exist |
| `created_at` | Current repair/write time in ISO8601Z |
| `dispatched_at` | Status sidecar |
| `claimed_at` | Status sidecar |
| `completed_at` | Status sidecar |
| `completed_by` | Literal `flowarm` |
| `output_root` | Literal `results/incoming/<job_id>` |
| `prompt_id` | Completed packet prompt |
| `base_concept` | Completed packet prompt |
| `world_state` | Completed packet prompt |
| `tone` | Completed packet prompt |
| `target_id` | Completed packet target |
| `model` | Completed packet target |
| `model_version` | Completed packet target |
| `platform` | Completed packet target |
| `created_by` | Completed packet target |
| `generation_model` | Usually same as `model`, here `nano-banana-pro` |
| `rendered_prompt` | Completed packet target |
| `asset_id` | Stable ID such as `<job_id>_p01_t01_img01` |
| `output_index` | `1` for the first image |
| `file_path` | Relative to `/workspace/handoff`, not relative to manifest |
| `mime_type` | `image/jpeg` |
| `width` | Actual image width, currently `2752` |
| `height` | Actual image height, currently `1536` |
| `image_origin` | Literal `generation` |
| `event_timestamp` | Status sidecar `completed_at`, unless a more precise capture time exists |
| `sha256` | SHA-256 hash of the image bytes |
| `failures` | Empty list for success |
| `warnings` | Empty list unless there are non-blocking warnings |

---

## Existing Image Facts

The Mac Studio side verified these images as valid JPEGs:

```text
job-4b-flowarm-validation-001:
  file: results/incoming/job-4b-flowarm-validation-001/prompt-p01/nano-banana-pro_job-4b-flowarm-validation-001_p01_img01_20260501.jpeg
  format: jpeg
  width: 2752
  height: 1536
  sha256: 87d1856cdb21dd8b140690ea7248227358e512604ca3476489093c64d32ad4dd

job-4b-flowarm-validation-002:
  file: results/incoming/job-4b-flowarm-validation-002/prompt-p01/nano-banana-pro_job-4b-flowarm-validation-002_p01_img01_20260501.jpeg
  format: jpeg
  width: 2752
  height: 1536
  sha256: 87a556d141552fea33d807bf6f1a6c33ce6080f5a08c1d7d5567a91561291958
```

---

## Important Rules

- Do not regenerate images.
- Do not move packets again.
- Do not edit Brain-owned `packet_status`.
- Do not depend on PIL/Pillow alone for image dimensions. Preferred finalization is `python /workspace/flowarm/scripts/finalize_result.py <job_id>`, which falls back from PIL/Pillow to ImageMagick `identify`, `file`, `sips`, and finally pure-Python image header parsing with JPEG support.
- Do not use the old top-level `errors` key.
- Use top-level `failures` and `warnings` instead.
- Do not use the old `prompts_completed[].file_paths` shape.
- Use `prompts_completed[].targets_completed[].assets[]`.
- `file_path` must be relative to `/workspace/handoff`.
- `source_packet_path` must point to `jobs/completed/<job_id>.json`.
- `result_status` must be one of `success`, `partial`, or `failed`.
- Use `success` only if every requested image exists and is listed.
- Use `partial` if some requested images exist and some failed.
- Use `failed` only if no usable outputs were produced.
- If `partial` or `failed`, describe missing or failed attempts in `failures[]`.
- If `success`, use `"failures": []`.
- Keep the status sidecar as `handoff_status: "completed"`.
- It is okay to update only `last_updated_at` in the status sidecar if you want to record the manifest repair time.

---

## Validation Checklist

After rewriting each manifest, verify:

1. `manifest.json` parses as JSON.
2. Top-level fields include:

   ```text
   schema_version
   manifest_type
   job_id
   intent_id
   packet_revision
   source_packet_path
   handoff_status
   result_status
   created_at
   dispatched_at
   claimed_at
   completed_at
   completed_by
   output_root
   prompts_completed
   failures
   warnings
   ```

3. `schema_version` is exactly:

   ```text
   handoff-result.v1
   ```

4. `manifest_type` is exactly:

   ```text
   series_flowarm_result
   ```

5. `handoff_status` is exactly:

   ```text
   completed
   ```

6. `result_status` is exactly:

   ```text
   success
   ```

7. There is no top-level `errors` key.
8. There is no `prompts_completed[].file_paths` key.
9. Every completed target uses `targets_completed[].assets[]`.
10. Every asset listed in `targets_completed[].assets[]` exists on disk.
11. Every asset has:

   ```text
   asset_id
   output_index
   file_path
   mime_type
   width
   height
   image_origin
   event_timestamp
   sha256
   ```

12. The image `sha256` in the manifest matches the actual image file.

Once both manifests are rewritten to this shape, Brain can ingest them.
