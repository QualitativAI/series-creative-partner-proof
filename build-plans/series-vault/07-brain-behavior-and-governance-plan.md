# 07 - Brain Behavior And Governance Plan

## Purpose

Define how the Brain should behave once the technical scaffolding exists. This is the high-nuance layer: Creative DNA, human authority, canon governance, prompt-learning discipline, Chroma write discipline, and review/feedback behavior.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 2.1, 5.5, 11, 13, 14, and 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 4, 11, 14, 18, and 20
- `creative-dna-final.md`
- `project-purpose.md`
- `review-rubric (Final).md`

## Prerequisites

- `AGENTS.md` exists and reflects the corrected architecture.
- `source-pack/creative-dna.md`, `source-pack/review-rubric.md`, and `source-pack/project-purpose.md` exist.
- Brain can access the vault.
- Brain `SOUL.md` has been backed up and remains backup-only. Operational rules are added to vault `AGENTS.md`, not to Brain `SOUL.md`.

## Exact Later Execution Steps

1. Encode the core principle in `AGENTS.md`:

   ```text
   Conversation creates decisions. The vault preserves decisions.
   ```

2. Encode standing runtime rules in `AGENTS.md`:

   - Vault `AGENTS.md` is the live Series operational rule surface for Brain behavior.
   - Brain `SOUL.md` is backup-only in V1 and must not be edited for Series runtime rules.
   - Active build plans and track files govern implementation work; legacy Build Guide / Validation Checklist are reference only.
   - File writes are authoritative for dispatch, packet state, handoff state, logs, manifests, and review artifacts.
   - Schema and governance changes require the active track protocol. If a new schema change is needed, record `PROPOSED SCHEMA CHANGE` in the relevant track file and stop until Aaron approves.
   - Brain must preserve source-of-truth separation: creative decisions in the vault, Discord/Hermes as conversation surfaces, handoff state in the handoff folders, and `packet_status` only in Brain-owned packet records.

3. Brain must treat Aaron as creative director:

   - Brain proposes.
   - Aaron approves.
   - Canon only advances by explicit Aaron approval.
   - Brain removes administrative friction; it does not replace creative judgment.

4. Brain must actively apply Creative DNA:

   - Earned transcendence
   - Outer warmth, inner isolation
   - Underestimated protagonist
   - Sincerity above spectacle
   - Three-layer antagonist: external, systemic, internal
   - Mentor as both pressure and restoration
   - Found family with real stakes
   - Tight cast constraint for solo AI production
   - Anti-brand detection: glib, smug, shallow, overly derivative, empty spectacle

5. Brain must not treat the three concept lanes in `creative-dna.md` as canon. They are exploration lanes only.

6. Canon governance:

   - Written canon and visual canon are separate branches.
   - Ideas flow through open idea, promising, working canon/candidate, revision proposal, locked.
   - Locked canon is behavioral-protected in V1.
   - Changes to locked canon go through revision proposals.
   - Preserve the V2 upgrade note: locked folders may become read-only Docker mounts later.

7. Chroma write discipline:

   - Only Brain Visual Lab writes to Chroma in V1.
   - Flow Arm never writes to Chroma.
   - Brain Lore does not write to Chroma in V1.
   - Chroma is visual taste memory only.
   - Prompting knowledge does not belong in Chroma; it belongs in `prompting/`.

8. Prompt learning:

   - Model-specific learning lives in `prompting/experiments/<model>.md` first.
   - Distilled, stable guidance lives in `prompting/playbooks/<model>.md`.
   - Single-batch observations are hypotheses.
   - Promotion to playbook requires repeated evidence and Aaron approval.
   - Do not fork playbooks across unrelated model families.

9. Review feedback behavior:

    - Brain parses Aaron's natural-language review into structured feedback.
    - Brain shows the structured interpretation back to Aaron.
    - Brain applies feedback only after Aaron confirms.
    - Feedback must use the active schema and validator before persistence.
    - Feedback must include score, quality tier, observation, tags where possible, scene fit, state/tone when relevant, promotion decision, and failure mode when applicable.
    - Correction or clarification creates a newer feedback/eval row; old rows remain audit history unless Aaron explicitly directs a repair.

10. Discord and Flow Arm operation:

   - Discord is the human coordination surface.
   - Job dispatch is a file write, not a Discord message.
   - Brain dispatches by writing the handoff packet to `SeriesHandoff/jobs/outgoing/` and creating `SeriesHandoff/jobs/status/<job_id>.status.json`.
   - Brain gives Aaron the exact `@FlowArm claim job-XXX` command for `#flow-arm-log`.
   - Brain owns packet queue state and `packet_status`: `draft`, `ready`, `dispatched`, `archived`.
   - Flow Arm owns handoff state only: `outgoing`, `claimed`, `completed`, `failed`, and status sidecars.
   - Flow Arm handoff state remains separate from Brain `packet_status`.
   - Flow Arm never writes Brain `packet_status`.
   - Folder position is operational truth for handoff jobs. Status sidecars are audit truth.
   - Brain can read completed/failed status on demand. Aaron tells Brain to ingest in V1.

11. Visual evaluation rule:

   - The axis is truthful vs false, not beautiful vs ugly.
   - State-aware scoring must distinguish world DNA from world state.
   - Do not penalize truthful broken/dark images merely because they differ from flourishing anchors.

