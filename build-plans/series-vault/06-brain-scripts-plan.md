# 06 - Brain Scripts Plan

## Purpose

Create the deterministic Brain-side Python scripts that make the system work: collection initialization, embedding tests, anchor embedding, scoring, charting, ingestion, feedback application, review packet creation, lightbox creation, alignment summary, and heartbeat/status readers.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 8.6, 9.5, 12.1 through 12.10, 13.1, and 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 7 through 15, 16.5, 18, 19, and 20

## Prerequisites

- Plans 01 through 05 have been executed.
- Python dependencies are installed in the Brain container.
- Chroma collections exist.
- Boot Clean behavior is required even when anchors, logs, handoff files, or generated images do not exist yet.

## Exact Later Execution Steps

1. Ensure these scripts exist in `benchmark/scripts/`:

   ```text
   init_collections.py
   test_embed.py
   embed_anchors.py
   score.py
   search_anchors.py
   make_chart.py
   ingest_batch.py
   apply_feedback.py
   create_review_packet.py
   create_lightbox.py
   rebuild_taste_memory_index.py
   search_taste_memory.py
   inspect_taste_memory.py
   compute_alignment.py
   create_alignment_summary.py
   read_heartbeat.py
   read_flowarm_status.py
   ```

2. `init_collections.py`:

   - Create or open `taste_memory`.
   - Create or open `visual_anchors`.
   - Use persistent path `/workspace/series-vault/benchmark/chroma_data`.
   - Print counts and `Ready.`
   - Must work when collections are empty.

3. `test_embed.py`:

   - Create a small PIL image.
   - Embed via Gemini Embedding 2.
   - Request `output_dimensionality=3072`.
   - Print `Vector length: 3072`.

4. `embed_anchors.py`:

   - Read anchor manifest.
   - Embed images from gold, anti, and aspirational folders.
   - Store flat Chroma metadata only.
   - Tolerate empty aspirational folder.

5. `score.py`:

   - Return full score dict.
   - Define `brain_initial_score_raw = taste_alignment = gold_similarity - anti_similarity`.
   - Return `brain_initial_gold_similarity` and `brain_initial_anti_similarity` as nullable diagnostic fields.
   - Derive `brain_initial_rank` from `brain_initial_score_raw`, not from `gold_similarity`.
   - If no anchors exist, return a clear missing-anchor note, not a crash.
   - If state-specific anchors are sparse, fall back to all gold anchors.

6. `search_anchors.py`:

   - Provide V1 free-text semantic retrieval over seeded anchors only.
   - Embed the query with Gemini Embedding 2 at `output_dimensionality=3072`.
   - Query the Chroma `visual_anchors` collection and return JSON containing:

     ```json
     {
       "ok": true,
       "query": "mountain ranges with sunset lighting",
       "collection": "visual_anchors",
       "count": 2,
       "top_k": 20,
       "matches": [
         {
           "image_id": "img-001",
           "score": 0.84,
           "source_path": "benchmark/anchors/gold/img-001.png",
           "anchor_promotion": "gold"
         }
       ],
       "image_ids": ["img-001", "img-002"]
     }
     ```

   - Return `ok: true`, `count: 0`, empty `matches`, empty `image_ids`, and note `no seeded visual anchors found` when `visual_anchors` is empty.
   - Return `ok: false` JSON with a clear `stage` such as `embed_query` for missing `GEMINI_API_KEY` or query-embedding failure.
   - Empty `visual_anchors` short-circuits before query embedding or API-key validation so Boot Clean retrieval checks can report no seeded anchors without network access.
   - Treat `--top-k` larger than the collection size as valid and return no more matches than exist.
   - Support optional minimum score filtering as a post-query filter over the nearest candidates returned for `--top-k`; the final `count` may be lower than `top_k`.
   - Use cosine-space Chroma collection metadata when creating/opening `visual_anchors` in alternate Chroma paths.
   - Output field `anchor_promotion` is the retrieval-facing name for the seeded anchor metadata value stored in Chroma as `anchor_type`.
   - V1 baseline note: `search_anchors.py` remains seeded-anchor-only and must not itself claim or implement full generated-image semantic search over `taste_memory`.
   - V1 baseline note: Chroma `documents` storage and compact `search_text` indexing are not part of `search_anchors.py`; Aaron's approved V1.1 slice implements those features separately in `taste_memory`.
   - Its JSON `image_ids` array is an accepted handoff file for `create_lightbox.py --image-ids-file`.

