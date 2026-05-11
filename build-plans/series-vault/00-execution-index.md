# 00 - Execution Index

## Purpose

This file is the ordered index for the Brain build plan corpus. The active corpus translates the legacy guide/checklist inputs into bounded execution tasks that can be run later without re-deriving the architecture.

This is a docs-only planning artifact. Creating these plan files must not create the final vault, install tools, configure profiles, write secrets, initialize Chroma, or build Flow Arm.

## Active Source Corpus

- `_SeriesAgentOps/series-vault-build-plans/`
- `_SeriesAgentOps/flow-arm-build-plans/`
- `_SeriesAgentOps/discord/discord-setup.md`
- `creative-dna-final.md`
- `project-purpose.md`
- `review-rubric (Final).md`

`Build-Guide-FINAL.md` and `BUILD-VALIDATION-CHECKLIST-FINAL.md` are legacy reference inputs. They are preserved unchanged; corrections live in this active plan corpus and the Discord setup document.

## Legacy reference is provenance only

`Build-Guide-FINAL.md` and `BUILD-VALIDATION-CHECKLIST-FINAL.md` are PRESERVED as historical reference. They are NOT execution inputs.

An executing agent must NOT open these files during build execution. Every active plan in `_SeriesAgentOps/` is self-contained: folder trees, file contents, JSON schemas, regex sweeps, and behavioral contracts are inlined where execution requires them.

The "Legacy Inputs Used" section at the top of each plan is a provenance citation for traceability only. Treat it like a footnote, not an instruction.

This same rule applies to external READMEs and third-party docs: use them only for tool installation troubleshooting, not for architecture decisions. Architecture decisions live in this active corpus.

If a plan appears to require legacy or external content not inlined, that is a documentation bug — surface it to Aaron and resolve via a docs reconciliation update, not by opening legacy or external files.

## Execution Order

Run the later build in this order:

1. `01-vault-and-source-pack-plan.md`
2. `02-brain-sandbox-and-hermes-plan.md`
3. `03-provider-auth-and-environment-plan.md`
4. `04-chroma-embeddings-and-anchor-plan.md`
5. `05-job-packet-and-handoff-contract-plan.md`
6. `06-brain-scripts-plan.md`
7. `07-brain-behavior-and-governance-plan.md`
8. `08-validation-and-boot-clean-plan.md`
9. `09-aaron-manual-checkpoints.md` as a companion checklist throughout the build

Do not skip validation inside each plan. If a step fails, stop and fix before continuing.

## Correction Ledger

The active build plans and Discord setup document are the source of truth for execution. These are the corrections carried forward from the legacy guide/checklist inputs:

- Use `/Volumes/4TB990PRO/SeriesDrive` as the current SSD root.
- Use future Brain vault path `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault`.
- Use existing handoff path `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff`.
- Keep all plan files in `/Volumes/4TB990PRO/SeriesDrive/_SeriesAgentOps/series-vault-build-plans/`, outside `SeriesAgent`.
- Do not build Flow Arm here; define only the Brain-side handoff contract.
- Do not reference removed legacy docs: `system-roadmap.md`, `master-blueprint.md`, or `future-arms-and-experiments.md`.
- Copy source-pack files with canonical names:
  - `creative-dna-final.md` to `source-pack/creative-dna.md`
  - `review-rubric (Final).md` to `source-pack/review-rubric.md`
  - `project-purpose.md` to `source-pack/project-purpose.md`
- Correct stale `wiki/prompting/` only in the future vault copy of `review-rubric.md`; leave the root `review-rubric (Final).md` untouched.
- Generate `AGENTS.md` from the inlined canonical content in `01-vault-and-source-pack-plan.md` step 10. The legacy three-doc bullets are not present in the inlined content; `source-pack/project-purpose.md` is present under "Important files to read."
- Add the Discord dispatch rule and V1 Flow Arm operational contract to generated `AGENTS.md`.
- Both `flowarm-status/` folders must exist:
  - `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault/flowarm-status/`
  - `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff/flowarm-status/`
