# 02 - Docker Hermes Flowarm Profile Plan

## Purpose

Install and configure the Hermes `flowarm` profile on the Flow Arm device using Docker sandboxing. The profile mounts only the local Flow Arm workspace and the synced handoff folder.

The Flow Arm device may already contain an unrelated Hermes profile named `trajectory-hermes`. That existing profile is protected infrastructure. This plan must preserve it exactly: no edits to its profile directory, no credential reuse, no alias changes, no Docker config changes, and no project files mounted into or from it.

`flowarm` and `trajectory-hermes` are separate Hermes profiles, launched as separate agent sessions in separate Docker containers; they must never share a chat session, conversation context, transcript, memory, or in-session state.

Same-user concurrent execution is the supported configuration. Aaron will run `flowchat` and `trajectory-hermes` at the same time under the same macOS user. Docker Desktop on macOS is tied to one user account for this build path, so do not recommend a dedicated macOS user unless Docker Desktop is replaced with another container runtime. Safety comes from separate Hermes profile homes, separate Docker containers, separate browser state, explicit browser CDP port assignment, and resource sizing.

OAuth storage note: Hermes profiles use `HERMES_HOME`. The `flowarm` profile wrapper must set `HERMES_HOME=~/.hermes/profiles/flowarm`, and Hermes `auth.py` stores auth state at `get_hermes_home() / "auth.json"`. Therefore Flow Arm provider auth is expected at `~/.hermes/profiles/flowarm/auth.json` when all Flow Arm commands are run through `flowarm ...` or `flowchat`. Do not run Flow Arm OAuth through plain `hermes model` or any active-profile-dependent command. Keychain behavior for the target OpenAI browser OAuth flow is not confirmed by the source reviewed here; use the dedicated Flow Arm browser profile and post-auth validation below.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 4, 12.11 through 12.16, 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 1.3, 16.1 through 16.3, 19, 20

## Prerequisites

- `01-device-prereqs-and-handoff-sync-plan.md` has been executed.
- `FLOWARM_HANDOFF_HOST_PATH` is known.
- Docker Desktop is installed or can be installed.
- The executing shell is inside the same macOS user that runs `trajectory-hermes`.
- If `trajectory-hermes` exists, Aaron has confirmed it is unrelated to this project and must remain functional.

## Exact Later Execution Steps

1. Confirm the concurrent same-user operating mode before making Hermes changes.

   Required mode:

   - stay in the same macOS user account that runs `trajectory-hermes`
   - keep `trajectory-hermes` and `flowarm` as separate Hermes profiles
   - launch each profile only through its own wrapper command
   - support concurrent `trajectory-hermes chat` and `flowchat` sessions as the normal steady state

2. Inventory and protect any existing Hermes profiles before making changes.

   Run:

   ```bash
   hermes --version
   ls ~/.hermes/profiles
   if test -d ~/.hermes/profiles/trajectory-hermes; then trajectory-hermes doctor; fi
   trajectory-hermes config
   cat ~/.hermes/profiles/trajectory-hermes/config.yaml
   ```

   In the printed `trajectory-hermes` config, record `terminal.container_memory`. If `trajectory-hermes config` is not available, use the `cat ~/.hermes/profiles/trajectory-hermes/config.yaml` fallback.

   If `trajectory-hermes` exists, create a reference backup of its current config files before continuing:

   ```bash
   mkdir -p ~/HermesArms/flowarm/FlowArmWorkspace/safety-backups/trajectory-hermes
   if test -f ~/.hermes/profiles/trajectory-hermes/config.yaml; then cp -p ~/.hermes/profiles/trajectory-hermes/config.yaml ~/HermesArms/flowarm/FlowArmWorkspace/safety-backups/trajectory-hermes/config.yaml.before-flowarm; else echo "missing trajectory-hermes config.yaml; stop and ask Aaron"; fi
   if test -f ~/.hermes/profiles/trajectory-hermes/SOUL.md; then cp -p ~/.hermes/profiles/trajectory-hermes/SOUL.md ~/HermesArms/flowarm/FlowArmWorkspace/safety-backups/trajectory-hermes/SOUL.md.before-flowarm; else echo "missing trajectory-hermes SOUL.md; stop and ask Aaron"; fi
   ```

   These backups are for verification and emergency restore only. Do not use them as templates for Flow Arm.

3. Start Docker Desktop.

4. Verify Docker:

   ```bash
   docker version
   docker run hello-world
   ```

5. Configure Docker resources for two persistent containers:

   - Memory floor: `trajectory-hermes container_memory` + `flowarm container_memory` + at least 4 GB host overhead.
   - If `trajectory-hermes` uses 8 GB and Flow Arm uses 8 GB, allocate at least 20 GB to Docker Desktop.
   - CPU: at least 6 cores if available; do not starve either persistent container.
   - Aaron must confirm the existing `trajectory-hermes` `container_memory` before locking the Docker Desktop memory number.
   - Expected idle resource use: both profiles use `container_persistent: true`, so both containers may remain alive between chats and continue reserving Docker Desktop resources.