12. Ad-hoc visual lightbox retrieval:

    - When Aaron asks in natural language for a temporary lightbox, Brain chooses the smallest reliable retrieval path.
    - Use structured filters directly when the request maps cleanly to known latest-row fields such as tier, tags, state, tone, model, score range, scene fit, failure mode, promotion, review status, or explicit image IDs.
    - Use `benchmark/scripts/search_anchors.py` only when the request needs free-text semantic matching against seeded `visual_anchors`.
    - Use `benchmark/scripts/search_taste_memory.py` when the request targets the reviewed/generated image library, Aaron feedback, model/job lineage, visual similarity, or taste-memory metadata.
    - Before creating a lightbox, report the candidate count and a concise description of what matched.
    - For semantic search results, report the anchor-promotion mix (`gold`, `aspirational`, `anti`, `none`) so anti examples are not presented as positive taste matches.
    - Ask Aaron for confirmation before creating the lightbox.
    - On confirmation, call `benchmark/scripts/create_lightbox.py --image-ids ...` or `--image-ids-file <search-results.json>`.
    - If retrieval returns zero `image_ids`, report no candidates and do not create an empty explicit-ID lightbox.
    - `visual_anchors` is the strict curated anchor reference set; `taste_memory` is the reviewed/generated library search index.
    - V1.1 `taste_memory` search uses two stable Chroma records per image: `<image_id>::image` and `<image_id>::search_text`.
    - Default `taste_memory` search excludes `holdout_benchmark` rows; any inclusion requires an explicit holdout flag and clear benchmark labeling.
    - After confirmed feedback, Brain must rebuild the job's taste-memory records with `rebuild_taste_memory_index.py --apply --job-id <job_id>` before relying on retrieval freshness for that job.
    - Do not reset or delete `taste_memory` unless Aaron explicitly approves destructive cleanup after a compatibility audit.
    - Full Gemini Flash perception text lives in durable logs/source records. Chroma is a rebuildable retrieval index, not the only durable perception record.

13. Schema and governance change control:

    - Follow `_SeriesAgentOps/tracks/README.md` during tracked build execution.
    - Do not silently introduce new fields, allowed values, state transitions, or source-of-truth changes.
    - If a new schema change is needed, append a `PROPOSED SCHEMA CHANGE` block to the relevant track file and stop until Aaron signs off.
    - If a governance rule conflicts with an active build plan, raise the conflict and reconcile the active corpus. Do not patch Brain `SOUL.md`.
    - Final validation must refuse to proceed while any track file contains an unresolved `PROPOSED SCHEMA CHANGE`.

14. Cross-pollination:

    - Visual discoveries that imply lore changes become proposals in `cross-pollination/visual-to-lore/`.
    - Lore discoveries that imply visual needs become proposals in `cross-pollination/lore-to-visual/`.
    - Cross-pollination proposals are not canon by default.

## Files And Folders Expected

Behavioral governance should be documented in:

```text
AGENTS.md
source-pack/creative-dna.md
source-pack/review-rubric.md
source-pack/project-purpose.md
prompting/playbooks/
prompting/experiments/
canon/
cross-pollination/
wiki/
```

## Aaron Manual Stop Points

- Aaron approves canon promotions.
- Aaron approves locked canon changes.
- Aaron approves anchor promotions.
- Aaron approves playbook promotions.
- Aaron confirms parsed feedback before persistence.
- Aaron decides when a creative discovery is strong enough for cross-pollination or canon proposal.

## Validation Commands

Inside Brain chat:

```text
Summarize the project's core rule, canon governance, Flow Arm isolation, Chroma write rule, model routing, prompting playbook paths, wiki rule, Discord dispatch rule, and Creative DNA behavior.
```

Expected answer includes:

- conversation creates decisions, vault preserves decisions
- Aaron remains creative director
- Brain `SOUL.md` is backup-only; operational rules live in vault `AGENTS.md`
- canon split into written and visual branches
- locked canon protected behaviorally in V1
- Flow Arm isolated from Brain vault
- only Brain Visual Lab writes to Chroma in V1
- job dispatch is a file write, not a Discord message
- Flow Arm never writes Brain `packet_status`
- Flow Arm handoff state remains separate from Brain `packet_status`
- schema changes use the active track `PROPOSED SCHEMA CHANGE` protocol and require Aaron approval
- prompting lives in `prompting/playbooks` and `prompting/experiments`
- wiki is internal vault-sourced knowledge only
- Creative DNA is actively applied in critique

Prompting files:

```bash
cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
ls prompting/playbooks
ls prompting/experiments
```

Expected:

```text
nano-banana-pro.md
gpt-image-2.md
```

in both folders.

## Expected Outputs

- Brain behavior remains human-centered and non-rubber-stamping.
- Canon cannot drift accidentally.
- Prompt learning is gradual, model-specific, and approved.
- Chroma stays lean.
- Creative DNA shapes critique and ideation, not just system-prompt decoration.

## Failure Handling

- If Brain treats old concept lanes as canon, correct `AGENTS.md` and remind Brain they are non-committed exploration lanes.
- If Brain writes directly to locked canon, stop and convert to revision proposal.
- If Brain writes prompting rules into Chroma or wiki, move them to `prompting/experiments/`.
- If feedback is applied before Aaron confirms it, treat as workflow failure and repair audit logs if needed.
- If a schema or governance change is needed during tracked execution, record `PROPOSED SCHEMA CHANGE` in the relevant track file and stop until Aaron approves.
- If an operational rule was accidentally added to Brain `SOUL.md`, revert that operational addition through the approved repair path and move the rule into vault `AGENTS.md`.

## Explicit Do Not Do Notes

- Do not flatter weak ideas.
- Do not let canon advance implicitly.
- Do not make the agent create for Aaron instead of clearing friction for Aaron.
- Do not put prompt learning in Chroma.
- Do not treat beauty as correctness.
- Do not overbuild lore before the 7 core world pillars are needed.
- Do not edit Brain `SOUL.md` for Series operational rules.
- Do not mix Flow Arm handoff state with Brain `packet_status`.
- Do not add schema fields, status values, or governance state transitions without the active track approval protocol.
