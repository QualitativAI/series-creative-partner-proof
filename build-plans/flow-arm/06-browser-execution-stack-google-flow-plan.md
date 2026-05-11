# 06 - Browser Execution Stack Google Flow Plan

## Purpose

Select and validate the browser execution method for Google Flow / Nano Banana Pro. Flow Arm's job is browser execution: submit prompts, wait for generation/upscale, download images, stage files, and write manifests.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 12.11 through 12.17, 13.3, 13.4, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 16, 18.2, 19, 20

## Prerequisites

- `03-provider-browser-auth-plan.md` has confirmed Google Flow login and Nano Banana Pro access.
- `05-handoff-job-claim-and-result-manifest-plan.md` has defined staging and manifest contract.
- Browser downloads work manually.

## Exact Later Execution Steps

1. Tier 1 test: Browser Harness.

   ```bash
   cd ~
   git clone https://github.com/browser-use/browser-harness.git
   cd browser-harness
   pip install -r requirements.txt
   ```

   Use the Browser Harness README only for tool installation troubleshooting (dependencies, Python version issues, OS-specific quirks). All architecture decisions for Tier 1 in this active plan supersede anything in the README. Specifically:

   - Connection target: the already-running Chrome/Chromium instance from step 2 below (`--remote-debugging-port=9333`, `--user-data-dir=$HOME/HermesArms/flowarm/FlowArmWorkspace/chrome-profile`).
   - Do NOT let Browser Harness launch its own browser instance.
   - Do NOT let Browser Harness write to any path outside `~/HermesArms/flowarm/FlowArmWorkspace/`.

2. Browser Harness smoke test:

   - launch Chrome/Chromium for Flow Arm with explicit CDP/profile flags:

     ```bash
     mkdir -p ~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile
     /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
       --remote-debugging-port=9333 \
       --user-data-dir="$HOME/HermesArms/flowarm/FlowArmWorkspace/chrome-profile"
     ```

     If using another Chromium-based browser, use the equivalent executable path with the same `--remote-debugging-port=9333` and `--user-data-dir="$HOME/HermesArms/flowarm/FlowArmWorkspace/chrome-profile"` flags.

   - run Browser Harness against that already-running browser/profile
   - use Flow Arm browser user data directory `~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile`
   - use Chrome CDP port `9333`, not default port `9222`
   - navigate to a simple page
   - perform a basic interaction
   - confirm Chrome CDP works

3. Google Flow Browser Harness test:

   - navigate to Google Flow
   - confirm login persists
   - submit one safe test prompt
   - wait for generation
   - download at expected resolution
   - move downloaded file into Flow Arm staging

4. Decide browser execution tier:

   - Clean success: Browser Harness is Tier 1.
   - Ambiguous: retry once.
   - Hard fail: use Tier 2 or Tier 3 instead of burning time.

5. Tier 2 fallback:

   - Browser Use official integration, if available and reliable on the Flow Arm device.

6. Tier 3 fallback:

   - Hermes native browser tools, if they can complete Google Flow interactions reliably.

7. Document the selected tier in:

   ```text
   ~/HermesArms/flowarm/FlowArmWorkspace/logs/browser-stack-decision.md
   ```

   Required content:

   ```markdown
   # Browser stack decision

   Final: Tier [N]
   Reasoning: [notes]
   Google Flow login persistence: [pass/fail]
   Nano Banana Pro access: [pass/fail]
   Download behavior: [notes]
   Implications for demo: [notes]
   ```

8. After Aaron approves the selected tier, preserve the decision for the Brain vault from the Mac Studio side.

   Flow Arm should keep its local log at `~/HermesArms/flowarm/FlowArmWorkspace/logs/browser-stack-decision.md`, but Flow Arm must not write into the Brain vault directly. From the Mac Studio side, copy the approved decision into:

   ```text
   system/browser-stack-decision.md
   ```

   within the Brain vault, then commit it with the Brain vault changes.

9. Implement or document the repeatable job execution procedure:

   - read job packet
   - for each `nano-banana-pro` target, submit `rendered_prompt`
   - generate requested count when practical
   - download images
   - rename consistently
   - stage under prompt folder
   - update heartbeat/status per prompt
   - write manifest
   - copy result folder to handoff

## Files And Folders Expected

Optional Browser Harness:

```text
~/browser-harness/
~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile/
```

Decision log:

```text
~/HermesArms/flowarm/FlowArmWorkspace/logs/browser-stack-decision.md
<BRAIN_VAULT>/system/browser-stack-decision.md   # copied from Mac Studio side after Aaron approval
```

Downloads/staging:

```text
~/HermesArms/flowarm/FlowArmWorkspace/downloads/
~/HermesArms/flowarm/FlowArmWorkspace/staging/
```

## Aaron Manual Stop Points

- Aaron must log into Google Flow.
- Aaron must confirm Nano Banana Pro access.
- Aaron must approve the selected browser execution tier after test results.
- Aaron or the Mac Studio-side agent must copy the approved browser decision into the Brain vault `system/` folder.
- Aaron may need to complete CAPTCHA, 2FA, or account prompts.

## Validation Commands

Manual/browser validation:

- Google Flow opens.
- Login persists after restart.
- Nano Banana Pro can generate.
- Image download completes.
- Downloaded file can be moved/renamed into staging.
- Browser automation uses CDP port `9333`.
- Browser automation uses `~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile`.

Flow Arm status during test:

```text
Run: python /workspace/flowarm/scripts/heartbeat.py working browser-test p01 1/1 "google flow test"
```

Decision log:

```bash
cat ~/HermesArms/flowarm/FlowArmWorkspace/logs/browser-stack-decision.md
```

Brain vault decision record, verified from the Mac Studio side:

```bash
cat <BRAIN_VAULT>/system/browser-stack-decision.md
```

## Expected Outputs

- One selected browser execution tier.
- A documented, repeatable procedure for Google Flow / Nano Banana Pro.
- Brain vault has a `system/browser-stack-decision.md` copy of the approved decision.
- At least one successful manual or automated image download before real jobs.

## Failure Handling

- If Browser Harness setup fails due to network/deps, retry with the approved installation path or fall back tiers.
- If login does not persist, fix browser profile before automation.
- If CDP port `9333` is already in use, choose another Flow Arm-specific non-default port and record it in `~/HermesArms/flowarm/FlowArmWorkspace/logs/browser-stack-decision.md`.
- If Google Flow UI changes, document the break and use manual-assisted execution until the browser procedure is repaired.
- If downloads are inconsistent, do not run large jobs.

## Explicit Do Not Do Notes

- Do not change the job packet or result manifest contract to fit browser tooling.
- Do not store credentials in scripts.
- Do not use default Chrome CDP port `9222` for Flow Arm.
- Do not reuse any `trajectory-hermes` browser profile or CDP endpoint.
- Do not proceed to a large batch before a tiny test succeeds.
- Do not let browser stack work consume the whole build if Tier 1 fails; use fallback tiers.
