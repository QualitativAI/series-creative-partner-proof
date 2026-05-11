# 04 - Workspace Heartbeat Status Plan

## Purpose

Create Flow Arm status reporting so Brain can tell whether Flow Arm is idle, working, complete, or stuck. The Build Guide writes `heartbeat.json`; the validation checklist also expects `status.json`. Flow Arm should write both native shapes for compatibility.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 12.15, 12.17, 13.1, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 16.4, 16.5, 19, 20

## Prerequisites

- `02-docker-hermes-flowarm-profile-plan.md` has been executed.
- `/workspace/handoff/flowarm-status` is visible inside `flowchat`.

## Exact Later Execution Steps

1. Create `~/HermesArms/flowarm/FlowArmWorkspace/scripts/heartbeat.py`.

2. The script must write `heartbeat.json` with native Build Guide fields:

   ```json
   {
     "timestamp": "ISO8601Z",
     "status": "working",
     "current_job": "job-001",
     "current_prompt": "p01",
     "progress": "1/4",
     "note": "optional note"
   }
   ```

3. The script must also write `status.json` with checklist fields:

   ```json
   {
     "status": "working",
     "timestamp": "ISO8601Z",
     "profile": "flowarm",
     "current_job": "job-001"
   }
   ```

4. Supported status values:

   ```text
   idle
   claimed
   working
   complete
   error
   ```

5. CLI usage should support:

   ```bash
   python /workspace/flowarm/scripts/heartbeat.py idle
   python /workspace/flowarm/scripts/heartbeat.py working job-001 p01 1/4 "generating"
   python /workspace/flowarm/scripts/heartbeat.py complete job-001 "" "" "manifest written"
   python /workspace/flowarm/scripts/heartbeat.py error job-001 p02 "" "download failed"
   ```

6. Run a test heartbeat:

   ```text
   Run: python /workspace/flowarm/scripts/heartbeat.py working test-job p01 1/4 "validation heartbeat"
   ```

7. Verify files exist in handoff:

   ```text
   Run: ls /workspace/handoff/flowarm-status
   Run: cat /workspace/handoff/flowarm-status/heartbeat.json
   Run: cat /workspace/handoff/flowarm-status/status.json
   ```

## Files And Folders Expected

```text
~/HermesArms/flowarm/FlowArmWorkspace/scripts/heartbeat.py
<FLOWARM_HANDOFF_HOST_PATH>/flowarm-status/heartbeat.json
<FLOWARM_HANDOFF_HOST_PATH>/flowarm-status/status.json
```

Inside container:

```text
/workspace/flowarm/scripts/heartbeat.py
/workspace/handoff/flowarm-status/heartbeat.json
/workspace/handoff/flowarm-status/status.json
```

## Aaron Manual Stop Points

- Aaron must confirm the Brain-side reader can see status files after sync.
- Aaron should confirm whether sync latency is acceptable.

## Validation Commands

Inside `flowchat`:

```text
Run: python /workspace/flowarm/scripts/heartbeat.py working test-job p01 1/4 "validation heartbeat"
Run: cat /workspace/handoff/flowarm-status/heartbeat.json
Run: cat /workspace/handoff/flowarm-status/status.json
```

On Brain side after sync:

```text
Run: python /workspace/series-vault/benchmark/scripts/read_flowarm_status.py
```

Expected: Brain reads current status without crashing.

## Expected Outputs

- Both `heartbeat.json` and `status.json` are written.
- Both files use their native schemas.
- Brain compatibility readers can normalize either file.

## Failure Handling

- If only one file writes, update script to write both.
- If timestamps are stale, check sync latency before assuming Flow Arm is stuck.
- If Brain cannot read status, verify the two devices are sharing the same handoff folder.

## Explicit Do Not Do Notes

- Do not write status inside Brain vault.
- Do not rely on one schema only.
- Do not treat transient sync delay as job failure until the configured stuck threshold is exceeded.
