# 08 - Validation And Boot Clean Plan

## Purpose

Validate the Brain build against the checklist and prove it boots cleanly before real anchors, real Flow Arm output, or real feedback exist. A Green Brain build should be stable with empty data and become meaningful as Aaron adds references and reviews real batches.

## Legacy Inputs Used

- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 1 through 20
- `Build-Guide-FINAL.md` sections 12.18, 13.1, 13.2, and 15

## Prerequisites

- Plans 01 through 07 have been executed.
- Aaron-approved V1.1 `taste_memory` semantic search/indexing slice has been implemented and verified before final Plan 08 validation. Scope is limited to `_SeriesAgentOps/proposals/v1.1-taste-memory-semantic-search-plan.md`; other V1.1 / V2 ideas remain out of scope unless separately approved.
- Brain can launch.
- Scripts exist.
- Handoff is mounted.
- Some provider checks may be Yellow depending on GPT Image 2 exposure.

## Track Reconciliation Audit

Run this audit before the fake end-to-end loop. Plan 08 must stop if any required track outcome is missing, unresolved, or inconsistent with the v3.2.1 execution brief.

Track status:

- [ ] Tracks 1, 2, and 3: all sub-tasks are declared `done` with passing DoD checklists.
- [ ] Track 4: 4.A is `done`; 4.B is `done` OR explicit Yellow/Deferred sign-off is recorded in `_SeriesAgentOps/PROJECT-STATE.md`.
- [ ] No unresolved `PROPOSED SCHEMA CHANGE` entries exist in any track file.
- [ ] `_SeriesAgentOps/PROJECT-STATE.md` matches completed track outcomes.

Source-plan reconciliation:

- [ ] Source Plan 04 amended where Track 1 decisions changed anchor methodology.
- [ ] Source Plan 05 amended where Track 2 decisions changed packet contract.
- [ ] Source Plan 06 amended where Tracks 1/3 decisions changed Brain scripts.
- [ ] Source Plan 07 amended where Track 3 decisions changed governance.
- [ ] Source Plan 08 amended; obsolete validation expectations removed.

Anchor, holdout, and leakage checks:

- [ ] Single-inbox flow exists; folder pre-sort leakage is gone.
- [ ] No folder-name leakage remains in Brain pre-eval prompt or draft-table process.
- [ ] Holdout images are excluded from `visual_anchors` by count/metadata check.
- [ ] No `holdout_benchmark` image_id appears in `manifest.json` or `visual_anchors` metadata.
- [ ] `created_by` field exists, validates, and is used in production records.
- [ ] `holdout_benchmark` `image_origin` value exists, validates, and is used correctly.

Alignment and scoring checks:

- [ ] `alignment_phase` field is required and present on all `alignment.jsonl` rows.
- [ ] `brain_initial_score_raw`, `brain_initial_gold_similarity`, and `brain_initial_anti_similarity` are reconciled across:
  - `SCHEMA.md`
  - `validate_eval.py`
  - `score.py`
  - Plan 06 doc
  - Plan 08 doc
  - `BRAIN_INTERVIEW_PROMPT.md`
- [ ] No live field/key/JSON-key/validation-rule references the obsolete bare `brain_initial_score` without `_raw`.
- [ ] Any prose-only mention of obsolete bare `brain_initial_score` is explicitly marked obsolete.
- [ ] `compute_alignment.py` handles cross-session holdout comparison.
- [ ] `compute_alignment.py` holdout join filters `event_type=final_eval` and `review_status=confirmed`.
- [ ] Missing-ground-truth fallback skips alignment computation and counts skipped rows.
- [ ] Smoke-test rows are excluded from alignment computation.
- [ ] `perception_history.jsonl` rows preserve full `perception_text` per `SCHEMA.md` Group A; Chroma remains a rebuildable retrieval index, not the sole source of descriptive truth.

Ad-hoc lightbox retrieval checks:

