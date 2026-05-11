# 04 - Chroma Embeddings And Anchor Plan

## Purpose

Set up visual taste memory for the Brain: Chroma collections, Gemini Embedding 2 at 3072 dimensions, initial anchor manifest, Aaron-curated reference anchors, and state-aware scoring. This is the foundation for measurable taste learning.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 8.6, 9, 11, 12.1, 12.2, 12.3, and 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 7, 8, 9, 15, and 20
- `project-purpose.md` sections on taste memory and state-aware taste memory
- `review-rubric (Final).md` sections on truthfulness, state awareness, failure modes, and anchor promotion

## Prerequisites

- `03-provider-auth-and-environment-plan.md` has been executed.
- `GEMINI_API_KEY` is available inside Brain.
- Brain container can run Python.
- Aaron has not yet needed to provide anchors for Boot Clean, but meaningful scoring requires curated anchors.

## Exact Later Execution Steps

1. Launch Brain:

   ```bash
   brain
   ```

2. Install Python dependencies inside the Brain container:

   ```text
   Run: pip install chromadb google-genai pillow matplotlib numpy
   ```

3. Create `benchmark/scripts/init_collections.py` implementing the contract below. It must:

   - use `chromadb.PersistentClient(path="/workspace/series-vault/benchmark/chroma_data")`
   - create `taste_memory`
   - create `visual_anchors`
   - print both collection counts
   - print `Ready.`

4. Run:

   ```text
   Run: python /workspace/series-vault/benchmark/scripts/init_collections.py
   ```

   Expected: both counts print and no crash, even with zero entries.

5. Create `benchmark/scripts/test_embed.py` implementing the contract below. It must:

   - create a simple in-memory image
   - call Gemini Embedding 2
   - request `output_dimensionality=3072`
   - print vector length

6. Run:

   ```text
   Run: python /workspace/series-vault/benchmark/scripts/test_embed.py
   ```

   Expected: `Vector length: 3072`.

7. Create initial `benchmark/anchors/manifest.json`:

   ```json
   {
     "description": "Anchor tags for state-aware retrieval. World DNA vs world state.",
     "world_states": ["flourishing", "sacred", "broken", "corrupted", "abandoned", "harsh", "neutral", "dna-core"],
     "tones": ["hopeful", "awe-filled", "mournful", "eerie", "tense", "oppressive", "still", "neutral"],
     "anchors": {}
   }
   ```

8. Aaron curates initial anchor and holdout images through the single inbox:

   ```text
   benchmark/anchors/inbox/
   ```

   Brain pre-evaluates every incoming reference from `inbox/` before any gold/anti/aspirational folder move. This prevents folder-name leakage during the prediction step.

   - 25-30 gold images across flourishing/sacred/hopeful, broken/dark/corrupted/harsh, and dna-core modes
   - 25-30 anti images
   - aspirational starts empty
   - roughly 10 Aaron-selected `holdout_benchmark` images for before/after proof; these may receive final ground-truth labels but must never enter `visual_anchors` or `manifest.json`

9. For every confirmed promoted non-holdout anchor image, Brain moves the file from `inbox/` to the confirmed folder, then adds an entry to `manifest.json` using exact vocabulary only:

   World states:

   ```text
   flourishing
   sacred
   broken
   corrupted
   abandoned
   harsh
   neutral
   dna-core
   ```

   Tones:

   ```text
   hopeful
   awe-filled
   mournful
   eerie
   tense
   oppressive
   still
   neutral
   ```

10. Create `benchmark/scripts/embed_anchors.py` implementing the contract below. It must:

    - read `manifest.json`
    - embed gold, anti, and aspirational folders if present
    - store `anchor_type`, `source_path`, `filename`, `world_state`, `tone`, and `notes`
    - store `created_by` and `image_origin` as flat metadata
    - use the `visual_anchors` collection
    - hard-fail with `stage: "holdout_anti_leakage"` if `image_origin == "holdout_benchmark"` and `anchor_promotion != "none"`
    - return a holdout skip response without Chroma or manifest writes if `image_origin == "holdout_benchmark"` and `anchor_promotion == "none"`

