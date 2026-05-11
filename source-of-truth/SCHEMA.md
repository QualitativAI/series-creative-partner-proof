# benchmark/SCHEMA.md

**Source-of-truth contract for evaluation, anchor curation, and taste-memory data flow.**

## Purpose

Defines the data contract for every image the Series system observes, evaluates, anchors, and learns from. Referenced by every script that touches evaluation: `describe_image.py`, `validate_eval.py`, `embed_anchors.py`, `score.py`, `apply_feedback.py` (plan 06), `create_alignment_summary.py` (plan 06).

## Scope

- Anchor curation (plan 04 — initial seeding and ongoing additions)
- Generation review (plan 06 — `brain_initial_*` capture, feedback loop, alignment metrics)
- Behavioral governance (plan 07 — canon promotion, anchor promotion authority)

For evaluation data fields and validation behavior, this schema is authoritative after Aaron approval. For broader architecture (devices, plan ordering, packet/handoff contracts, canon governance, Flow Arm boundaries), the active build-plan corpus and PROJECT-STATE remain authoritative. If this document conflicts with a corpus-locked decision (e.g., `packet_status` is Brain-only per PROJECT-STATE §2), the corpus wins and this document gets corrected.

## Schema version

`schema_version: v1`

When fields are added, removed, or have semantics change, bump the version and note the change in the activity log. JSONL entries should record the schema version in effect when they were written, so old entries remain interpretable.

---

## Standing rules

These apply to every script and every Brain session. Hard rules.

### 1. Capability availability ≠ architectural permission

If a model, API, or tool happens to be reachable via auth we already have, that does not authorize routing work through it. Architecture lines were drawn deliberately in the build plans for specific reasons. Respect those lines.

Concrete example: The Gemini API key reaches `nano-banana-pro-preview`. Nano Banana Pro is **not** routed via API in this system. It is generated through Flow Arm browser execution against Google Flow on the MacBook Pro (see `flow-arm-build-plans/06-browser-execution-stack-google-flow-plan.md` in the `_SeriesAgentOps` corpus, which lives outside this vault repository). Do not write API calls for Nano Banana Pro into any script in this repository.

### 2. Visual architecture: Gemini sees, Brain reasons, Aaron decides

```
Image pixels
  → Gemini 3 Flash = visual perception (eyes; current default — see model routing table)
  → GPT-5.5 Brain = creative interpretation, rubric application, dialogue, pushback (judge)
  → Aaron = final creative authority (director)
  → Gemini Embedding 2 = similarity vectors for retrieval and scoring (memory coordinates)
  → Chroma + JSONL logs = durable memory
```

GPT-5.5 inside Hermes does not have native local-image vision in the chat surface. It reasons over Gemini's structured perception report plus the rubric, Creative DNA, and Aaron's natural-language reactions. It does not see pixels directly.

### 3. Embeddings are similarity coordinates, not visual understanding

Gemini Embedding 2 produces 3072-dimensional vectors used for nearest-neighbor retrieval against the anchor pool. These vectors do **not** carry human-readable spatial detail and cannot substitute for visual perception. Brain must not treat embedding similarity as "I have seen the image." Embeddings answer "is this image close to images I've already learned about." They do not answer "what does this image depict."

### 4. Perception observations vs interpretive judgments

Gemini may report visual cues ("the image contains a weathered stone interior with late-afternoon light, atmospheric cues that may suggest a solemn or sacred space"). Gemini must **not** assign final values for `world_state`, `tone`, `quality_tier`, `anchor_promotion`, `failure_mode`, or rubric tags. Those are interpretive judgments under Brain's authority and the rubric's vocabulary.

If Gemini's output includes these field names with concrete values, that's a prompt bug — fix the perception prompt (and bump `perception_prompt_version`).

### 5. Aaron can override perception itself, not just interpretation

If Gemini's perception report misses something visible (a small creature on the tree trunk, a key compositional element, a color band) and Aaron points it out during review, the correction is captured in `aaron_perception_corrections` on the final eval record. Gemini's perception is evidence, not authority. Aaron's direct visual reading supersedes Gemini's report on points of conflict.

This matters for two reasons: (a) it preserves Aaron's creative authority over what the image actually contains, (b) accumulated corrections become diagnostic data about Gemini's perception blind spots.

### 6. Source-of-truth split

```
benchmark/anchors/manifest.json            ONLY confirmed gold/anti/aspirational entries
benchmark/anchors/manifest.draft.jsonl     in-progress session draft (machine-readable)
benchmark/anchors/manifest.draft.md        in-progress session draft (human-readable)
benchmark/anchors/inbox/                   single incoming reference-image inbox
benchmark/logs/generations.jsonl           generated-image lineage + review events
benchmark/logs/perception_history.jsonl    every Gemini perception report, immutable append
benchmark/logs/pre_eval_history.jsonl      every Brain pre-eval, immutable append
benchmark/logs/final_eval_history.jsonl    every confirmed Aaron decision, immutable append
benchmark/logs/alignment.jsonl             per-image delta + session aggregate
```

