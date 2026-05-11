# 07 - Validation And First Real Job Plan

## Purpose

Validate Flow Arm end to end: workspace, sandbox isolation, handoff visibility, heartbeat/status, fake result packet, and first tiny real Nano Banana Pro job.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 12.17, 13.1, 13.2, 13.4, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 16, 18.1, 18.2, 19, 20

## Prerequisites

- Plans 01 through 06 have been executed.
- Brain-side handoff can place a job in `jobs/outgoing`.
- Google Flow/Nano Banana Pro manual access is confirmed.
- If `trajectory-hermes` exists, it had a passing baseline check before Flow Arm setup.
- **Browser-harness must be reachable from inside the Flow Arm Docker container.** Chunk 4 validated browser-harness driving Flow + NBP, but did so from a host-side process, not from the Hermes Flow Arm agent itself. V1 production requires that the Hermes Flow Arm agent invokes browser-harness via its own `terminal` tool, not via a separate host-side orchestrator. Before Step 8 ("Fake claim and output creation") executes, one of the following architectures must be configured and proven by Step 7.5 below:
  - **Architecture A (preferred):** browser-harness is installed inside the Flow Arm container, OR `~/browser-harness/` is bind-mounted into the container as a third mount alongside `/workspace/flowarm` and `/workspace/handoff`. Either way, `browser-harness -c '...'` is callable from `flowchat`'s `terminal` tool.
  - **Architecture B (fallback):** the Hermes container's native `browser-cdp` tool is used instead of browser-harness. This effectively reverts the Chunk 4 tier decision from Tier 1 to Tier 3 (Hermes native browser tools). Requires re-running Chunk 4's Flow + NBP validation against the native driver before proceeding. Default: do not use Architecture B unless Architecture A proves infeasible.
  - **Architecture C (host-side orchestrator) is explicitly NOT the default for V1.** Aaron and the external review agent both confirmed during Chunk 4 review that the Hermes Flow Arm agent — not a separate host process — should drive browser-harness in production. Do not adopt Architecture C unless Aaron explicitly approves it as a fallback later.
- The Flow Arm container must be able to reach the host's CDP `9333` endpoint. From inside the container, `127.0.0.1:9333` is container-local — Architecture A invocations of `browser-harness` must use `BU_CDP_WS=ws://host.docker.internal:9333/devtools/browser/<UUID>` (or equivalent host bridge) instead of `127.0.0.1`.

## Exact Later Execution Steps

1. Workspace check:

   ```bash
   ls ~/HermesArms/flowarm/FlowArmWorkspace
   ```

2. Existing Hermes profile preservation check:

   ```bash
   if test -d ~/.hermes/profiles/trajectory-hermes; then trajectory-hermes doctor; fi
   ```

   Expected: if `trajectory-hermes` exists, it still works after Flow Arm setup.

3. Concurrent profile launch and auth contention check:

   Open both sessions at the same time:

   ```bash
   trajectory-hermes chat
   flowchat
   ```

   Keep both sessions live for at least 10 minutes. In separate terminals, run:

   ```bash
   trajectory-hermes doctor
   flowarm doctor
   if test -f ~/.hermes/profiles/trajectory-hermes/auth.json; then ls -l ~/.hermes/profiles/trajectory-hermes/auth.json; else echo "trajectory-hermes auth.json not present or not OAuth-backed"; fi
   if test -f ~/.hermes/profiles/flowarm/auth.json; then ls -l ~/.hermes/profiles/flowarm/auth.json; else echo "flowarm auth.json not present yet"; fi
   ```

   Then re-run `flowarm model` or complete one Flow Arm OAuth refresh if prompted, restart `flowchat`, and verify `trajectory-hermes doctor` still works. This catches auth-file or OAuth-state clobbering before the first real job.

4. Profile launch / continuation:

   If the Step 3 `flowchat` session is still open and healthy, continue using it. If Step 3 sessions were closed after the 10-minute validation, relaunch Flow Arm:

   ```bash
   flowchat
   ```

   Inside Flow Arm:

   ```text
   Run: python -c "print('flowarm environment reachable')"
   ```

5. Isolation check:

   ```text
   List files in /workspace/flowarm and /workspace/handoff. Then try to list /workspace/series-vault.
   ```

   Expected: `/workspace/series-vault` is not visible.

6. Handoff status check:

   ```text
   Run: python /workspace/flowarm/scripts/heartbeat.py idle
   Run: cat /workspace/handoff/flowarm-status/heartbeat.json
   Run: cat /workspace/handoff/flowarm-status/status.json
   ```

7. Fake job read check:

   - Brain places `job-001.json` in `/workspace/handoff/jobs/outgoing/`.
   - Brain creates `/workspace/handoff/jobs/status/job-001.status.json`.
   - Flow Arm reads and summarizes both files without editing `packet_status`.