- [ ] If Track 3.E is accepted, `create_lightbox.py` can build a lightbox from explicit `image_id` input without adding filter-derived extras.
- [ ] If Track 3.E is accepted, `search_anchors.py` returns pinned-shape JSON with `ok`, `query`, `collection`, `count`, `top_k`, `matches`, and `image_ids`.
- [ ] If Track 3.E is accepted, `search_anchors.py` handles empty `visual_anchors`, missing query-embedding credentials, and `top_k` larger than collection size without traceback.
- [ ] If Track 3.E is accepted, Brain governance documents the search -> count -> confirmation -> lightbox creation workflow.
- [ ] V1.1 generated-image semantic search over `taste_memory` is implemented because Aaron promoted this slice into pre-Plan 08 scope on 2026-05-03.
- [ ] `rebuild_taste_memory_index.py` or approved equivalent can dry-run and apply the `taste_memory` index using two stable records per image: `<image_id>::image` and `<image_id>::search_text`.
- [ ] `taste_memory` stores actual image embeddings for visual similarity and compact `search_text` embeddings/documents for feedback/perception/lineage search.
- [ ] `search_taste_memory.py` or approved equivalent returns pinned-shape JSON with `ok`, `query`, `collection`, `mode`, `count`, `top_k`, `matches`, and `image_ids`.
- [ ] `search_taste_memory.py` supports metadata filters for `anchor_promotion`, `quality_tier`, score range, model, created_by, job_id, world_state, tone, failure_mode, canon_candidate, and holdout inclusion.
- [ ] Default `taste_memory` search excludes `holdout_benchmark` rows; any inclusion requires an explicit `--include-holdouts`-style flag and visibly marks benchmark records.
- [ ] V1.1 compatibility audit is non-destructive: no default reset/deletion of `taste_memory`, any old/plain-id records are reported under compatibility warnings, and search ignores non-V1.1-shaped records unless Aaron approves cleanup.
- [ ] `apply_feedback.py` / feedback workflow cannot leave the V1.1 index silently stale. Either feedback triggers both modality-record updates, or the documented rebuild-after-feedback command is run and verified.
- [ ] `search_taste_memory.py` output can be handed to `create_lightbox.py --image-ids-file` and produces a lightbox containing exactly the returned existing image IDs.
- [ ] Full generated-image semantic search over `taste_memory` and Chroma `documents` / compact `search_text` indexing are no longer deferred for this slice; other V1.1 / V2 items remain deferred unless separately approved.

Chart and cleanup checks:

- [ ] `alignment_score_by_session.png` exists.
- [ ] Promotion precision/recall chart exists.
- [ ] Final blind holdout retest has been run after V1.1 `taste_memory` semantic search/indexing is complete, using a new session_id and preserving holdout privacy.
- [ ] Final holdout chart/report compares the original frozen baseline against the final retest score. If other intermediate numbers are shown, they must be labeled as intermediate/calibrated and must not replace the original baseline comparison.
- [ ] No holdout retest image is embedded into `visual_anchors`, written into `manifest.json`, or indexed into `taste_memory` unless Aaron explicitly approves a separate benchmark-search mode.
- [ ] Manual Discord happy-path smoke test completed or explicitly marked manual-Aaron-needed.
- [ ] Smoke fixtures, `.DS_Store`, and `__pycache__` are cleaned up or excluded via `.gitignore`.
- [ ] Git status reviewed; intentional uncommitted files explained before final commit.

## Exact Later Execution Steps

1. Run foundation checks:

   - Docker healthy
   - Hermes installed and updated
   - `series doctor` runs

2. Run vault layout checks:

   - vault root exists
   - OPS folder is outside Brain visibility
   - folder structure exists
   - source-pack canonical names exist
   - both `flowarm-status/` folders exist
   - handoff `jobs/status/` exists

3. Run stale-path sweep last in vault validation, after source-pack cleanup and corrected `AGENTS.md` generation:

   ```bash
   cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
   grep -RInE '(^|[^A-Za-z])ArmWorkspace|wiki/prompting|working/work-in-progress|contact-sheet|/llm-wiki|armchat|(^|[^A-Za-z])arm-status|/workspace/arm' . --exclude-dir=.git --exclude-dir=benchmark/chroma_data || true
   ```

   Expected: no output.

4. Run Brain sandbox checks:

   - Brain sees vault.
   - Brain sees `/workspace/handoff`.
   - Brain cannot read arbitrary host files.
   - Brain cannot see `_SeriesAgentOps`.

5. Run `AGENTS.md` grounding check:

   - Brain summarizes architecture accurately.
   - Brain mentions Creative DNA behavior and project purpose.

6. Run provider checks:

   - `GEMINI_API_KEY True`
   - GPT-5.5 routes through Hermes
   - Kimi routes through Ollama
   - GPT Image 2 works or is marked Yellow

7. Run Gemini/Chroma checks:

   - `test_embed.py` returns 3072
   - Chroma collections exist
   - persistence works
   - no legacy 768-dimensional data

8. Run script checks:

   - all required scripts exist
   - V1.1 `taste_memory` search scripts exist after Aaron's 2026-05-03 scope promotion:
     - `rebuild_taste_memory_index.py` or approved equivalent
     - `search_taste_memory.py` or approved equivalent
     - `inspect_taste_memory.py` if implemented as the optional inspection helper
   - `python -m py_compile benchmark/scripts/*.py` passes