Non-promoted images (`anchor_promotion=none`) never enter `manifest.json`. They DO enter the eval-history logs and contribute to alignment metrics. Okay/great/middle/meh tiers are valuable taste data and are preserved durably; they just don't become reference vectors.

Chroma collections also split this way:

- **`visual_anchors`** holds embeddings ONLY for images promoted to gold/anti/aspirational. This is the strict reference set scored against.
- **`taste_memory`** holds rebuildable reviewed/generated image retrieval records. "Not anchored" does not mean "not in Chroma ever" — it means "not in the `visual_anchors` reference set."

In V1 plan 04 we initialize both collections empty. `visual_anchors` is populated by `embed_anchors.py` as Aaron confirms anchor promotions. `taste_memory` is populated by the V1.1 rebuild path from durable generation, perception, pre-eval, and final-eval logs.

V1.1 `taste_memory` record contract:

```text
<image_id>::image       actual image embedding for visual similarity
<image_id>::search_text compact derived text embedding/document for perception, Brain pre-eval,
                         Aaron feedback, tags, anchor_promotion, quality tier, model/job lineage
```

The compact `search_text` document is derived and rebuildable. It is not source truth, and it must not replace full raw perception text or Aaron feedback in JSONL logs. Chroma metadata remains flat scalar-only and includes `search_index_version` plus `modality` so search can ignore legacy/plain-id records. Default rebuild scope is generated-image memory (`image_origin: generation`) so seeded anchors remain in `visual_anchors`; reviewed non-generation rows require an explicit include flag. Holdout benchmark rows are excluded from `taste_memory` search by default unless explicitly included for a benchmark-search command.

### 7. Chroma metadata flatness

Chroma metadata must be flat scalars and strings only. Nested fields must be either flattened to multiple top-level keys (`brain_initial_confidence__world_state: "high"`) or serialized as a single JSON string (`brain_initial_confidence_json: '{"world_state":"high",...}'`).

V1 default for nested fields: JSON-string serialization with a `_json` suffix on the key. Easier to evolve, one column per logical field.

### 8. Embed-after-confirm rule (script-enforced)

`embed_anchors.py` refuses to embed unless ALL true:

```
review_status == "confirmed"
anchor_promotion in {"gold", "anti", "aspirational"}
world_state in <valid 8>
tone in <valid 8>
quality_tier in <valid 6>
final_notes is non-empty string
aaron_score is int in [0, 10]
filename exists on disk at expected anchor folder path
image_id matches sha256(content)
```

If `anchor_promotion == "none"`, the script returns "skipped: no promotion" — never embeds, never errors. Logs ≠ anchors.

If `image_origin == "holdout_benchmark"`, Brain never intentionally calls `embed_anchors.py`. Script-level defense-in-depth still applies:

```text
anchor_promotion != "none"  -> ok:false, stage:"holdout_anti_leakage"; no Chroma write; no manifest write
anchor_promotion == "none"  -> ok:true, skipped holdout message; no Chroma write; no manifest write
```

This rule is enforced at the script layer, not at the Brain interview layer. Defense in depth: prompt says don't embed early, script refuses to embed early.

---

## Architecture

### Model routing table

| Capability | Model | Provider | Auth | Device | Notes |
|--|--|--|--|--|--|
| Brain reasoning + creative judgment | `gpt-5.5` | OpenAI Codex CLI | OAuth (ChatGPT Plus) | Mac Studio | Via Hermes profile=`series` |
| Image description (visual perception) | `gemini-3-flash-preview` | Gemini API | API key | Mac Studio | Plan 04 approved capability. Locked 2026-04-29 after benchmark research: ~2.3× faster TTFT and ~5× cheaper than 3.1 Pro Preview at 80% vs 82% MMMU Pro. `--model gemini-3.1-pro-preview` override available per-image. |
| Vector embedding | `gemini-embedding-2` | Gemini API | API key (same) | Mac Studio | Plan 04, 3072 dims, pre-normalized |
| Brain-side image generation | `gpt-image-2` | OpenAI Codex | OAuth (same) | Mac Studio | High fidelity, plan 03 |
| Flow Arm image generation | Nano Banana Pro via Google Flow | Browser session | Google account login | MacBook Pro | Browser execution only — not API |
| Lore writing | `kimi-k2.6:cloud` | Ollama | Ollama signin | Mac Studio (host) | Plan 03 |

Nano Banana Pro is reachable via the Gemini API key but is not used that way — see Standing Rule 1.

### Approved capabilities (plan 04)

- Gemini Embedding 2 — for vector embeddings (already approved, plan 03)
- **Gemini 3.x preview family — for image description / visual perception (plan 04 approved).** Initially scoped to `gemini-3.1-pro-preview`; switched to `gemini-3-flash-preview` on 2026-04-29 after benchmark research showed comparable visual reasoning at substantially lower latency and cost. Either model is in-scope; specific variant choice is a tuning decision, not a separate capability approval. The default lives in `describe_image.py`'s `PERCEPTION_MODEL` constant; `--model` override flag exists for per-image fallback.

Both share the same Gemini API key but represent two separate approved capabilities. Future capability additions follow the same explicit-approval pattern.