7.5. **Hermes-drives-browser-harness smoke step** (added per Chunk 4 review):

   This step proves that the Hermes Flow Arm agent — running inside the flowarm container — can invoke browser-harness via its own `terminal` tool to drive Chrome on CDP 9333. Chunk 4 proved browser-harness works; this step proves the *agent itself* can drive it autonomously.

   **Pre-step container setup (one-time, before invoking flowchat):**

   For Architecture A1 (bind-mount source + container-local venv — recommended):
   1. Add `~/browser-harness:/workspace/browser-harness` to the flowarm config.yaml mounts.
   2. Restart any flowchat session so the new mount is active.
   3. Inside the container (via `flowchat` `terminal` tool, OR via `docker run` once with the same mounts), create the container-local Linux venv:

      ```bash
      python3.11 -m venv /workspace/flowarm/browser-harness-venv
      /workspace/flowarm/browser-harness-venv/bin/pip install -e /workspace/browser-harness
      ```

      Important: do NOT use `/workspace/browser-harness/.venv/` if it exists — that's the macOS host venv and its binaries are not Linux ELF. Create a separate container-local venv at the path above.

   For Architecture A2 (in-container install): the venv is pre-baked in the container image; no per-session setup needed.

   **Smoke step inside `flowchat`:**

   ```text
   Use your terminal tool to run a single browser-harness smoke test against the dedicated Chrome on CDP 9333.

   First, derive the correct CDP WebSocket URL by extracting the UUID path from /json/version and rebuilding it with the host.docker.internal bridge (Chrome reports 127.0.0.1 in webSocketDebuggerUrl, which is the container's own loopback and unreachable):

     UUID_PATH=$(curl -s http://host.docker.internal:9333/json/version \
       | python3 -c 'import json,sys,re; url=json.load(sys.stdin)["webSocketDebuggerUrl"]; print(re.sub(r"^ws://[^/]+", "", url).strip("/"))')
     export BU_CDP_WS="ws://host.docker.internal:9333/${UUID_PATH}"
     export BU_NAME=flowarm

   Then invoke browser-harness from the container-local Linux venv:

     /workspace/flowarm/browser-harness-venv/bin/browser-harness -c 'new_tab("https://example.com"); wait_for_load(); print(page_info()); capture_screenshot(path="/workspace/flowarm/logs/hermes-drove-harness-smoke.png")'

   Expected: page_info returns url=https://example.com/, title indicates Example Domain. Screenshot file appears at /workspace/flowarm/logs/hermes-drove-harness-smoke.png. No CDP attach errors. No "browser-harness not found" errors.
   ```

   Expected outcome:
   - The Hermes Flow Arm agent successfully invokes browser-harness via its terminal tool from inside the container.
   - browser-harness attaches to the host's Chrome on CDP 9333 via the `host.docker.internal` bridge with the rewritten WebSocket URL.
   - example.com navigation + page_info reports correctly.
   - Screenshot lands at `~/HermesArms/flowarm/FlowArmWorkspace/logs/hermes-drove-harness-smoke.png` on the host (because `/workspace/flowarm` is bind-mounted to that path).

   **If this step fails:** stop Plan 07 execution. Triage which Architecture (A/B) gap caused the failure. Common gaps:
   - Architecture A but browser-harness not actually installed in / accessible from the container — verify the mount and verify `/workspace/flowarm/browser-harness-venv/bin/browser-harness` exists (NOT `/workspace/browser-harness/.venv/bin/browser-harness` — that's the macOS host venv).
   - `BU_CDP_WS` still contains `127.0.0.1` instead of `host.docker.internal` — re-derive from `/json/version` using the path-extraction snippet above.
   - `host.docker.internal` not reaching the host (Linux Docker users must use a different bridge name like the gateway IP; macOS Docker Desktop should resolve `host.docker.internal` natively).
   - CDP UUID stale (Chrome was relaunched mid-session) — re-fetch.

   Aaron must approve the screenshot and the page_info output before Step 8 proceeds. This is a non-skip step — if the agent cannot autonomously drive browser-harness here, the V1 production loop's claim-driven execution is not validated, and the first real Nano Banana Pro job (Step 10) cannot be authorized.

8. Fake claim and output creation:

   - Aaron or the executing tester sends the manual claim command in `#flow-arm-log` or walks Flow Arm through the equivalent command:

     ```text
     @FlowArm claim job-001
     ```

   - Flow Arm moves:

     ```text
     /workspace/handoff/jobs/outgoing/job-001.json
     -> /workspace/handoff/jobs/claimed/job-001.json
     ```

   - Flow Arm updates `/workspace/handoff/jobs/status/job-001.status.json` with `handoff_status: "claimed"`.

   - For each prompt in fake `job-001`, generate placeholder images with PIL.
   - Stage under:

     ```text
     /workspace/flowarm/staging/job-001/prompt-pPP/
     ```

   - Write `manifest.json`.
   - Copy to:

     ```text
     /workspace/handoff/results/incoming/job-001/
     ```

   - Write status `complete`.
   - Move claimed packet to `/workspace/handoff/jobs/completed/job-001.json`.
   - Update status sidecar with `handoff_status: "completed"` and `completed_at`.

9. Brain ingestion confirmation:

   - Aaron asks Brain to ingest `job-001`.
   - Brain reads handoff status/result files and runs `ingest_batch.py job-001`.
   - Flow Arm does not run Brain ingestion.

10. First tiny real job:

   - One job.
   - One prompt.
   - One or two Nano Banana Pro images.
   - No large creative batch yet.
   - Flow Arm runs Google Flow, downloads images, stages files, writes manifest, returns results.

11. Record any browser failures and fix before larger batches.

## Files And Folders Expected

```text
~/HermesArms/flowarm/FlowArmWorkspace/
/workspace/handoff/jobs/outgoing/job-001.json
/workspace/handoff/jobs/status/job-001.status.json
/workspace/handoff/jobs/claimed/job-001.json
/workspace/handoff/jobs/completed/job-001.json
/workspace/flowarm/staging/job-001/
/workspace/handoff/results/incoming/job-001/manifest.json
/workspace/handoff/results/incoming/job-001/prompt-pPP/<images>
/workspace/handoff/flowarm-status/heartbeat.json
/workspace/handoff/flowarm-status/status.json
```

## Aaron Manual Stop Points

- Aaron must approve moving from fake output validation to real Google Flow job.
- Aaron must confirm any pre-existing `trajectory-hermes` profile still works before the first real job.
- Aaron must confirm concurrent `flowchat` and `trajectory-hermes chat` operation has passed the 10-minute validation.
- Aaron may need to intervene for Google login/CAPTCHA/2FA.
- Aaron should visually confirm the first downloaded image exists before Brain ingestion.
- **Aaron must approve the Step 7.5 Hermes-drives-browser-harness smoke step** (added per Chunk 4 review). This is a hard gate: if the Hermes Flow Arm agent cannot autonomously invoke browser-harness via its terminal tool, Step 8 (fake claim) and Step 10 (first tiny real job) MUST NOT proceed. Triage and fix the architecture-level gap before continuing.

## Validation Commands

Flow Arm workspace:

```bash
ls ~/HermesArms/flowarm/FlowArmWorkspace
```

Flow Arm environment:

```text
Run: python -c "print('flowarm environment reachable')"
```

Existing Hermes profile preservation:

```bash
if test -d ~/.hermes/profiles/trajectory-hermes; then trajectory-hermes doctor; fi
```

Concurrent execution:

```bash
trajectory-hermes doctor
flowarm doctor
if test -f ~/.hermes/profiles/trajectory-hermes/auth.json; then ls -l ~/.hermes/profiles/trajectory-hermes/auth.json; else echo "trajectory-hermes auth.json not present or not OAuth-backed"; fi
if test -f ~/.hermes/profiles/flowarm/auth.json; then ls -l ~/.hermes/profiles/flowarm/auth.json; else echo "flowarm auth.json not present yet"; fi
```

Isolation:

```text
List files in /workspace/flowarm and /workspace/handoff. Then try to list /workspace/series-vault.
```

Result packet:

```text
Run: find /workspace/handoff/results/incoming/job-001 -maxdepth 3 -type f | sort
Run: cat /workspace/handoff/results/incoming/job-001/manifest.json
```

## Expected Outputs

- Flow Arm can read outgoing jobs.
- Flow Arm can move the handoff copy through outgoing, claimed, and completed.
- Flow Arm can update the job status sidecar.
- Flow Arm can write status.
- Flow Arm can produce result packet shape Brain can ingest.
- `trajectory-hermes`, if present, still passes its baseline check.
- `flowchat` and `trajectory-hermes chat` can remain open concurrently without auth clobbering during the validation window.
- First tiny real Nano Banana Pro job succeeds before larger batches.

## Failure Handling

- Red if Flow Arm can see the Brain vault.
- Red if a previously working `trajectory-hermes` profile is broken after Flow Arm setup.
- Red if reauthenticating one profile breaks the other's OAuth/model access.
- Red if Flow Arm cannot see handoff.
- Red if manifest does not match actual files.
- Yellow if Google Flow UI requires temporary manual assistance but files and manifest are correct.
- Stop before large batches if the tiny real job fails.
- Red if Flow Arm writes claimed or completed as `packet_status` values into the packet.
- **Red if Step 7.5 fails and the Hermes Flow Arm agent cannot autonomously invoke browser-harness from inside its container.** Stop Plan 07. Triage the Architecture A vs B configuration. Do NOT proceed to Step 8 (fake claim) or Step 10 (first real job) under a host-side-orchestrator workaround unless Aaron explicitly authorizes Architecture C as a deliberate fallback (he did not, as of Chunk 4 close).

## Explicit Do Not Do Notes

- Do not run a 60-image stress test before fake and tiny real validation pass.
- Do not ingest results on Flow Arm.
- Do not modify Brain vault.
- Do not modify `trajectory-hermes`.
- Do not delete handoff jobs/results unless the Brain-side process explicitly archives them.