7. `make_chart.py`:

   - Read `benchmark/logs/generations.jsonl`.
   - Read `benchmark/logs/alignment.jsonl` when present.
   - If no entries exist, print `No entries yet.` and exit cleanly.
   - After ingestion, write:

     ```text
     benchmark/charts/taste_score_over_time.png
     benchmark/charts/taste_score_by_model.png
     benchmark/charts/alignment_score_by_session.png
     benchmark/charts/promotion_precision_recall.png
     ```

8. `ingest_batch.py`:

   - Ingest Flow Arm results from `/workspace/handoff/results/incoming/<job_id>/`.
   - Provide `ingest_from_gpt(job_id, prompt_mappings)` for Brain-side GPT Image 2 staging.
   - Copy images into the durable master library:

     ```text
     assets/images/generated/jobs/<job_id>/<model>/<prompt_id>/
     ```

   - Preserve lineage without claiming perception or Brain pre-eval has happened:

     ```text
     intent_id -> prompt_id -> model -> model_version -> rendered_prompt -> image_id -> score.py output -> brain_initial_* -> later feedback
     ```

   - Write raw generated assets as `event_type: generation_ingested` with `review_status: pending`; do not fabricate Group A perception fields or Group B creative judgment fields.
   - Validate prompt-intent `world_state` and `tone` if present; fail on invalid values instead of silently coercing them to `neutral`.
   - Refuse manifest/file SHA mismatches by default; allow an explicit override only for isolated repair/testing.
   - `brain_initial_score_raw`, when present from score.py, must be the scalar `taste_alignment` value from `score.py`, where `taste_alignment = gold_similarity - anti_similarity`.
   - Persist `brain_initial_gold_similarity` and `brain_initial_anti_similarity` only as nullable score.py diagnostic numbers, not as proof that Brain pre-eval happened.
   - If scoring is not run, or anchors are absent/incomplete, persist `taste_alignment`, `brain_initial_score_raw`, `brain_initial_gold_similarity`, `brain_initial_anti_similarity`, and `brain_initial_rank` as null with `score_status` explaining the state.
   - `brain_initial_rank` derives from `brain_initial_score_raw` using fixed thresholds:

     ```text
     strong: >= 0.82
     promising: >= 0.72 and < 0.82
     borderline: >= 0.62 and < 0.72
     likely-miss: < 0.62
     ```

   - Chroma metadata must be flat scalars/strings only.

9. `apply_feedback.py`:

   - Read structured feedback JSON.
   - Validate tier, score, and failure mode.
   - Update Chroma metadata.
   - Append `feedback.jsonl`.
   - Append a latest-row feedback event to `generations.jsonl`.
   - Store `feedback_tags` as a comma-separated string in Chroma.
   - Promote to anchors only when feedback explicitly requests `gold`, `anti`, or `aspirational`.

10. `create_review_packet.py`:

   - Read latest row per image ID for the job.
   - Copy images into `reviews/visual/jobs/<job_id>/images/`.
   - Write `review-manifest.json`.
   - Write `aaron-feedback-worksheet.md` in the same review job folder as the human-editable review surface.
   - The worksheet must embed images with review-packet-relative links like `images/<filename>` so Obsidian renders them when the worksheet is opened from the job folder.
   - The worksheet Aaron section must stay compact, matching the holdout worksheet pattern: final label (`none | gold | anti | aspirational`), 0-10 score, reason, optional response to Brain, and optional structured corrections only when Aaron cares. Do not make Aaron fill every Group C schema field by hand; Brain/parser expands the compact worksheet into the structured pending feedback payload for `apply_feedback.py`.
   - Do not generate contact sheets.

