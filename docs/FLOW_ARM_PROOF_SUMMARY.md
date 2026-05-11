# Flow Arm Proof Summary

Flow Arm is the dedicated execution side of the system. It runs on a separate MacBook Pro Hermes profile and handles bounded browser work for Google Flow / Nano Banana Pro while the Brain side keeps creative authority, memory, review, and canon decisions.

## What Was Proven

- A separate `flowarm` Hermes profile was created without sharing the protected `trajectory-hermes` profile.
- The Flow Arm container was mounted only to its own workspace and the synced handoff folder, not to the Brain vault.
- A dedicated Chrome profile on CDP port 9333 was used for Google Flow / Nano Banana Pro access.
- Discord mention-based claiming worked through `#flow-arm-log`.
- Real Nano Banana Pro jobs completed and produced 2K JPEG outputs.
- Returned manifests were repaired to the finalized `handoff-result.v1` schema and ingested by Brain.

## Dedicated-Device Evidence

The final dedicated-device plan corpus is included at:

- `build-plans/flow-arm/`

The two post-V1 plans are included as clearly separate enhancement plans, not V1 requirements:

- `build-plans/flow-arm/v2.1-model-interchangeability-plan.md`
- `build-plans/flow-arm/v2.2-multi-arm-handoff-folder-restructuring-plan.md`

The proof artifacts included in this repo show the result side of the loop:

- `proof-artifacts/flow-arm-validation/`
- `proof-artifacts/handoff-jobs/`
- `proof-artifacts/result-manifests/`
- `proof-artifacts/flow-arm-status/`

The validation folder includes both real dedicated-device validation jobs:

- `job-4b-flowarm-validation-001`
- `job-4b-flowarm-validation-002`

Each folder includes the job packet, status sidecar, `handoff-result.v1` manifest, and output JPEG.

## Important Notes

During final validation, two real jobs were completed end-to-end on the dedicated device. The final ops record also captured practical findings from real execution: native browser tools were used successfully in production, browser-harness remained the architecturally preferred path, heartbeat lifecycle writes needed explicit commands, and result manifests were aligned to Brain's finalized `handoff-result.v1` contract.

That is the useful proof point: this was not only a planned architecture. It ran, encountered real integration details, and was corrected into a working handoff contract.
