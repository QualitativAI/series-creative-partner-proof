# 03 - Provider And Browser Auth Plan

## Purpose

Authenticate Flow Arm for its two required external surfaces: GPT-5.5 through Hermes OpenAI OAuth, and Google Flow / Nano Banana Pro in the browser. Flow Arm uses GPT-5.5 for orchestration and the browser for generation execution.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 1, 10.1, 12.13, 12.14, 13.3, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 6.1, 16.2, 18.2, 19, 20

## Prerequisites

- `02-docker-hermes-flowarm-profile-plan.md` has been executed.
- `flowchat` launches.
- Aaron has ChatGPT/OpenAI OAuth access.
- Aaron has Google Flow and Nano Banana Pro access.
- Any pre-existing `trajectory-hermes` profile is treated as unrelated and protected.
- Same-user concurrent execution with `trajectory-hermes` is the supported steady state; auth and browser setup must preserve that profile while `flowchat` runs beside it.

## Exact Later Execution Steps

1. Configure OpenAI provider for Flow Arm:

   ```bash
   flowarm model
   ```

   - Configure OpenAI provider via OAuth.
   - Follow the browser auth flow.
   - Set GPT-5.5 or the exact exposed equivalent as Flow Arm default.
   - Run this only as `flowarm model`, never plain `hermes model`.
   - Confirm the resulting Flow Arm auth state is under `~/.hermes/profiles/flowarm/auth.json`.
   - Do not import or reuse provider files from `trajectory-hermes`.

2. Verify:

   ```bash
   flowarm doctor
   ```

3. Launch Flow Arm:

   ```bash
   flowchat
   ```

4. Inside Flow Arm chat:

   ```text
   Use the default reasoning model and tell me which provider/model is handling this message.
   ```

   Expected: GPT-5.5 or the configured equivalent.

5. Browser login preparation:

   - Open the browser that will be used for Google Flow automation.
   - Required: use a dedicated browser profile for Flow Arm. Do not reuse the browser profile that holds `trajectory-hermes` Google or OAuth state.
   - Launch/attach Flow Arm browser automation with CDP port `9333`, not default port `9222`.
   - Use Flow Arm browser user data directory `~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile`.
   - Log into the Google account that has Flow and Nano Banana Pro access.
   - Visit Google Flow manually.
   - Confirm Nano Banana Pro is available.
   - Confirm downloads work and the download location is known.

6. Do not begin real job execution until the browser can:

   - stay logged in
   - open Google Flow
   - select/use Nano Banana Pro
   - download generated images

## Files And Folders Expected

Hermes OAuth storage is profile-scoped only if the profile wrapper is used.

```text
~/.hermes/profiles/flowarm/
~/.hermes/profiles/flowarm/auth.json
~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile/
```

Hermes docs/source indicate profile wrappers set `HERMES_HOME`, and `auth.py` stores `auth.json` under `get_hermes_home()`. Therefore `flowarm model` should use `~/.hermes/profiles/flowarm/auth.json`. Do not use plain `hermes model`, because that can target the active/default profile instead of Flow Arm. The target OpenAI browser OAuth flow's macOS Keychain behavior is not confirmed by the source reviewed here; mitigate with the dedicated Flow Arm browser profile and the Plan 07 concurrent OAuth validation.

Browser state is managed by the dedicated browser profile used for Google Flow. The exact browser profile must be documented in `~/HermesArms/flowarm/FlowArmWorkspace/logs/browser-auth-notes.md` during execution.

Do not use or modify browser state that belongs to `trajectory-hermes` workflows.

## Aaron Manual Stop Points

- Aaron must complete OpenAI OAuth.
- Aaron must confirm the auth flow is for `flowarm`, not `trajectory-hermes`.
- Aaron must use a dedicated Flow Arm browser profile and must not reuse `trajectory-hermes` browser/OAuth state.
- Aaron must confirm Flow Arm browser automation uses CDP port `9333` and `~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile`.
- Aaron must log into Google Flow manually.
- Aaron must confirm Nano Banana Pro access.
- Aaron must confirm browser downloads work.

## Validation Commands

Hermes:

```bash
flowarm doctor
```

Inside Flow Arm:

```text
Use the default reasoning model and tell me which provider/model is handling this message.
```

Browser:

- Manual confirmation: Google Flow opens.
- Manual confirmation: Nano Banana Pro is available.
- Manual confirmation: a test download can be saved.

## Expected Outputs

- Flow Arm can reason through GPT-5.5.
- Browser session is ready for Google Flow work.
- No API keys are needed in Flow Arm `.env`.
- `trajectory-hermes` provider/browser state is not reused or modified.

## Failure Handling

- If OAuth fails, rerun `flowarm model`.
- If `flowarm model` writes auth state outside `~/.hermes/profiles/flowarm/auth.json`, stop and document the behavior before continuing.
- If model identity is unclear, verify provider/default model in Hermes.
- If Google Flow login does not persist, fix browser profile/session before browser automation.
- If Nano Banana Pro is unavailable, stop and resolve account/access before continuing.

## Explicit Do Not Do Notes

- Do not use Brain OAuth/profile credentials.
- Do not use `trajectory-hermes` OAuth/profile credentials or browser state.
- Do not reuse the `trajectory-hermes` browser profile.
- Do not use Chrome CDP port `9222` for Flow Arm.
- Do not store Google passwords in the workspace.
- Do not run real generation before Google Flow download behavior is verified.