11. `create_lightbox.py`:

    - Read latest generation rows.
    - Apply filters for tier, tags, state, tone, model, score, scene fit, and failure mode.
    - Select latest rows per `image_id` using `event_timestamp` plus append order as the tie-breaker.
    - Accept explicit image-id handoff input from retrieval/search via inline `--image-ids img-001,img-002` or `--image-ids-file <path>`.
    - Treat explicit image IDs as the selected set; do not include filter-derived extras when explicit IDs are provided.
    - Accept `--image-ids-file` as either a JSON search-result object containing an `image_ids` array or a plain newline-delimited list of image IDs.
    - If inline IDs and file IDs are both provided, preserve inline order first, append file IDs second, and de-duplicate IDs by first occurrence.
    - If explicit IDs are missing from latest rows, record them in `missing_image_ids`; `item_count` is the rendered-card count, so `len(explicit_image_ids) - len(missing_image_ids) == item_count` for explicit-ID runs.
    - If retrieval/search returns zero IDs, Brain should report no candidates and not call `create_lightbox.py` to create an empty explicit-ID lightbox.
    - Copy images into `reviews/visual/lightboxes/<date>-<slug>/images/`.
    - Write `lightbox-manifest.json`.
    - Do not generate contact sheets.

12. `compute_alignment.py`:

    - Compare Brain `pre_eval` rows against Aaron `final_eval` rows.
    - Exclude `image_origin: "smoke_test"` rows from alignment computation.
    - For non-holdout rows, join by `(image_id, session_id)`.
    - For `image_origin: "holdout_benchmark"`, join each pre-eval row to the latest row for the same `image_id` where `event_type == "final_eval"` and `review_status == "confirmed"`, regardless of session mismatch.
    - If no confirmed final-eval ground truth exists, skip alignment computation for that row and report it under `missing_ground_truth`.
    - Require `alignment_phase` on every `alignment.jsonl` row: `baseline`, `post_seed`, or `normal`.
    - Write `benchmark/logs/alignment.jsonl`.
    - Write `benchmark/charts/alignment_score_by_session.png`.
    - Write `benchmark/charts/promotion_precision_recall.png`.

13. V1.1 `taste_memory` semantic search scripts:

    - `rebuild_taste_memory_index.py` rebuilds or incrementally updates `taste_memory` from durable logs without deleting or resetting the collection.
    - It writes two stable records per indexed image:

      ```text
      <image_id>::image
      <image_id>::search_text
      ```

    - The `image` record stores the actual image embedding for visual similarity.
    - The `search_text` record stores a compact derived Chroma document and embedding covering perception, Brain pre-eval, Aaron feedback, tags, `anchor_promotion`, quality tier, model/job lineage, and source path.
    - Metadata is flat scalar-only and includes `search_index_version` and `modality`.
    - Default rebuild scope is reviewed/generated image memory (`image_origin: generation`). Non-generation reviewed rows such as `anchor_seed` or `external_inbox` require an explicit include flag so `visual_anchors` remains the seeded-anchor search surface.
    - `holdout_benchmark` rows are excluded by default; inclusion requires an explicit holdout flag.
    - `--dry-run --compatibility-audit` is non-destructive and reports old/plain-id records under compatibility warnings.
    - `search_taste_memory.py` returns pinned JSON with `ok`, `query`, `collection`, `mode`, `count`, `top_k`, `matches`, and `image_ids`, compatible with `create_lightbox.py --image-ids-file`.
    - `inspect_taste_memory.py` reports counts, modality counts, promotion counts, compatibility warnings, and sample records.
    - After `apply_feedback.py` appends confirmed feedback, run:

      ```bash
      python3 benchmark/scripts/rebuild_taste_memory_index.py --apply --job-id <job_id>
      ```

      before relying on taste-memory retrieval for that job. This refreshes both modality records and the compact `search_text` document.

14. `create_alignment_summary.py`:

    - Compare `brain_initial_*` fields against Aaron feedback.
    - Write `reviews/visual/jobs/<job_id>/alignment-summary.md`.
    - Write `reviews/visual/jobs/<job_id>/alignment-metrics.json`.
    - Read or reference `benchmark/logs/alignment.jsonl` as the canonical per-image/session alignment log.

15. `read_heartbeat.py` and `read_flowarm_status.py`:

    - Read either `/workspace/handoff/flowarm-status/heartbeat.json` or `/workspace/handoff/flowarm-status/status.json`.
    - Preserve the no-file Boot Clean path:

      ```json
      {"status": "no_heartbeat_file", "stuck": false}
      ```

    - Normalize to fields:

      ```text
      timestamp
      status
      profile
      current_job
      current_prompt
      progress
      note
      age_seconds
      stuck
      ```

    - Native fake schemas must both be tested:

      `heartbeat.json`:

      ```json
      {
        "timestamp": "2026-04-26T00:00:00Z",
        "status": "working",
        "current_job": "job-001",
        "current_prompt": "p01",
        "progress": "1/4",
        "note": "fake heartbeat test"
      }
      ```

      `status.json`:

      ```json
      {
        "status": "idle",
        "timestamp": "2026-04-26T00:00:00Z",
        "profile": "flowarm",
        "current_job": null
      }
      ```

