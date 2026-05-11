# 08 - Aaron Manual Checkpoints

## Purpose

Collect every manual action Aaron must take while building Flow Arm on the separate device. The executing agent should pause at these points and wait for confirmation.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 1, 8, 10, 12.11 through 12.17, 13.3, 13.4, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 16, 18.2, 19, 20

## Prerequisites

- This file is used throughout Flow Arm setup.
- Aaron is present or reachable for account/login/sync decisions.

## Exact Later Execution Steps

1. Handoff sync setup and path confirmation:

   Syncthing is the canonical sync mechanism. Aaron must complete setup on the Flow Arm device and identify the exact local path that syncs with the Brain handoff folder.

   Aaron must:

   - install Syncthing on the Flow Arm MacBook
   - pair the Flow Arm MacBook with the Mac Studio
   - accept or configure `SeriesHandoff` as a synced folder
   - default the local folder to `~/HermesArms/flowarm/SeriesHandoff` unless explicitly choosing an override
   - wait for initial sync to complete

   If iCloud or another sync tool is used as a fallback, Aaron must explicitly approve it and complete the equivalent account, folder, and local-availability setup.

   Required value:

   ```text
   FLOWARM_HANDOFF_HOST_PATH=<exact local synced SeriesHandoff path>
   ```

2. Existing Hermes profile protection and concurrent same-user mode:

   If the Flow Arm device already has `trajectory-hermes`, Aaron must confirm it is unrelated to this project and must be preserved.

   Required same-user concurrent mode:

   - run Flow Arm setup under the same macOS user that runs `trajectory-hermes`
   - keep `trajectory-hermes` and `flowarm` as separate Hermes profiles
   - use `trajectory-hermes ...` for Trajectory Hermes and `flowarm ...` / `flowchat` for Flow Arm
   - support both chat sessions running at the same time as the steady state
   - do not re-recommend a dedicated macOS user unless Docker Desktop is replaced, because Docker Desktop on macOS is tied to one user account for this build path

   Required checks before Flow Arm setup:

   ```bash
   ls ~/.hermes/profiles
   if test -d ~/.hermes/profiles/trajectory-hermes; then trajectory-hermes doctor; fi
   ```

   Required rule: do not edit, delete, rename, copy from, alias over, or reuse `trajectory-hermes` for Flow Arm.

3. Docker Desktop:

   Aaron must:

   - open Docker Desktop
   - approve prompts
   - set resources using the concurrent memory floor: `trajectory-hermes container_memory` + 8192 MB + 4096 MB overhead
   - add file sharing for `~/HermesArms/flowarm/FlowArmWorkspace`
   - add file sharing for `FLOWARM_HANDOFF_HOST_PATH`

4. OpenAI OAuth:

   Aaron must:

   - run `flowarm model`
   - complete browser OAuth
   - confirm GPT-5.5 or equivalent is available
   - confirm the OAuth flow is for Flow Arm and is not importing or reusing `trajectory-hermes` auth state
   - confirm Flow Arm auth lands at `~/.hermes/profiles/flowarm/auth.json`

5. Google Flow:

   Aaron must:

   - open browser on Flow Arm device
   - use a dedicated Flow Arm browser profile
   - do not reuse the browser profile that holds `trajectory-hermes` Google or OAuth state
   - use Flow Arm browser user data directory `~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile`
   - use Chrome CDP port `9333`, not default port `9222`
   - log into Google account
   - open Google Flow
   - confirm Nano Banana Pro access
   - confirm download behavior
   - handle CAPTCHA, 2FA, or account prompts if needed

6. Browser execution tier:

   Aaron must approve the selected browser execution tier after testing:

   - Tier 1: Browser Harness
   - Tier 2: Browser Use official integration
   - Tier 3: Hermes native browser tools

   After approval, Aaron or the Mac Studio-side agent must copy the approved Flow Arm decision log into the Brain vault at:

   ```text
   system/browser-stack-decision.md
   ```

7. Concurrent execution checkpoint:

   Aaron must verify:

   ```text
   Flow Arm command: flowchat -> flowarm chat
   Trajectory command: trajectory-hermes chat
   Flow Arm auth file: ~/.hermes/profiles/flowarm/auth.json
   Trajectory auth file: ~/.hermes/profiles/trajectory-hermes/auth.json
   Flow Arm CDP port: 9333
   Flow Arm browser profile: ~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile
   Docker memory floor: trajectory-hermes container_memory + 8192 MB + 4096 MB overhead
   ```

   Then Aaron must keep both sessions open for at least 10 minutes and confirm both `flowarm doctor` and `trajectory-hermes doctor` still work.