---

## Vocabularies (locked)

These are the only valid values for their respective fields. No synonyms. Brain pushes back when Aaron uses a non-vocab term ("you said `peaceful` for image 4 — that's not in the tone vocab; closest valid options are `still` or `hopeful`, which one?").

### `review_status` — workflow metadata (5 values)

```
pending          Brain has not pre-evaluated yet
pre_evaluated    Brain pre-eval done; awaiting Aaron
in_review        Aaron reacting; Brain may have clarifying questions outstanding
confirmed        Aaron locked the entry
embedded         Entry has been written to Chroma (post-confirmation)
```

### `quality_tier` — creative judgment (6 values, no `pending`)

```
bad → okay → great → aspirational → approved → canon
```

`canon` is reserved for explicit canon governance per plan 07. Brain never assigns `canon` autonomously. Brain may set `canon_candidate: true` to flag for governance review; only Aaron promotes to `canon`.

### `anchor_promotion` — folder decision (4 values)

```
none, gold, anti, aspirational
```

Most images = `none`. Promotion is explicit and rare. See plan 06 anchor promotion rules.

### `image_origin` — source class (5 values)

```
anchor_seed          curated reference image intended for possible visual_anchors promotion
external_inbox       external non-generation image that is not part of the holdout proof set
generation           system-generated image from a job or Brain-side generation path
holdout_benchmark    Aaron-picked benchmark image used for before/after taste-prediction proof
smoke_test           pipeline verification artifact excluded from metrics
```

`holdout_benchmark` rows may carry Aaron's final `anchor_promotion` ground-truth label for alignment scoring, but that label is not an embed intent.

### `created_by` — image creator / generator (6 values)

```
midjourney
nano-banana-pro
gpt-image-2
flow-google-veo3
web
unknown
```

This is separate from `image_origin`: `image_origin` says why the image entered the pipeline, while `created_by` says where the pixels came from. The vocabulary is semi-locked and can be extended deliberately when a new creator/source becomes first-class.

### `world_state` — rubric vocab (8 values)

```
flourishing, sacred, broken, corrupted, abandoned, harsh, neutral, dna-core
```

`dna-core` is special: anchors tagged `dna-core` are always retrieved alongside state-specific anchors during scoring (see plan 04 step 11 score.py contract).

### `tone` — rubric vocab (8 values)

```
hopeful, awe-filled, mournful, eerie, tense, oppressive, still, neutral
```

### `failure_mode` (3 values + null)

```
execution     concept was right, model fumbled rendering
concept       prompt itself was wrong; idea isn't right for the world
partial       some elements work, others don't; salvageable with prompt iteration
null          not applicable — no failure mode applies (e.g., a strong great/approved/canon image,
                an aspirational image that's beautiful but situationally misplaced, or an okay image
                that's neutral rather than a clear failure)
```

### `rank` — derived from `brain_initial_score_raw` (4 values + null)

```
strong         >= 0.82
promising      >= 0.72 and < 0.82
borderline     >= 0.62 and < 0.72
likely-miss    < 0.62
null           score not applicable (e.g., initial seeding with no anchors yet)
```

Thresholds locked per plan 06 step 7.

---

## Field schemas

Four field groups, each owned by a different layer.

### Group A: Perception fields (Gemini 3.x preview family owns)

Produced by `describe_image.py`. Pure visual observation. No interpretive vocabulary, no rubric application.

```
image_id                          sha256:<first 16 hex chars of file content hash>
filename                          human-readable name on disk (may change)
source_path                       full container-relative path
perception_model                  default per describe_image.py PERCEPTION_MODEL constant
                                  (currently "gemini-3-flash-preview"; --model override per-image
                                  allowed within the approved Gemini 3.x preview family).
                                  Historical smoke-test rows may carry "gemini-3.1-pro-preview".
perception_model_version          provider-reported version string when available, else null
perception_prompt_version         "v1" (bumped when prompt changes)
perception_timestamp              ISO 8601 UTC
perception_text                   full raw text returned by Gemini (preserved verbatim)
perception_subject                what's in the foreground / primary subject
perception_composition            spatial layout, framing, focal points
perception_dominant_colors        list of color descriptors (e.g., ["weathered tan", "muted purple"])
perception_visible_text           any text rendered in the image, transcribed
perception_spatial_layout         relationships between elements, depth cues
perception_atmosphere             felt-quality observations (mist, light, weight, stillness, etc.)
perception_notable_details        specific elements worth flagging (small creature on tree, etc.)
perception_possible_state_cues    free-text suggestions ("cues might suggest sacred or solemn"), NOT tags
perception_possible_tone_cues     free-text suggestions, NOT tags
```

Stored in `benchmark/logs/perception_history.jsonl` per session. The full record persists; Brain pre-eval references it by `image_id`.

Operational note: production appenders must use the idempotent validator append path so a restarted run does not duplicate `(event_type, session_id, image_id)` rows. Historical duplicate perception rows may exist from pre-idempotence restarts; alignment tooling reads unique pre-eval/final-eval rows and must not join directly on raw perception row counts.