6. Install or update Hermes only if needed.

   If Hermes is already installed for `trajectory-hermes`, do not reinstall or update it by default because the Hermes binary is shared across profiles. Record the current version and ask Aaron before any global Hermes update.

   If Hermes is not installed, or Aaron explicitly approves the global update, run:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
   source ~/.zshrc
   hermes --version
   hermes update
   ```

   After install/update, re-check `trajectory-hermes doctor` if that profile exists. If it fails, stop and restore before creating Flow Arm.

7. Create the separate Flow Arm profile:

   First confirm no existing project profile will be overwritten:

   ```bash
   test ! -d ~/.hermes/profiles/flowarm
   ```

   Then create only the `flowarm` profile:

   ```bash
   hermes profile create flowarm
   cp ~/.hermes/profiles/flowarm/SOUL.md ~/.hermes/profiles/flowarm/SOUL.original.backup.md
   flowarm doctor
   ```

   Do not copy files from `~/.hermes/profiles/trajectory-hermes/` into `~/.hermes/profiles/flowarm/`.
   Do not use `hermes profile use flowarm` as a substitute for the wrapper; use `flowarm ...` explicitly so the profile home is unambiguous.

8. Add Flow Arm operating instructions to `~/.hermes/profiles/flowarm/SOUL.md`.

   Keep the original backup from Step 7. Add a Flow Arm-specific section with these rules:

   ```text
   Flow Arm is a bounded browser-execution worker.
   Flow Arm may read /workspace/handoff and write Flow Arm results/status.
   Flow Arm must not access the Brain vault, Chroma, canon, source-pack, or prompting playbooks.
   Flow Arm never writes Brain packet_status.
   Flow Arm claim state is represented by handoff folder position and /workspace/handoff/jobs/status/<job_id>.status.json.
   Folder position is operational truth. Status sidecar is audit truth.
   On @FlowArm claim job-XXX, follow the Claim Protocol in _SeriesAgentOps/discord/discord-setup.md and flow-arm-build-plans/05.
   ```

   Do not paste content from `trajectory-hermes` SOUL/config into Flow Arm. This is a new Flow Arm-specific instruction block only.

9. Configure Docker Desktop file sharing for:

   ```text
   /Users/<YOUR_USERNAME>/HermesArms/flowarm/FlowArmWorkspace
   <FLOWARM_HANDOFF_HOST_PATH>
   ```

10. Edit only `~/.hermes/profiles/flowarm/config.yaml`:

   ```yaml
   terminal:
     backend: docker
     cwd: /workspace/flowarm
     docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
     docker_mount_cwd_to_workspace: false
     docker_forward_env: []
     docker_volumes:
       - "/Users/<YOUR_USERNAME>/HermesArms/flowarm/FlowArmWorkspace:/workspace/flowarm"
       - "<FLOWARM_HANDOFF_HOST_PATH>:/workspace/handoff"
     container_cpu: 2
     container_memory: 8192
     container_persistent: true
   browser:
     # Verified Hermes config key: attaches browser tools to the Flow Arm CDP endpoint.
     cdp_url: "http://127.0.0.1:9333"
   ```

11. Create an empty Flow Arm `.env`:

   ```bash
   touch ~/HermesArms/flowarm/FlowArmWorkspace/.env
   ```

   Flow Arm does not need a local API key file for V1. OpenAI OAuth is managed by Hermes.
   Do not put `HERMES_HOME`, OpenAI credentials, Google credentials, or `trajectory-hermes` paths in this file.

12. Create `flowchat` alias without shadowing `flowarm` or `trajectory-hermes`.

    Before appending, check whether `flowchat` already exists:

    ```bash
    if type flowchat >/dev/null 2>&1; then echo "flowchat already exists; stop and ask Aaron"; fi
    ```

    If `flowchat` does not already exist, append the Flow Arm-only alias:

   ```bash
   echo 'alias flowchat="set -a && source ~/HermesArms/flowarm/FlowArmWorkspace/.env && set +a && cd ~/HermesArms/flowarm/FlowArmWorkspace && flowarm chat"' >> ~/.zshrc
   source ~/.zshrc
   ```

13. Launch:

    ```bash
    flowchat
    ```

14. Concurrent Execution Configuration:

    Concurrent execution is required and supported when this configuration is satisfied:

    ```text
    Flow Arm command: flowchat -> flowarm chat
    Trajectory command: trajectory-hermes chat
    Flow Arm HERMES_HOME: ~/.hermes/profiles/flowarm
    Trajectory HERMES_HOME: ~/.hermes/profiles/trajectory-hermes
    Flow Arm auth file: ~/.hermes/profiles/flowarm/auth.json
    Trajectory auth file: ~/.hermes/profiles/trajectory-hermes/auth.json
    Flow Arm browser CDP port: 9333
    Flow Arm browser user-data-dir: ~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile
    Docker memory floor: trajectory-hermes container_memory + 8192 MB + 4096 MB overhead
    ```

    Verified from Hermes docs/source: profile wrappers set `HERMES_HOME`; `auth.py` writes `auth.json` under `get_hermes_home()`; profile docs say sessions, memory, logs, gateway state, and config are profile-scoped. No global single-chat-session lock was found in the reviewed profile/auth docs; the on-device 10-minute concurrent validation in Plan 07 is still required. Open question: whether the target OpenAI browser OAuth flow writes any macOS Keychain entries outside Hermes control. Mitigation: use dedicated Flow Arm browser profile and complete the concurrent OAuth validation in Plan 07.

## Files And Folders Expected

```text
~/.hermes/profiles/flowarm/
~/.hermes/profiles/flowarm/config.yaml
~/.hermes/profiles/flowarm/SOUL.md
~/.hermes/profiles/flowarm/auth.json        # after flowarm model/OAuth
~/HermesArms/flowarm/FlowArmWorkspace/.env
~/HermesArms/flowarm/FlowArmWorkspace/chrome-profile/
~/HermesArms/flowarm/FlowArmWorkspace/safety-backups/trajectory-hermes/   # only if trajectory-hermes exists
```

Inside Flow Arm container:

```text
/workspace/flowarm
/workspace/handoff
```

## Aaron Manual Stop Points

- Aaron must start Docker Desktop and approve file sharing.
- Aaron may need to approve macOS prompts.
- Aaron must confirm same-user concurrent execution is the intended steady state.
- Aaron must confirm `trajectory-hermes` is protected before any Hermes install/update/profile work.
- Aaron must approve any global `hermes update` on a device where `trajectory-hermes` already exists.
- Aaron must approve any OAuth flow after acknowledging the remaining Keychain/browser open question.
- Aaron must confirm both profiles are launched through their wrapper commands for concurrent operation.
- Aaron must confirm the exact handoff path before it is inserted into `config.yaml`.

## Validation Commands

Host:

```bash
flowarm doctor
if test -d ~/.hermes/profiles/trajectory-hermes; then trajectory-hermes doctor; fi
if test -f ~/.hermes/profiles/flowarm/auth.json; then ls -l ~/.hermes/profiles/flowarm/auth.json; else echo "flowarm auth.json not present yet"; fi
if test -f ~/.hermes/profiles/trajectory-hermes/auth.json; then ls -l ~/.hermes/profiles/trajectory-hermes/auth.json; else echo "trajectory-hermes auth.json not present or not OAuth-backed"; fi
flowchat
```

Inside Flow Arm chat:

```text
Run: python -c "print('flowarm environment reachable')"
List files in /workspace/flowarm and /workspace/handoff. Then try to list /workspace/series-vault.
```

Expected:

- Python command works.
- `/workspace/flowarm` is visible.
- `/workspace/handoff` is visible.
- `/workspace/series-vault` is not visible.
- If `trajectory-hermes` exists, `trajectory-hermes doctor` still works after Flow Arm setup.

## Expected Outputs

- `flowarm` profile works.
- Flow Arm SOUL.md contains the claim/state ownership rules.
- `flowchat` launches the Flow Arm profile.
- `flowchat` and `trajectory-hermes chat` can be open concurrently after Plan 07 validation.
- Flow Arm has no Brain vault access.
- `trajectory-hermes`, if present, remains untouched and functional.

## Failure Handling

- If `flowchat` is missing, recreate the alias.
- If `trajectory-hermes doctor` worked before setup and fails after setup, stop immediately and restore that profile before continuing.
- If `flowarm model` writes auth state anywhere other than `~/.hermes/profiles/flowarm/auth.json`, stop and document before authenticating further.
- If `flowchat` conflicts with an existing alias or function, stop and choose a different Flow Arm-only alias.
- If Flow Arm sees `/workspace/series-vault`, remove the mount and stop.
- If handoff is missing inside the container, fix Docker file sharing and `docker_volumes`.

## Explicit Do Not Do Notes

- Do not edit `trajectory-hermes` SOUL.md. Only edit `~/.hermes/profiles/flowarm/SOUL.md` with Flow Arm-specific instructions after backing it up.
- Do not edit, delete, rename, copy from, or use `~/.hermes/profiles/trajectory-hermes/`.
- Do not run a global Hermes update on a device with `trajectory-hermes` unless Aaron explicitly approves.
- Do not use plain `hermes chat`, `hermes model`, or `hermes auth` for Flow Arm; use `flowarm chat`, `flowarm model`, and `flowarm auth` so `HERMES_HOME` is profile-scoped.
- Do not run browser automation on default CDP port `9222`; Flow Arm uses `9333`.
- Do not use `trajectory-hermes` config, OAuth files, browser state, Docker mounts, aliases, or workspace paths for Flow Arm.
- Do not mount the Brain vault.
- Do not place API keys in `~/HermesArms/flowarm/FlowArmWorkspace/.env` for V1.
- Do not alias over the built-in `flowarm` command.
