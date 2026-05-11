# 00 - Flow Arm Execution Index

## Purpose

This is the ordered index for building the Flow Arm agent on a separate device. Flow Arm is the bounded browser-execution worker for Google Flow / Nano Banana Pro. It receives job packets through the shared handoff folder, executes generation work, saves outputs, writes result manifests, and reports status. It must not see or modify the Brain vault.

This plan set is docs-only. Creating these Markdown files does not install tools or configure the other device.

Important existing-device constraint: the Flow Arm device may already have a Hermes agent profile named `trajectory-hermes`. That profile is unrelated to this project and must be treated as protected. Flow Arm setup must create and use a separate Hermes profile named `flowarm`; it must not edit, copy from, delete, rename, alias over, or otherwise depend on `trajectory-hermes`.

`flowarm` and `trajectory-hermes` are separate Hermes profiles, launched as separate agent sessions in separate Docker containers; they must never share a chat session, conversation context, transcript, memory, or in-session state.

Required steady state: `flowarm` and `trajectory-hermes` run concurrently under the same macOS user on the Flow Arm device. Docker Desktop on macOS is effectively tied to one user account for this build path, so do not re-recommend a dedicated macOS user unless Docker Desktop is replaced with a different container runtime. Safety comes from profile wrappers, separate `HERMES_HOME` directories, separate Docker containers, separate browser profiles, and explicit resource/port configuration.

## Active Source Corpus

- `_SeriesAgentOps/flow-arm-build-plans/`
- `_SeriesAgentOps/series-vault-build-plans/`
- `_SeriesAgentOps/discord/discord-setup.md`
- `project-purpose.md` sections on Brain-and-arms separation and structured handoffs

`Build-Guide-FINAL.md` and `BUILD-VALIDATION-CHECKLIST-FINAL.md` are legacy reference inputs. They are preserved unchanged; corrections live in this active plan corpus and the Discord setup document.

## Legacy reference is provenance only

`Build-Guide-FINAL.md` and `BUILD-VALIDATION-CHECKLIST-FINAL.md` are PRESERVED as historical reference. They are NOT execution inputs.

An executing agent must NOT open these files during build execution. Every active plan in `_SeriesAgentOps/` is self-contained: folder trees, file contents, JSON schemas, regex sweeps, and behavioral contracts are inlined where execution requires them.

The "Legacy Inputs Used" section at the top of each plan is a provenance citation for traceability only. Treat it like a footnote, not an instruction.

This same rule applies to external READMEs and third-party docs: use them only for tool installation troubleshooting, not for architecture decisions. Architecture decisions live in this active corpus.

If a plan appears to require legacy or external content not inlined, that is a documentation bug — surface it to Aaron and resolve via a docs reconciliation update, not by opening legacy or external files.

## Prerequisites

- These files will be copied to the Flow Arm device.
- The Flow Arm device is expected to be a MacBook Pro or equivalent Mac.
- Same macOS user setup is the supported path because `flowchat` and `trajectory-hermes` will run concurrently on the same device.
- Aaron has a Google account with Google Flow and Nano Banana Pro access.
- Aaron has ChatGPT/OpenAI OAuth access for GPT-5.5 in Hermes.
- A shared/synced `SeriesHandoff` folder exists or will be created on the Flow Arm device.
- If `trajectory-hermes` exists on the Flow Arm device, Aaron confirms it is protected and should remain functional before and after Flow Arm setup.

## Exact Later Execution Steps

Execute the plan files in this order on the Flow Arm device:

1. `01-device-prereqs-and-handoff-sync-plan.md`
2. `02-docker-hermes-flowarm-profile-plan.md`
3. `03-provider-browser-auth-plan.md`
4. `04-workspace-heartbeat-status-plan.md`
5. `05-handoff-job-claim-and-result-manifest-plan.md`
6. `06-browser-execution-stack-google-flow-plan.md`
7. `07-validation-and-first-real-job-plan.md`
8. `08-aaron-manual-checkpoints.md` as the manual companion throughout

## Post-V1 (v2) Enhancement Plans

These plans are **not part of the V1 build** and are not required for V1 completion. They are deliberate, contract-aware extensions to a running V1 system. Use the `v2.X` prefix to keep them visually separate from the numbered V1 sequence above. They should be reviewed in advance by the Brain-side (Mac Studio) reviewer so Brain knows what's coming, but they should NOT execute until V1 has shipped real jobs through the full Brain-dispatch → Flow-Arm-execute → Brain-ingest loop. Each is written so that it can be deferred indefinitely without breaking V1 and migrated against a running system rather than executed against a clean slate:

- `v2.1-model-interchangeability-plan.md` — extend the packet model whitelist from `nano-banana-pro` only to `{nano-banana-pro, nano-banana-2}`. Triggered by Google's 2026-04-28 Flow product surface change (NB2 is now default; NBP remains selectable). **V1 remains `nano-banana-pro` only** until this plan executes.
- `v2.2-multi-arm-handoff-folder-restructuring-plan.md` — restructure `SeriesHandoff/` into per-Arm subtrees so each Arm's container mounts only its own subtree. Triggered by the planned addition of a second Arm (Mid Journey Arm or other). **V1 remains on the flat `SeriesHandoff/` layout** until this plan executes.

Both plans explicitly require V1 to be live before execution. Both include explicit migration paths for the running system rather than greenfield setup steps.

## Files And Folders Expected

On the Flow Arm device, later execution creates:

```text
~/HermesArms/flowarm/
~/HermesArms/flowarm/FlowArmWorkspace/
~/.hermes/profiles/flowarm/
~/browser-harness/                  # if Browser Harness is selected
~/HermesArms/flowarm/SeriesHandoff/ # default Syncthing peer; also recorded as FLOWARM_HANDOFF_HOST_PATH
```

Inside the Flow Arm Docker container:

```text
/workspace/flowarm
/workspace/handoff
```

## Aaron Manual Stop Points

- Confirm the exact synced handoff folder path on the Flow Arm device.
- Confirm whether `trajectory-hermes` exists, record its baseline state, and preserve it.
- Start Docker Desktop and approve file sharing.
- Complete Hermes OpenAI OAuth for GPT-5.5.
- Log into Google Flow in the browser and confirm Nano Banana Pro access.
- Approve the browser execution tier after testing.
- Watch the first tiny real job and confirm downloads/manifest shape are acceptable.

## Validation Commands

After the plan corpus is copied to the Flow Arm device, verify the files:

```bash
find ./flow-arm-build-plans -maxdepth 1 -type f -name '*.md' | sort
```

Expected:
- Nine V1 plan files with numeric `NN-` prefixes: `00-flow-arm-execution-index.md` plus `01-` through `08-` (the build sequence).
- Plus zero or more post-V1 enhancement plan files with `v2.X-` prefixes (`v2.1-`, `v2.2-`, etc., as authored — see "Post-V1 (v2) Enhancement Plans" section above). At minimum, two are present at this point in the build: `v2.1-model-interchangeability-plan.md` and `v2.2-multi-arm-handoff-folder-restructuring-plan.md`.

Total markdown files in this directory will therefore be `9 + (count of v2.X enhancement plans)`. Verify the V1 nine are all present; the v2.X count grows over the project's lifetime as new enhancements are scoped.

After the build is later executed, key checks are:

```bash
flowarm doctor
flowchat
```

Inside `flowchat`:

```text
List files in /workspace/flowarm and /workspace/handoff. Then try to list /workspace/series-vault.
```

Expected: Flow Arm sees workspace and handoff, but not the Brain vault.

## Expected Outputs

- A bounded Flow Arm profile that can read handoff jobs and return result packets.
- Any pre-existing `trajectory-hermes` profile remains untouched and functional.
- A local workspace for downloads, staging, logs, and helper scripts.
- Heartbeat/status files written into shared handoff.
- Move-based handoff state under `jobs/{outgoing,claimed,completed,failed,status}/`.
- No access to Brain vault, Chroma, Creative DNA, canon, source-pack, or prompting playbooks.

## Failure Handling

- If Flow Arm can see `series-vault`, remove the vault mount immediately.
- If `trajectory-hermes` changes, breaks, loses config, or is aliased over, stop and restore it before continuing.
- If the handoff folder is not synced, fix sync before attempting real jobs.
- If Google Flow login or Nano Banana Pro access fails, pause for Aaron.
- If browser automation is unreliable, fall back through the selected browser execution tiers rather than changing the handoff contract.

## Explicit Do Not Do Notes

- Do not mount the Brain vault.
- Do not edit, delete, rename, copy from, or alias over `trajectory-hermes`.
- Do not write to Chroma.
- Do not make creative/canon decisions.
- Do not create prompt playbooks.
- Do not rename the Hermes profile; it is `flowarm`.
- Do not shadow the built-in `flowarm` command with an alias; use `flowchat`.