### Group B: Brain pre-evaluation fields (GPT-5.5 owns)

Produced by Brain reading the perception record + the rubric + Creative DNA. Interpretive judgment using locked vocabulary. Validated by `validate_eval.py`.

```
image_id                                       (matches perception record)
brain_initial_score_raw                        = taste_alignment = gold_similarity - anti_similarity
                                                 from score.py vs existing anchors;
                                                 NULL when anchors are absent
brain_initial_gold_similarity                  diagnostic score.py gold_similarity; number or NULL
brain_initial_anti_similarity                  diagnostic score.py anti_similarity; number or NULL
brain_initial_rank                             one of 4 + null, derived from brain_initial_score_raw
brain_initial_quality_tier                     one of 6 (canon excluded — Brain may not assign)
brain_initial_world_state                      one of 8
brain_initial_tone                             one of 8
brain_initial_scene_fit                        true / false / n-a
brain_initial_failure_mode                     one of 3 + null
brain_initial_tags                             comma-separated, from rubric tag categories
brain_initial_notes                            short prose, Brain's interpretation
brain_initial_anchor_promotion_recommendation  one of 4 — Brain's RECOMMENDATION only
brain_initial_canon_candidate                  boolean — Brain may flag, never assigns canon
brain_initial_confidence                       per-field map: high / medium / low
brain_initial_questions_or_flags               Aaron-targeted questions, or null
brain_initial_timestamp                        ISO 8601 UTC
```

Stored in `benchmark/logs/pre_eval_history.jsonl`.

### Group C: Aaron final evaluation fields

Filled after Aaron's reaction + final confirmation. Aaron's authority. Brain transcribes and validates.

```
image_id                       (matches perception + pre-eval records)
aaron_score                    int 0-10
quality_tier                   one of 6 — Aaron's final call
world_state                    one of 8
tone                           one of 8
fits_current_scene             true / false / n-a
failure_mode                   one of 3 + null
feedback_tags                  comma-separated
feedback_text                  raw natural-language reaction (preserved verbatim, no rewriting)
anchor_promotion               one of 4 — AARON'S FINAL DECISION (separate from Brain's recommendation)
canon_candidate                boolean — only Aaron sets to true; canon itself stays gated by plan 07
final_notes                    Aaron's observation, short prose
aaron_perception_corrections   array of strings, optional — visual details Gemini missed that Aaron flags
final_eval_timestamp           ISO 8601 UTC
```

Stored in `benchmark/logs/final_eval_history.jsonl`. If `anchor_promotion in {gold, anti, aspirational}`, also written to `benchmark/anchors/manifest.json`.

### Group D: Computed alignment fields

Computed by `compute_alignment.py` (or equivalent in `make_alignment_chart.py`). Not human-authored.

```
image_id
pre_eval_timestamp         ISO 8601 (joined from pre-eval log)
final_eval_timestamp       ISO 8601 (joined from final-eval log)
alignment_score            scalar [0, 1] using V1 provisional weights
alignment_breakdown        per-field hit/partial/miss for debugging and chart drilldown
schema_version             schema version in effect when computed
weighting_version          delta-weighting version in effect when computed
computed_at                ISO 8601 UTC
alignment_phase            one of: baseline, post_seed, normal
```

Stored in `benchmark/logs/alignment.jsonl`. Each row is one (image, session) pair; aggregated by session for charting.

`review_status` is NOT in Group D — it's a workflow field that appears on the per-row records of every log file (see "JSONL row shapes" below). It captures where the image was in its lifecycle at the moment that event was written.

---

## JSONL row shapes

Each log file is append-only and event-sourced. The unified state for an `image_id` is reconstructed by joining the latest entries across logs. Each row carries common fields plus stage-specific fields.

### Common fields (every row, every log)

```
schema_version       "v1"
session_id           ISO 8601 UTC of session start (groups rows from one curation/review session)
image_id             sha256:<first 16 hex chars>
filename             human-readable name on disk
source_path          container-relative path
image_origin         one of: "anchor_seed", "external_inbox", "generation", "holdout_benchmark", "smoke_test"
created_by           one of: "midjourney", "nano-banana-pro", "gpt-image-2", "flow-google-veo3", "web", "unknown";
                     required on production pre_eval/final_eval/alignment rows after Track 1.A
event_type           one of: "generation_ingested", "perception", "pre_eval", "final_eval", "embedded", "alignment"
review_status        one of 5 — status AS OF this row's event
event_timestamp      ISO 8601 UTC when this row was written
```

`event_type` identifies what kind of event this row records. Multiple log files may have rows with the same `review_status` (e.g., two rows can both report `review_status: pre_evaluated`, but one has `event_type: perception` and one has `event_type: pre_eval`), and `event_type` makes the distinction unambiguous when joining logs.

`review_status` advances over the lifecycle: `pending → pre_evaluated → in_review → confirmed → embedded`. The status reflects the post-event state of the image at the moment this row was written.

### `generations.jsonl` raw ingest row