9. Run Boot Clean checks:

   - `init_collections.py` works with empty collections
   - `make_chart.py` prints `No entries yet.` before ingestion
   - `score.py` reports missing anchors without crashing if anchors are absent
   - `read_flowarm_status.py` and `read_heartbeat.py` handle absent heartbeat/status files without crashing
   - sparse state anchors produce fallback output, not errors
   - `taste_memory` search tooling handles an empty or unindexed collection without crashing

10. Run V1.1 `taste_memory` semantic search checks:

   ```text
   Run: python /workspace/series-vault/benchmark/scripts/rebuild_taste_memory_index.py --dry-run --compatibility-audit
   Run: python /workspace/series-vault/benchmark/scripts/rebuild_taste_memory_index.py --dry-run --job-id <real-reviewed-job-id>
   Run: python /workspace/series-vault/benchmark/scripts/rebuild_taste_memory_index.py --apply --job-id <real-reviewed-job-id>
   Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py "beautiful but wrong for the current style" --top-k 5
   Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py "architecture" --anchor-promotion anti --top-k 10
   Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py --query-image <known-indexed-image-path> --mode image --top-k 5
   Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py "mountain at sunset" --top-k 8 > /tmp/taste-search.json
   Run: python /workspace/series-vault/benchmark/scripts/create_lightbox.py --slug taste-search-smoke --description "Taste search smoke" --image-ids-file /tmp/taste-search.json
   ```

   Expected:

   - no destructive `taste_memory` reset/deletion occurs
   - compatibility warnings are reported rather than auto-cleaned
   - two V1.1 records per indexed image exist: `::image` and `::search_text`
   - search output matches the pinned JSON shape and returns deduplicated `image_ids`
   - metadata filters are respected
   - default search excludes holdout benchmark rows
   - lightbox contains exactly the returned existing image IDs

11. Run fake native heartbeat/status tests:

    Create native `heartbeat.json` shape:

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

    Validate reader normalization.

    Create native `status.json` shape:

    ```json
    {
      "status": "idle",
      "timestamp": "2026-04-26T00:00:00Z",
      "profile": "flowarm",
      "current_job": null
    }
    ```

    Validate reader normalization.

12. Run final blind holdout retest:

    - Run a fresh holdout pre-eval/retest session after V1.1 implementation.
    - Use a new `session_id`; do not reuse baseline or post-seed session IDs.
    - Keep Brain blind to Aaron's holdout labels/reasoning.
    - Use the external holdout truth path for scoring, not Brain-readable answer-key ingestion.
    - Verify holdouts remain excluded from:
      - `benchmark/anchors/manifest.json`
      - Chroma `visual_anchors`
      - Chroma `taste_memory` default index/search scope
    - Generate a visual chart/report comparing:
      - original frozen baseline score
      - final retest score
    - Intermediate/post-seed/calibrated metrics may be included only if clearly labeled and not substituted for the original baseline comparison.

13. Run fake end-to-end loop:

    - Create full fake job packet.
    - Move through `draft -> ready -> dispatched`.
    - Copy dispatched packet to `/workspace/handoff/jobs/outgoing/`.
    - Create `/workspace/handoff/jobs/status/job-001.status.json` with `handoff_status: "outgoing"`.
    - Create fake result manifest and fake images in `/workspace/handoff/results/incoming/job-001/`.
    - Run `ingest_batch.py job-001`.
    - Create review packet.
    - Create pending feedback file using a real fake image ID.
    - Run `apply_feedback.py`.
    - Recreate review packet to prove latest-row-wins.
    - Create lightbox.
    - Create alignment summary.
    - Generate charts.
    - Archive packet with `packet_status: "archived"`.

14. Run manual Discord happy-path smoke test:

    This is the operator-experience test. It is separate from the fake loop, which primarily validates contracts and scripts.

    Minimal happy path:

    - Aaron asks Brain in Discord to prepare or identify a tiny validation job.
    - Brain produces the packet/claim instruction using the normal Discord coordination pattern.
    - Aaron posts the Flow Arm claim command in `#flow-arm-log`.
    - Flow Arm claims, completes, and writes status/result artifacts.
    - Aaron tells Brain the job is ready.
    - Brain ingests the result.
    - Brain creates review packet, Markdown worksheet, and lightbox.
    - Aaron provides tiny feedback through the intended review surface.
    - Brain applies feedback.
    - Brain updates anchors or `taste_memory` as appropriate for the feedback.
    - Brain can search/retrieve the result and create a lightbox from the search output.

    Expected:

    - Discord coordination is understandable and does not require hidden local-file knowledge from Aaron.
    - Flow Arm and Brain remain in their ownership lanes.
    - Artifacts are written in the expected locations.
    - Review worksheet/lightbox are usable.
    - Feedback application and V1.1 search/index update are visible and verifiable.