- Dispatched packets must live in `working/job-packets/dispatched/` and also be copied to `/workspace/handoff/jobs/outgoing/`.
- Brain-owned `packet_status` is exactly `draft`, `ready`, `dispatched`, `archived`.
- Flow Arm handoff state is separate and lives in `SeriesHandoff/jobs/{outgoing,claimed,completed,failed,status}/`; Flow Arm never uses claimed or completed as Brain `packet_status` values.
- Brain creates `SeriesHandoff/jobs/status/<job_id>.status.json` at dispatch. Folder position is operational truth; the status sidecar is audit truth.
- GPT Image 2 unavailable in Hermes is Yellow, not Red, as long as GPT-5.5 and the handoff path remain healthy.
- Heartbeat/status compatibility must support both native fake schemas:
  - `heartbeat.json`: `timestamp`, `status`, `current_job`, `current_prompt`, `progress`, `note`
  - `status.json`: `status`, `timestamp`, `profile`, `current_job`
- Boot Clean is a named greenlight criterion: empty Chroma, no anchors, absent heartbeat, no generated images, and sparse state anchors must produce informative non-crashing output.

## Prerequisites

- The root files remain available at `/Volumes/4TB990PRO/SeriesDrive`.
- The legacy Build Guide and validation checklist are treated as historical reference inputs, not files to modify.
- Aaron understands that execution of this corpus later will include manual gates for OAuth, API keys, Docker file sharing, Ollama signin, reference image curation, dispatch approval, and feedback confirmation.

## Exact Later Execution Steps

1. Create the future vault only when executing `01-vault-and-source-pack-plan.md`.
2. Keep the OPS layer outside the Brain vault so the Brain container does not see build notes.
3. Execute each plan in order.
4. Use `09-aaron-manual-checkpoints.md` to know when Aaron must step in.
5. Run `08-validation-and-boot-clean-plan.md` after the build plans have created their artifacts.

## Files And Folders Expected

Later execution will create:

- `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault/`
- `/Volumes/4TB990PRO/SeriesDrive/_SeriesAgentOps/`
- Existing `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff/` remains the handoff folder.

This index file itself lives at:

- `/Volumes/4TB990PRO/SeriesDrive/_SeriesAgentOps/series-vault-build-plans/00-execution-index.md`

## Aaron Manual Stop Points

Aaron must be involved at the stop points collected in `09-aaron-manual-checkpoints.md`. The highest-impact gates are:

- Docker Desktop file sharing approval
- Gemini API key
- OpenAI OAuth
- Ollama Cloud signin
- Reference image and anchor curation
- Dispatch approval
- Parsed feedback confirmation
- Anchor, playbook, and canon promotion approval
- Obsidian vault opening after the vault exists

## Validation Commands

After the plan corpus is created:

```bash
find /Volumes/4TB990PRO/SeriesDrive/_SeriesAgentOps/series-vault-build-plans -maxdepth 1 -type f -name '*.md' | sort
```

Expected exactly ten numbered Markdown files.

```bash
rg -n 'Boot Clean|project-purpose.md|read_flowarm_status|read_heartbeat|flowarm-status|jobs/status|handoff_status|packet_status: "archived"|GPT Image 2|working/job-packets/dispatched|/workspace/handoff/jobs/outgoing|vault copy|/Volumes/4TB990PRO/SeriesDrive' /Volumes/4TB990PRO/SeriesDrive/_SeriesAgentOps/series-vault-build-plans
```

Expected: every critical decision appears in the appropriate file.

## Expected Outputs

- A complete, ordered, docs-only execution corpus.
- No final Brain vault created by plan-set creation.
- No runtime config changed by plan-set creation.
- No root guide/source files changed by plan-set creation.

## Failure Handling

- If a later executing agent finds a mismatch between these plans and the legacy Build Guide, follow these plans and preserve the legacy Build Guide unchanged.
- If validation fails because a root source file contains old text, do not edit the root file unless it is part of the active plan corpus. Correct only the future vault copy when that plan is executed.
- If a required provider is unavailable, classify according to the validation checklist: GPT Image 2 unavailable is Yellow, not Red; GPT-5.5 routing failure is Red.

## Explicit Do Not Do Notes

- Do not modify `Build-Guide-FINAL.md`.
- Do not modify `BUILD-VALIDATION-CHECKLIST-FINAL.md`.
- Do not modify root `creative-dna-final.md`, `project-purpose.md`, `review-rubric (Final).md`, or `review-rubric (Final).pdf`.
- Do not create the final `series-vault` while only creating this plan corpus.
- Do not build or configure Flow Arm in this Brain plan.
- Do not put OPS plans inside `SeriesAgent`.