Common fields (with `event_type: "generation_ingested"` and `review_status: "pending"`), plus generated-asset lineage fields. Written by `ingest_batch.py` when a Flow Arm or Brain-side generation result manifest is accepted. This row is **not** a Gemini perception row and **not** a Brain pre-eval row.

Required lineage fields:

```text
job_id
intent_id
packet_revision
prompt_id
target_id
asset_id
output_index
base_concept
world_state             nullable prompt intent; validated if present, never silently coerced
tone                    nullable prompt intent; validated if present, never silently coerced
model
model_version
platform
generation_model
rendered_prompt
file_path               vault-relative durable generated-image path
original_file_path      result-manifest path exactly as provided by Flow Arm / generator
original_resolved_path  local resolved path used during ingest
asset_event_timestamp   generation timestamp from the result manifest
mime_type
width
height
sha256                  computed from copied durable file bytes
declared_sha256         manifest-provided hash, when present
sha256_mismatch         false by default; ingest refuses mismatches unless explicitly overridden
ingest_source_manifest
ingested_at
score_status            one of: not_run, scored, unavailable
taste_alignment
brain_initial_score_raw
brain_initial_gold_similarity
brain_initial_anti_similarity
brain_initial_rank
score_error
```

`taste_alignment` and the four `brain_initial_*` score/rank fields are allowed on `generation_ingested` rows only as score.py diagnostics. They are nullable, and all must be null unless `score_status == "scored"`. If scored, the same Track 1.A equation applies:

```text
brain_initial_score_raw = taste_alignment = brain_initial_gold_similarity - brain_initial_anti_similarity
brain_initial_rank derives from brain_initial_score_raw
```

No Group A perception fields may be written by raw ingest. No Brain creative judgment fields (`brain_initial_quality_tier`, `brain_initial_world_state`, `brain_initial_tone`, `brain_initial_anchor_promotion_recommendation`, etc.) may be written until Brain actually performs pre-eval and appends a real `pre_eval` row. This prevents pending generated images from polluting review filters, alignment metrics, promotion precision/recall, or future semantic indexes as if Brain had judged them.

### `perception_history.jsonl` row

Common fields (with `event_type: "perception"`), plus all of Group A. Written by `describe_image.py` after Gemini returns. `review_status` stays `pending` — perception is visual data capture, not Brain interpretation; status doesn't advance until Brain pre-eval is produced.

### `pre_eval_history.jsonl` row

Common fields (with `event_type: "pre_eval"`), plus all of Group B. Written by Brain after producing the interpretive pre-eval. Sets `review_status` to `pre_evaluated`.

### `final_eval_history.jsonl` row