16. Commit scripts:

    ```bash
    cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
    git add benchmark/scripts reviews assets
    git commit -m "Brain scoring ingestion feedback review lightbox alignment and status scripts"
    ```

## Files And Folders Expected

Expected required scripts:

```text
benchmark/scripts/init_collections.py
benchmark/scripts/test_embed.py
benchmark/scripts/embed_anchors.py
benchmark/scripts/score.py
benchmark/scripts/search_anchors.py
benchmark/scripts/make_chart.py
benchmark/scripts/ingest_batch.py
benchmark/scripts/apply_feedback.py
benchmark/scripts/create_review_packet.py
benchmark/scripts/create_lightbox.py
benchmark/scripts/rebuild_taste_memory_index.py
benchmark/scripts/search_taste_memory.py
benchmark/scripts/inspect_taste_memory.py
benchmark/scripts/compute_alignment.py
benchmark/scripts/create_alignment_summary.py
benchmark/scripts/read_heartbeat.py
benchmark/scripts/read_flowarm_status.py
```

Expected output families:

```text
benchmark/logs/generations.jsonl
benchmark/logs/feedback.jsonl
benchmark/logs/alignment.jsonl
benchmark/charts/*.png
reviews/visual/jobs/<job_id>/
reviews/visual/lightboxes/<date>-<slug>/
assets/images/generated/jobs/<job_id>/<model>/<prompt_id>/
```

## Aaron Manual Stop Points

- Aaron must confirm parsed feedback before `apply_feedback.py` runs on real review data.
- Aaron must explicitly approve anchor promotions.
- Aaron must explicitly approve canon promotions.
- Aaron does not need to act for fake Boot Clean validation.

## Validation Commands

Required scripts:

```text
Run: cd /workspace/series-vault && for f in \
  benchmark/scripts/init_collections.py \
  benchmark/scripts/test_embed.py \
  benchmark/scripts/embed_anchors.py \
  benchmark/scripts/score.py \
  benchmark/scripts/make_chart.py \
  benchmark/scripts/ingest_batch.py \
  benchmark/scripts/apply_feedback.py \
  benchmark/scripts/create_review_packet.py \
  benchmark/scripts/create_lightbox.py \
  benchmark/scripts/compute_alignment.py \
  benchmark/scripts/create_alignment_summary.py \
  benchmark/scripts/read_heartbeat.py \
  benchmark/scripts/read_flowarm_status.py; do
  test -f "$f" && echo "OK $f" || echo "MISSING $f"
done
```

Compile:

```text
Run: cd /workspace/series-vault && python -m py_compile benchmark/scripts/*.py
```

Chart Boot Clean:

```text
Run: python /workspace/series-vault/benchmark/scripts/make_chart.py
```

Expected before ingestion: `No entries yet.`

Heartbeat no-file Boot Clean:

```text
Run: python /workspace/series-vault/benchmark/scripts/read_flowarm_status.py
```

Expected: no crash; no-file status if neither status file exists.

## Expected Outputs

- All scripts compile.
- Empty or missing data produces informative output, not tracebacks.
- Chroma metadata remains scalar-safe.
- Review packets and lightboxes contain manifests plus images only.
- Alignment summaries work after feedback is visible in latest generation rows.

## Failure Handling

- If Chroma rejects metadata, flatten it before upsert/update.
- If the obsolete bare `brain_initial_score` field reappears as a live key, replace it with `brain_initial_score_raw` plus `brain_initial_gold_similarity` and `brain_initial_anti_similarity`.
- If review packets duplicate images after feedback, restore latest-row-per-image logic.
- If alignment says no reviewed images after feedback, verify `apply_feedback.py` appended latest rows to `generations.jsonl`.
- If contact sheets appear, remove contact-sheet code from V1.

## Explicit Do Not Do Notes

- Do not store nested dicts/lists in Chroma metadata.
- Do not move originals out of the master image library.
- Do not generate contact sheets.
- Do not write generated images to `working/work-in-progress`.
- Do not make Flow Arm write to Chroma.