15. Run Obsidian manual validation after the vault exists:

    - Aaron opens Obsidian.
    - Open folder as vault: `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault`.
    - Verify source-pack, reviews, and images are browsable.
    - Verify Dataview, Templater, and Recent Files if needed.

## Files And Folders Expected

Fake loop artifacts:

```text
assets/images/generated/jobs/job-001/nano-banana-pro/<prompt_id>/<image_file>
benchmark/logs/generations.jsonl
benchmark/logs/feedback.jsonl
benchmark/logs/alignment.jsonl
reviews/visual/jobs/job-001/review-manifest.json
reviews/visual/jobs/job-001/images/
reviews/visual/jobs/job-001/alignment-summary.md
reviews/visual/jobs/job-001/alignment-metrics.json
reviews/visual/lightboxes/<date>-validation-great/lightbox-manifest.json
benchmark/charts/taste_score_over_time.png
benchmark/charts/taste_score_by_model.png
benchmark/charts/alignment_score_by_session.png
benchmark/charts/promotion_precision_recall.png
```

Forbidden artifacts:

```text
contact-sheet.png
working/work-in-progress
/llm-wiki
```

## Aaron Manual Stop Points

- Aaron must perform Obsidian validation.
- Aaron must distinguish Yellow GPT Image 2 from Red provider failure.
- Aaron does not need to provide real reference images for Boot Clean; real taste learning waits for anchors.

## Validation Commands

Plan-set critical decision check:

```bash
rg -n 'Boot Clean|project-purpose.md|read_flowarm_status|read_heartbeat|flowarm-status|jobs/status|handoff_status|packet_status: "archived"|GPT Image 2|working/job-packets/dispatched|/workspace/handoff/jobs/outgoing|vault copy|/Volumes/4TB990PRO/SeriesDrive' /Volumes/4TB990PRO/SeriesDrive/_SeriesAgentOps/series-vault-build-plans
```

Script compile:

```text
Run: cd /workspace/series-vault && python -m py_compile benchmark/scripts/*.py
```

V1.1 taste-memory semantic search:

```text
Run: python /workspace/series-vault/benchmark/scripts/rebuild_taste_memory_index.py --dry-run --compatibility-audit
Run: python /workspace/series-vault/benchmark/scripts/rebuild_taste_memory_index.py --apply --job-id <real-reviewed-job-id>
Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py "beautiful but wrong for the current style" --top-k 5
Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py "architecture" --anchor-promotion anti --top-k 10
Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py --query-image <known-indexed-image-path> --mode image --top-k 5
Run: python /workspace/series-vault/benchmark/scripts/search_taste_memory.py "mountain at sunset" --top-k 8 > /tmp/taste-search.json
Run: python /workspace/series-vault/benchmark/scripts/create_lightbox.py --slug taste-search-smoke --description "Taste search smoke" --image-ids-file /tmp/taste-search.json
```

Full fake loop:

```text
Run: python /workspace/series-vault/benchmark/scripts/ingest_batch.py job-001
Run: python /workspace/series-vault/benchmark/scripts/create_review_packet.py job-001
Run: python /workspace/series-vault/benchmark/scripts/apply_feedback.py /workspace/series-vault/benchmark/logs/pending-feedback.json
Run: python /workspace/series-vault/benchmark/scripts/create_review_packet.py job-001
Run: python /workspace/series-vault/benchmark/scripts/create_lightbox.py --slug validation-great --description "Validation great images" --tier great --limit 20
Run: python /workspace/series-vault/benchmark/scripts/compute_alignment.py
Run: python /workspace/series-vault/benchmark/scripts/create_alignment_summary.py job-001
Run: python /workspace/series-vault/benchmark/scripts/make_chart.py
```

## Expected Outputs

- Green only when all required Brain-side checklist items pass.
- Yellow allowed for GPT Image 2 unavailability if GPT-5.5 and handoff remain healthy.
- Boot Clean passes without anchors, heartbeat, generated images, or logs.
- Fake end-to-end loop produces required artifacts.

## Failure Handling

- Red if Brain sandbox can see arbitrary host files.
- Red if Chroma dimension is not 3072.
- Red if the obsolete bare `brain_initial_score` field reappears as a live key; use `brain_initial_score_raw` plus gold/anti diagnostics instead.
- Red if feedback does not append latest rows to `generations.jsonl`.
- Red if contact sheets are generated.
- Yellow if GPT Image 2 is unavailable but documented.
- Yellow if state-aware scoring falls back due to sparse anchors but says so clearly.

## Explicit Do Not Do Notes

- Do not mark Boot Clean failed because there are no real anchors yet.
- Do not mark GPT Image 2 unavailable as Red by itself.
- Do not run real Flow Arm jobs as part of Brain fake validation.
- Do not skip stale-path sweep.
- Do not leave validation artifacts unexplained in logs.