8. Fake job validation:

   Aaron should confirm Brain has placed a fake job packet in the outgoing handoff folder if the Flow Arm agent cannot see one.

9. First tiny real job:

   Aaron must approve running one tiny real Nano Banana Pro job.

10. Escalation during real jobs:

   Aaron must be called in if:

   - Google login expires
   - CAPTCHA/2FA appears
   - Nano Banana Pro is unavailable
   - downloads fail
   - generated images cannot be located
   - manifest shape cannot be verified

## Files And Folders Expected

```text
~/HermesArms/flowarm/FlowArmWorkspace/
~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile/
~/HermesArms/flowarm/FlowArmWorkspace/logs/browser-stack-decision.md
~/HermesArms/flowarm/FlowArmWorkspace/scripts/heartbeat.py
~/.hermes/profiles/flowarm/auth.json        # after flowarm model/OAuth
~/HermesArms/flowarm/FlowArmWorkspace/safety-backups/trajectory-hermes/   # only if trajectory-hermes exists
<FLOWARM_HANDOFF_HOST_PATH>/jobs/outgoing/
<FLOWARM_HANDOFF_HOST_PATH>/jobs/claimed/
<FLOWARM_HANDOFF_HOST_PATH>/jobs/completed/
<FLOWARM_HANDOFF_HOST_PATH>/jobs/failed/
<FLOWARM_HANDOFF_HOST_PATH>/jobs/status/
<FLOWARM_HANDOFF_HOST_PATH>/results/incoming/
<FLOWARM_HANDOFF_HOST_PATH>/flowarm-status/
```

## Aaron Manual Stop Points

This whole file is the manual-stop guide. The executing agent must not silently continue past:

- unknown handoff path
- incomplete sync setup or Syncthing pairing
- unconfirmed same-user concurrent execution setup
- unknown or unverified `trajectory-hermes` baseline on a device where it exists
- unclear Flow Arm auth location after `flowarm model`
- failed concurrent `flowchat` and `trajectory-hermes` validation
- Docker file sharing prompts
- OpenAI OAuth
- Google Flow login/access
- browser execution tier selection
- missing Brain vault copy of `system/browser-stack-decision.md`
- first tiny real job approval
- any account/download failure

## Validation Commands

Handoff:

```bash
find "<FLOWARM_HANDOFF_HOST_PATH>" -maxdepth 3 -type d | sort
```

Flow Arm:

```bash
flowchat
```

Inside Flow Arm:

```text
Run: python /workspace/flowarm/scripts/heartbeat.py working manual-check p01 1/1 "manual checkpoint"
Run: cat /workspace/handoff/flowarm-status/status.json
```

Browser:

- Manual: Google Flow opens.
- Manual: Nano Banana Pro available.
- Manual: download succeeds.

## Expected Outputs

- Aaron knows exactly when he is needed.
- The executing agent does not invent credentials, paths, or creative decisions.
- Flow Arm setup can proceed safely on a separate device.

## Failure Handling

- If Aaron cannot confirm the handoff path, stop.
- If Aaron cannot confirm same-user concurrent operation is the target, stop.
- If Aaron cannot confirm the `trajectory-hermes` protection boundary, stop.
- If Flow Arm auth does not land in `~/.hermes/profiles/flowarm/auth.json`, stop and document the behavior before real jobs.
- If `trajectory-hermes` worked before setup but fails after setup, stop and restore it before continuing.
- If Google Flow access is unavailable, stop.
- If browser downloads fail, stop before real jobs.
- If Docker file sharing cannot be approved, stop and fix Docker setup.

## Explicit Do Not Do Notes

- Do not continue with placeholder handoff paths.
- Do not modify or reuse `trajectory-hermes`.
- Do not reuse `trajectory-hermes` OAuth, browser, Keychain-backed, or credential-pool state.
- Do not run Flow Arm through plain `hermes`; use `flowarm` or `flowchat`.
- Do not use default Chrome CDP port `9222` for Flow Arm.
- Do not store account credentials in files.
- Do not run real jobs before Aaron approves.
- Do not treat manual CAPTCHA/2FA as an automation failure; pause for Aaron.
