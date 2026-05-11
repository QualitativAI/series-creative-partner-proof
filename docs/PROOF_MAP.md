# Proof Map

This repo is organized so reviewers can verify the system at four levels: architecture, plan, implementation, and artifact trail.

## 0. Architecture At A Glance

- `media/flow-diagram.png` shows the Brain / Flow Arm / vault / handoff / review loop.
- `docs/KIMI_REVIEW_BRIEF.md` gives the shortest written framing for the Kimi review.

## 1. Build Plan Evidence

- `build-plans/series-vault/` contains the Brain-side build sequence: vault setup, sandboxing, provider auth, embeddings/anchors, packet contract, scripts, governance, and validation.
- `build-plans/flow-arm/` contains the dedicated-device Flow Arm build sequence: device setup, Hermes profile, browser auth, heartbeat/status files, claim protocol, browser execution, and validation. It also includes post-V1 enhancement plans with `v2.X` prefixes, clearly separated from the V1 sequence.

These are the final active plan folders used by the project snapshot. Older legacy guide files are intentionally not included.

## 2. Working Code Evidence

- `working-code/benchmark-scripts/` contains the Python scripts for ingestion, scoring, review packets, lightboxes, feedback application, taste-memory indexing/search, validation, and status reads.

The repo does not include live credentials, database files, or the full holdout answer rows.

## 3. Flow Arm Execution Evidence

- `proof-artifacts/handoff-jobs/` contains sample completed job packets and status sidecars.
- `proof-artifacts/result-manifests/` contains sample Flow Arm result manifests using the finalized `handoff-result.v1` contract.
- `proof-artifacts/flow-arm-validation/` contains the two dedicated-device validation jobs referenced in the Flow Arm proof summary, including job packets, status sidecars, result manifests, and output JPEGs.
- `proof-artifacts/flow-arm-status/` contains status/heartbeat evidence from the dedicated Flow Arm path plus the result-manifest contract repair note.
- `docs/FLOW_ARM_PROOF_SUMMARY.md` summarizes the dedicated-device validation and the practical findings from real jobs.

Together, these show the file-based dispatch loop: Brain writes a job packet, Flow Arm claims/completes it, then writes a structured result manifest.

## 4. Visual Review Evidence

- `proof-artifacts/review-lightbox/` contains a review lightbox generated from a real Nano Banana Pro visual probe.

The compact version keeps the workflow, images, tags, and review notes while leaving raw scoring diagnostics out of the main review path.

## 5. Evaluation Evidence

- `docs/EVALUATION_SUMMARY.md` reports the aggregate 31-item holdout check: `3/31` frozen baseline to `7/31` post-workflow retest.
- `working-code/benchmark-scripts/` and `source-of-truth/SCHEMA.md` show the scoring/evaluation methodology.

## 6. Media

- `media/flow-diagram.png` is the recommended visual architecture reference.
- The full demo video is linked from the root `README.md` via the X post.