Common fields (with `event_type: "final_eval"`), plus all of Group C. Written after Aaron confirms. Sets `review_status` to `confirmed`. If `anchor_promotion in {gold, anti, aspirational}` and embed succeeds, a follow-up row is appended with `event_type: "embedded"` and `review_status: "embedded"` (status-bump row — common fields plus the bump-specific values; Group A/B/C are not repeated since they're already in prior rows).

### `alignment.jsonl` row

Common fields (with `event_type: "alignment"`), plus all of Group D. One row per (`image_id`, `session_id`) pair. Written by `compute_alignment.py` after final-eval is logged. `alignment_phase` is required:

```text
baseline    first holdout_benchmark pre-eval session for that image_id
post_seed   later holdout_benchmark pre-eval sessions for that image_id
normal      non-holdout alignment row
```

### `generations.jsonl` row

Per plan 04 + plan 06. Lineage record for generated images. Raw ingest rows use `event_type: "generation_ingested"` and remain `pending` until real perception/pre-eval/review rows are appended. Later rows may layer in Group A, Group B, Group C, or Group D fields only when the corresponding work actually happened.

**Chart-required fields (locked by plan 04 `make_chart.py`).** Every generation row that should appear in taste-score charts must include at minimum:

```
event_timestamp     ISO 8601 UTC string  (already a common field)
taste_alignment     number               (= score.py output: gold_similarity - anti_similarity)
generation_model    string               (provider+model id, e.g. "nano-banana-pro",
                                          "gpt-image-2", "flow-google-veo3")
```

Plan 06's `ingest_batch.py` may write `taste_alignment` only when score.py actually runs successfully; otherwise it writes score/rank fields as null. `make_chart.py` skips rows missing any chart-required value and excludes `image_origin == "smoke_test"` rows entirely. Skipped-row counts are reported to stderr.

**Naming distinction — `taste_alignment` vs `alignment_score`.** These are two different metrics with similar-sounding names. Do not conflate.

| Field | Where | Range | What it measures |
|--|--|--|--|
| `taste_alignment` | `score.py` output, `generations.jsonl`, `Group B`'s `brain_initial_score_raw` | `[-2, 2]` theoretical, typically `[-1, 1]` practical (cosine similarities are usually non-negative for image embeddings) | This image's distance from gold anchors minus distance from anti anchors. Sign matters: positive = closer to gold, negative = closer to anti. A coordinate hint, per Standing Rule #3 — not a verdict. |
| `alignment_score` | `compute_alignment.py` output, `alignment.jsonl` (Group D) | `[0, 1]` | Per-image weighted agreement between Brain's pre-eval and Aaron's final-eval over the rubric vocabulary fields. Higher = Brain's interpretation matches Aaron's. |

`taste_alignment` is "how does this image score against the anchor pool." `alignment_score` is "how well does Brain's interpretation match Aaron's." Both flow into different charts, different decision loops, different SLOs.

### Lifecycle example for a single anchor

```
1. perception_history.jsonl   appends {event_type: "perception",  review_status: "pending",       ...Group A...}
2. pre_eval_history.jsonl     appends {event_type: "pre_eval",    review_status: "pre_evaluated", ...Group B...}
3. (Aaron reviews; clarifying questions flow in chat; review_status conceptually "in_review")
4. final_eval_history.jsonl   appends {event_type: "final_eval",  review_status: "confirmed",     ...Group C...}
5. embed_anchors.py validates + embeds + appends to manifest.json
   final_eval_history.jsonl   appends {event_type: "embedded",    review_status: "embedded",      image_id: ...} (status-bump row, no field group repeated)
6. compute_alignment.py joins logs, appends to alignment.jsonl
   alignment.jsonl            appends {event_type: "alignment",   review_status: "embedded",      ...Group D...}
```

---

## `manifest.json` entry shape

Top-level structure (per plan 04 step 7):

```json
{
  "description": "Anchor tags for state-aware retrieval. World DNA vs world state.",
  "world_states": ["flourishing", "sacred", "broken", "corrupted", "abandoned", "harsh", "neutral", "dna-core"],
  "tones": ["hopeful", "awe-filled", "mournful", "eerie", "tense", "oppressive", "still", "neutral"],
  "anchors": {
    "<image_id>": { ...per-anchor entry... }
  }
}
```

Per-anchor entry (one per confirmed promoted image):

```json
{
  "image_id": "sha256:abc123def456...",
  "filename": "cathedral-light-01.jpg",
  "source_path": "benchmark/anchors/gold/cathedral-light-01.jpg",
  "anchor_type": "gold",
  "image_origin": "anchor_seed",
  "created_by": "midjourney",
  "world_state": "sacred",
  "tone": "awe-filled",
  "quality_tier": "approved",
  "aaron_score": 9,
  "notes": "weathered stone, late golden light, sense of waiting and time",
  "session_id": "2026-04-28T22:00:00Z",
  "final_eval_timestamp": "2026-04-28T22:30:00Z",
  "schema_version": "v1"
}
```

`anchor_type` mirrors `anchor_promotion` (kept named `anchor_type` here for compatibility with plan 06 step 4 wording on `embed_anchors.py`).

`source_path` in `manifest.json` is **vault-relative** (e.g., `benchmark/anchors/gold/...`) — not absolute, not container-relative. This makes the manifest portable across host-vs-container reads.

### Single-inbox and file-placement rule

All incoming reference images start in:

```text
benchmark/anchors/inbox/
```

Brain must make its pre-eval `anchor_promotion` recommendation from pixels and perception data, not from a pre-sorted folder name. After Aaron confirms the final record, Brain moves only confirmed promoted anchor files into the matching anchor folder and then invokes `embed_anchors.py`:

- `gold/` for `anchor_type=gold`
- `anti/` for `anchor_type=anti`
- `aspirational/` for `anchor_type=aspirational`

`embed_anchors.py` does NOT copy or move image files. It verifies the file exists at `source_path` and refuses to embed if the path doesn't match the declared `anchor_type`'s folder. Non-promoted files and holdout benchmark files stay out of `manifest.json` and `visual_anchors`.

---

## Validator modes (`validate_eval.py`)

A single flat schema can't validate every moment in the lifecycle, because pre-eval drafts legitimately have Aaron fields missing. The validator runs in stage-specific modes.

### `--mode auto`

Routes each record by `event_type`: generation ingest rows use `generation_ingested`, perception rows use `perception`, pre-eval rows use `pre_eval`, final confirmation rows use `final_eval`, embedded status-bump rows use `lifecycle_event`, and alignment rows use `alignment`.

Use this for mixed JSONL files such as `final_eval_history.jsonl`, which can contain both confirmed final-eval rows and embedded status-bump rows.

### `--mode generation_ingested`

Required: common fields + generated-asset lineage fields. Requires `event_type: "generation_ingested"`, `review_status: "pending"`, and `image_origin: "generation"`.

This mode validates raw generated-image ingest without requiring Group A perception, Group B Brain pre-eval, Group C Aaron feedback, or Group D alignment fields. It rejects invalid prompt-intent vocab (`world_state`, `tone`) instead of silently coercing it and enforces the score-field null/scored semantics above.

### `--mode perception`

Required: common fields + Group A fields. Aaron and Brain pre-eval fields not required.
Used by `describe_image.py` after Gemini returns and before appending to `perception_history.jsonl`.

### `--mode pre_eval`

Required: common fields + Group A fields + Group B fields. Group C fields not required.
Used by Brain after producing the interpretive pre-eval, before appending to `pre_eval_history.jsonl` and before showing draft to Aaron.

### `--mode final_eval`

Required: common fields + Group A + Group C fields. Group B (Brain pre-eval) is **optional** at this mode — there are legitimate cases where Aaron directly reviews an image without a Brain pre-eval (manual curation, repair passes, override situations). Group D not required.

Used after Aaron confirms, before appending to `final_eval_history.jsonl`.

If Group B is absent for an image, alignment computation is skipped for that image (no Brain pre-eval to compare against). Alignment metrics only apply to images where both Group B and Group C exist for the same `image_id`.

### `--mode embed_ready`

Required: everything `final_eval` requires, PLUS:
- `review_status == "confirmed"`
- `anchor_promotion in {"gold", "anti", "aspirational"}`
- The anchor-promotion consistency rules listed under "Validation rules" below
- `image_id` matches `sha256(file content)` truncated to 16 hex chars
- File exists on disk at `source_path` and is in the matching anchor folder

Used by `embed_anchors.py` as the gate before any Chroma upsert. If `embed_ready` validation fails, the script returns the failure reason and refuses to embed. If `anchor_promotion == "none"`, the script returns "skipped: no promotion" without invoking the validator.

### `--mode lifecycle_event`

Used for status-bump rows (e.g., `event_type: "embedded"`) that record only a state transition without repeating Group A/B/C/D fields.

Required: common fields only. Group A/B/C/D fields are NOT required and are NOT validated. The validator must explicitly recognize `event_type` values that indicate lifecycle bumps (`"embedded"` in V1; future bump events would extend this list) and exempt them from group-field validation. If a bump row erroneously contains group fields, the validator can warn but should not fail on their presence.

Auto-detection: `validate_eval.py` may also auto-route a row to `lifecycle_event` mode if `event_type == "embedded"` (or another bump event) and the caller didn't explicitly specify mode. Brain and downstream scripts should not be tripped up by missing group fields on a lifecycle bump.

### `--mode alignment`

Required: common fields + Group D fields, with `event_type: "alignment"`. `alignment_phase` is required and must be `baseline`, `post_seed`, or `normal`.

### Validator output shape

```json
{
  "ok": true | false,
  "mode": "auto" | "generation_ingested" | "perception" | "pre_eval" | "final_eval" | "embed_ready" | "lifecycle_event",
  "errors": [
    {"field": "world_state", "reason": "value 'peaceful' not in vocab"},
    {"field": "image_id", "reason": "does not match sha256 of source_path content"}
  ]
}
```

Brain calls validator before showing draft to Aaron and before writing to logs. Aaron can call validator manually as a sanity check.

---

## Delta weighting

**V1 PROVISIONAL.** Not locked. Revisit after first batch of real review data shows whether the metric matches Aaron's creative intuition. `weighting_version: v1` is stamped on every alignment record so future re-weights remain comparable.

Each row compares a Brain pre-eval field against the corresponding Aaron final-eval field on the same `image_id`. The weighted sum is the per-image alignment score.

| Comparison | Weight | Match policy |
|--|--|--|
| `brain_initial_quality_tier` vs `quality_tier` | 0.30 | Adjacent tiers (great↔approved) → 0.5; non-adjacent → 0 |
| `brain_initial_anchor_promotion_recommendation` vs `anchor_promotion` | 0.25 | Categorical; exact match or 0. This is one of the most important signals of whether Brain understands Aaron's taste, and stays in V1. |
| `brain_initial_world_state` vs `world_state` | 0.20 | Exact or 0 |
| `brain_initial_tone` vs `tone` | 0.10 | Adjacent tones → 0.5 (adjacency table TBD on first real batch) |
| `brain_initial_failure_mode` vs `failure_mode` | 0.10 | Exact or 0 (null=null counts as match) |
| `brain_initial_tags` vs `feedback_tags` semantic similarity | 0.05 | Continuous; cosine of embedded tag strings |
| **Sum** | **1.00** | |

Per-image alignment ∈ [0, 1]. Session-level alignment = mean over images. Chart trend = session means over time, expected to rise as Brain learns Aaron's taste.

**Exclude `image_origin: "smoke_test"` records from alignment computation.** Smoke-test rows are pipeline-verification artifacts, not real taste data. They live in the eval-history logs as audit trail but must not pollute alignment metrics. `compute_alignment.py` (plan 06) and any future scoring script must filter `image_origin != "smoke_test"`.

Join rules:

- For `image_origin != "holdout_benchmark"`, join pre-eval to confirmed final-eval by `(image_id, session_id)`.
- For `image_origin == "holdout_benchmark"`, the preferred V1 benchmark path is an external holdout truth file outside the Brain-readable vault, passed to `compute_alignment.py --holdout-truth <path>`. This keeps the answer key out of Brain memory/logs before post-seed retesting. With external truth, holdout alignment uses promotion-label accuracy only and records `weighting_version: "v1-promotion-only"`.
- If no external truth file is provided, `compute_alignment.py` falls back to joining each holdout pre-eval row to the latest row for the same `image_id` where `event_type == "final_eval"` and `review_status == "confirmed"`, regardless of `session_id`. Use this fallback only for non-blind evaluation flows.
- If no confirmed final-eval ground truth exists, skip that pre-eval row and report it under `missing_ground_truth`; do not fabricate an alignment score.

`compute_alignment.py` writes `alignment.jsonl` and can render the proof charts immediately after computation. `make_chart.py` also renders these same alignment charts from `alignment.jsonl`, matching the Track 1.A brief:

```text
benchmark/charts/alignment_score_by_session.png
benchmark/charts/promotion_precision_recall.png
```

`aaron_score` is intentionally NOT in the alignment weighting (Brain doesn't pre-emit a 0–10 score); it's logged for context and for future scoring-axis variants but doesn't drive V1 alignment.

---

## Validation rules (`validate_eval.py`)

Deterministic checks, no judgment. The validator refuses to pass an entry if:

- `image_id` is missing, malformed, or doesn't match `sha256(file content)` truncated to 16 hex chars
- Any vocab field contains a value outside its locked set
- A required field is null where the schema says non-null
- A field type is wrong (e.g., `aaron_score` not an int, `canon_candidate` not a boolean)
- `anchor_promotion=gold` but `quality_tier not in {great, approved, canon}` (gold requires `great` or higher)
- `anchor_promotion=aspirational` but `quality_tier != aspirational` UNLESS Aaron has explicitly overridden (an `approved` image saved as future inspiration is allowed; the override must be recorded in `final_notes`)
- `anchor_promotion=anti` but `quality_tier != bad` (anti is for `bad` exemplars only)
- `quality_tier=canon` written by anyone other than Aaron through explicit canon governance (plan 07)
- `anchor_promotion=none` is valid for any `quality_tier` — most reviewed images stay `none`

Validator returns `{"ok": true, "errors": []}` or `{"ok": false, "errors": [...]}` with specific field/reason per error. Brain calls validator before showing draft to Aaron and before writing to logs.

---

## Quality smoke test (build gate)

Before `validate_eval.py` and `embed_anchors.py` are built, `describe_image.py` must pass a quality smoke test:

1. Run `describe_image.py` inside the Brain container against the container path `/workspace/series-vault/raw/reference-images/vision-smoke-test.jpg`. (Host path is `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault/raw/reference-images/vision-smoke-test.jpg`, used only as historical reference for the earlier `vision_analyze` host-path test. `describe_image.py` runs in-container and uses container paths.)
2. Compare the perception report to the `vision_analyze` output captured during the vision-availability smoke test (the description that caught the gecko, bioluminescent markings, weathered bark, metallic title text "THE BREATH OF THE VALLEY", misty palette).
3. Pass criteria: the perception report catches at least equivalent detail. Specifically must mention: the small creature, its bioluminescent/glowing markings, the dominant tree trunk, the misty/atmospheric background palette, and the title text. (Smoke test was originally run against Gemini 3.1 Pro Preview on 2026-04-29 and passed; see PROJECT-STATE log.)
4. If Gemini visibly misses these obvious details — STOP. Do not build the rest of the pipeline. Reassess the perception prompt or the model choice.

After the smoke test passes, `vision-smoke-test.jpg` should be deleted before plan 04 commit (it's a throwaway test fixture, not a curated reference image). Same for any throwaway probe scripts (`list_embed_models.py` from the early embedding-model discovery test). Verify no `.DS_Store` files have crept into the staged tree before commit (run `find . -name .DS_Store` from the vault root and remove any found; the `.gitignore` should already exclude them, but worth a manual sweep). PROJECT-STATE update at plan 04 commit time should record the smoke-test outcome and the Gemini 3.x preview family capability addition (initial default `gemini-3.1-pro-preview`, swapped to `gemini-3-flash-preview` on 2026-04-29 by Aaron decision based on external benchmark research; domain-specific A/B against the original smoke fixture deferred — see PROJECT-STATE).

This gate exists because Gemini's perception report is the only visual evidence Brain ever reads. If perception is poor, every downstream judgment is poisoned.

---

## Versioning

- `schema_version: v1` — bump on field additions/removals/semantic changes
- `perception_prompt_version: v1` — bump when `describe_image.py`'s prompt to Gemini changes
- `weighting_version: v1` — bump when delta weights change

Every JSONL record stamps the versions in effect when it was written. This lets us reprocess old data or compute alignment under updated weights without losing historical comparability.

---

## Forward compatibility

This schema covers plan 04 (anchor seeding) and plan 06 (generation review) without rewriting. Plan 06 ingestion (`ingest_batch.py`) populates the same Group A + Group B fields per generated image; `apply_feedback.py` populates Group C; `create_alignment_summary.py` populates Group D. The fields are identical between anchor seeding and generation review — only the source of the image differs (curated reference vs system output).

If plan 06 reveals a needed field that doesn't exist here, bump `schema_version` to v2 and document the addition in the activity log.

---

## What this document does NOT cover

- Job packet / handoff contract (see plan 05)
- Canon governance flow (see plan 07)
- Flow Arm result manifest contract (see flow-arm plan 05)
- Boot Clean rules (see plan 08)
- Heartbeat / status file format (see plan 06 step 12)

If a question about evaluation data isn't answered here, check those plans before inventing a new convention.