11. Create `benchmark/scripts/score.py` implementing the contract below. It must:

    - embed the target image at 3072 dims
    - retrieve anti anchors unfiltered
    - retrieve state-matching gold anchors plus `dna-core` when `world_state` is provided
    - fall back to all gold anchors if the state-specific pool is sparse
    - return `taste_alignment`, `gold_similarity`, `anti_similarity`, `brain_initial_score_raw`, `brain_initial_gold_similarity`, `brain_initial_anti_similarity`, `brain_initial_rank`, `world_state`, and `anchor_count`
    - define `brain_initial_score_raw = taste_alignment = gold_similarity - anti_similarity`
    - derive `brain_initial_rank` from `brain_initial_score_raw`
    - gracefully return missing-anchor info if gold or anti anchors are absent

12. Create `benchmark/scripts/make_chart.py` implementing the contract below. It must:

    - read `benchmark/logs/generations.jsonl`
    - create `taste_score_over_time.png`
    - create `taste_score_by_model.png`
    - print `No entries yet.` if no log rows exist

13. Commit scripts and anchor manifest:

    ```bash
    cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
    git add benchmark/
    git commit -m "Set up Chroma embeddings anchors and scoring"
    ```

## Files And Folders Expected

Expected scripts:

```text
benchmark/scripts/init_collections.py
benchmark/scripts/test_embed.py
benchmark/scripts/embed_anchors.py
benchmark/scripts/score.py
benchmark/scripts/make_chart.py
```

Expected anchor folders:

```text
benchmark/anchors/gold/
benchmark/anchors/anti/
benchmark/anchors/aspirational/
benchmark/anchors/inbox/
benchmark/anchors/manifest.json
```

Expected Chroma path:

```text
benchmark/chroma_data/
```

## Aaron Manual Stop Points

- Aaron must provide the Gemini API key before embedding tests.
- Aaron must curate reference images before scoring is meaningful.
- Aaron must approve anchor manifest state/tone tags.
- Aaron should not promote aspirational anchors before real generated images exist, unless explicitly choosing to seed them.

## Validation Commands

Collections:

```text
Run: python /workspace/series-vault/benchmark/scripts/init_collections.py
```

Embedding:

```text
Run: python /workspace/series-vault/benchmark/scripts/test_embed.py
```

Compile scripts:

```text
Run: cd /workspace/series-vault && python -m py_compile benchmark/scripts/*.py
```

Anchor manifest file check:

```text
Run: python - <<'PY'
import json
from pathlib import Path
base = Path('/workspace/series-vault/benchmark/anchors')
manifest = json.loads((base / 'manifest.json').read_text())
print(manifest['world_states'])
print(manifest['tones'])
PY
```

Charts before ingestion:

```text
Run: python /workspace/series-vault/benchmark/scripts/make_chart.py
```

Expected: `No entries yet.`

## Expected Outputs

- Empty Chroma collections initialize cleanly.
- Gemini image embedding returns 3072 dimensions.
- Anchor manifest uses exact state/tone vocabulary.
- Scoring handles missing anchors without crashing.
- Charting handles no generation log without crashing.

## Failure Handling

- If Gemini returns anything other than 3072 dimensions, stop and fix before adding vectors.
- If Chroma reports dimension mismatch, do not mix dimensions; rebuild the affected collection.
- If no anchors exist, scoring should report missing anchors, not crash.
- If state-specific anchors are sparse, scoring should fall back to all gold anchors and report the fallback.

## Explicit Do Not Do Notes

- Do not use 768-dimensional embeddings.
- Do not L2-normalize embeddings separately; Gemini Embedding 2 output is pre-normalized — do not double-normalize.
- Do not use synonyms for state/tone metadata.
- Do not put prompting knowledge in Chroma.
- Do not treat beauty as the scoring axis. The axis is truthful vs false.
