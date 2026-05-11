# 01 - Device Prereqs And Handoff Sync Plan

## Purpose

Prepare the Flow Arm device and shared handoff folder. The handoff folder is the only shared state between Brain and Flow Arm. Flow Arm must see handoff jobs/results/status, but not the Brain vault.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 3, 8.1 through 8.5, 12.11 through 12.12, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 16.1, 16.3, 16.6, 19, 20

## Prerequisites

- Flow Arm device is available.
- Same macOS user setup is the supported path because Docker Desktop on macOS is tied to one user account for this build path and `flowchat` must run concurrently with `trajectory-hermes`.
- Docker Desktop can be installed or is already installed.
- Hermes can be installed.
- Syncthing is the canonical sync mechanism between Mac Studio handoff and Flow Arm device handoff. The Brain-side path is:

  ```text
  /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff
  ```

## Exact Later Execution Steps

1. Confirm the macOS account that will own Flow Arm setup.

   Use the same macOS user account that runs `trajectory-hermes`. This is intentional: Aaron will run `flowchat` and `trajectory-hermes` concurrently, and Docker Desktop on macOS does not support this plan cleanly across two simultaneous macOS users. Do not switch to a dedicated macOS user unless the container runtime is changed away from Docker Desktop.

2. Set up Syncthing on the Flow Arm device.

   - install Syncthing on the Flow Arm MacBook
   - start Syncthing and open its local web UI
   - accept or initiate device pairing with the Mac Studio
   - accept or create the shared `SeriesHandoff` folder
   - set the Flow Arm local folder path to `~/HermesArms/flowarm/SeriesHandoff` unless Aaron explicitly chooses an override
   - record the exact path as `FLOWARM_HANDOFF_HOST_PATH`
   - wait until initial sync is complete before continuing

   iCloud or another sync tool is fallback-only. If Syncthing cannot be used, Aaron must explicitly approve the alternate sync mechanism and record the exact equivalent local path before Docker config is written.

3. On the Flow Arm device, choose the exact local synced handoff path and record it as:

   ```text
   FLOWARM_HANDOFF_HOST_PATH=<exact local path to SeriesHandoff on the Flow Arm device>
   ```

   Canonical default:

   ```text
   ~/HermesArms/flowarm/SeriesHandoff
   ```

   If using iCloud as an explicit fallback, the legacy path is:

   ```text
   ~/Library/Mobile Documents/com~apple~CloudDocs/SeriesHandoff
   ```

   Use whichever path is actually synced with the Brain-side handoff. Do not guess. Keep `FLOWARM_HANDOFF_HOST_PATH` as the config variable even when the canonical default is used.

4. Ensure the handoff folder contains or creates these subfolders:

   ```text
   jobs/outgoing
   jobs/claimed
   jobs/completed
   jobs/failed
   jobs/status
   results/incoming
   flowarm-status
   archive
   ```

   `jobs/outgoing`, `jobs/claimed`, `jobs/completed`, and `jobs/failed` are operational folder state. `jobs/status` holds audit sidecars.

5. Create the local Flow Arm workspace:

   ```bash
   mkdir -p ~/HermesArms/flowarm/FlowArmWorkspace/downloads
   mkdir -p ~/HermesArms/flowarm/FlowArmWorkspace/staging
   mkdir -p ~/HermesArms/flowarm/FlowArmWorkspace/logs
   mkdir -p ~/HermesArms/flowarm/FlowArmWorkspace/scripts
   mkdir -p ~/HermesArms/flowarm/logs
   mkdir -p ~/HermesArms/flowarm/scratch
   ```

6. Confirm there is no local mount or copy of the Brain vault in the Flow Arm workspace.

7. Create a tiny handoff sync test file on one device and verify it appears on the other before continuing.

## Files And Folders Expected

On Flow Arm device:

```text
~/HermesArms/flowarm/FlowArmWorkspace/downloads
~/HermesArms/flowarm/FlowArmWorkspace/staging
~/HermesArms/flowarm/FlowArmWorkspace/logs
~/HermesArms/flowarm/FlowArmWorkspace/scripts
<FLOWARM_HANDOFF_HOST_PATH>/jobs/outgoing
<FLOWARM_HANDOFF_HOST_PATH>/jobs/claimed
<FLOWARM_HANDOFF_HOST_PATH>/jobs/completed
<FLOWARM_HANDOFF_HOST_PATH>/jobs/failed
<FLOWARM_HANDOFF_HOST_PATH>/jobs/status
<FLOWARM_HANDOFF_HOST_PATH>/results/incoming
<FLOWARM_HANDOFF_HOST_PATH>/flowarm-status
```

## Aaron Manual Stop Points

- Aaron must identify and confirm `FLOWARM_HANDOFF_HOST_PATH` on the Flow Arm device.
- Aaron must confirm setup is running under the same macOS user that runs `trajectory-hermes`.
- Aaron must install/configure Syncthing on the Flow Arm device, unless explicitly approving a fallback sync tool.
- Aaron must ensure the handoff folder is actually syncing with the Brain-side handoff and that initial sync is complete.
- Aaron must explicitly approve any non-Syncthing fallback before Docker config is written.

## Validation Commands

On Flow Arm device:

```bash
ls ~/HermesArms/flowarm/FlowArmWorkspace
find "<FLOWARM_HANDOFF_HOST_PATH>" -maxdepth 3 -type d | sort
```

Expected:

- FlowArmWorkspace exists.
- Handoff shows `jobs`, `results`, and `flowarm-status`.

Sync test:

```bash
date > "<FLOWARM_HANDOFF_HOST_PATH>/flowarm-status/sync-test-from-flowarm.txt"
```

Expected: the file appears on the Mac Studio handoff folder after sync completes.

## Expected Outputs

- Local Flow Arm workspace exists.
- Shared handoff folder is confirmed and synced.
- The exact path is known before Docker profile config is written.

## Failure Handling

- If sync is not working, do not proceed to Hermes/Docker profile configuration.
- If the macOS account choice is unclear, do not proceed to Hermes/Docker profile configuration.
- If the local path contains spaces, quote it carefully in shell commands and Docker config.
- If using Syncthing, ensure Syncthing is running and the folder is fully synced. If using iCloud as a fallback, ensure the folder is downloaded locally.

## Explicit Do Not Do Notes

- Do not mount or copy the Brain vault.
- Do not use a placeholder handoff path in final config.
- Do not proceed with browser execution until handoff sync is proven.
