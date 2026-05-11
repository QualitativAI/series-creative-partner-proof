# 02 - Brain Sandbox And Hermes Plan

## Purpose

Install and configure the Brain Hermes profile so it runs inside a Docker sandbox with access only to the Brain vault and the handoff folder. This plan preserves the Build Guide's sandbox boundary and path corrections.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 4, 6, 8.3 through 8.5, 12.18, and 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 1, 3, 4, 5.1, and 20

## Prerequisites

- `01-vault-and-source-pack-plan.md` has been executed.
- Docker Desktop is installed on Mac Studio.
- Hermes is not assumed installed.
- Future vault path:
  - `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault`
- Existing handoff path:
  - `/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff`

## Exact Later Execution Steps

1. Start Docker Desktop manually if it is not running.

2. Verify Docker:

   ```bash
   docker version
   docker run hello-world
   ```

   Expected: client/server info and hello-world success.

3. Configure Docker resources:

   - Memory: at least 8 GB
   - CPU: at least 4 cores

4. Install Hermes:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
   source ~/.zshrc
   hermes --version
   hermes update
   ```

5. Create the Brain profile:

   ```bash
   hermes profile create series
   cp ~/.hermes/profiles/series/SOUL.md ~/.hermes/profiles/series/SOUL.original.backup.md
   series doctor
   ```

   Provider errors are acceptable at this point. `command not found` is not acceptable.

6. Configure Docker file sharing in Docker Desktop for:

   ```text
   /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
   /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff
   ```

7. Edit `~/.hermes/profiles/series/config.yaml` terminal section:

   ```yaml
   terminal:
     backend: docker
     cwd: /workspace/series-vault
     docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
     docker_mount_cwd_to_workspace: false
     docker_forward_env: []
     docker_volumes:
       - "/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault:/workspace/series-vault"
       - "/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff:/workspace/handoff"
     container_cpu: 2
     container_memory: 8192
     container_persistent: true
   ```

   `docker_mount_cwd_to_workspace: false` is deliberate sandbox tightening. Do not omit it.

8. Launch Brain:

   ```bash
   cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
   series chat
   ```

9. Inside Brain chat, ask:

   ```text
   List the files in the current directory.
   ```

10. Verify sandbox boundary. On host:

    ```bash
    mkdir -p ~/docker-sandbox-test
    echo "host-only-marker" > ~/docker-sandbox-test/host-only.txt
    ```

    In Brain chat:

    ```text
    Read /Users/Aaron/docker-sandbox-test/host-only.txt
    ```

    Expected: not accessible.

11. Verify handoff mount in Brain chat:

    ```text
    List files in /workspace/handoff
    ```

    Expected: at least `jobs`, `results`, and `flowarm-status`.

12. Commit an empty verification marker only after the sandbox test passes:

    ```bash
    cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
    git commit --allow-empty -m "Brain sandbox verified"
    ```

## Files And Folders Expected

Expected profile:

```text
~/.hermes/profiles/series/
```

Expected config file:

```text
~/.hermes/profiles/series/config.yaml
```

Expected visible container paths:

```text
/workspace/series-vault
/workspace/handoff
```

## Aaron Manual Stop Points

- Aaron must start Docker Desktop if it is not running.
- Aaron must approve Docker file sharing paths.
- Aaron may need to approve macOS prompts triggered by Docker or Hermes.

## Validation Commands

Host:

```bash
docker version
docker run hello-world
series doctor
```

Inside Brain chat:

```text
List the files in the current directory.
List files in /workspace/handoff.
Read /Users/Aaron/docker-sandbox-test/host-only.txt.
```

Expected:

- Docker works.
- `series doctor` runs.
- Brain sees the vault.
- Brain sees handoff.
- Brain cannot read host-only marker.

## Expected Outputs

- Hermes `series` profile exists.
- Brain Docker sandbox uses the corrected vault and handoff paths.
- Brain container cannot see arbitrary host files.
- `_SeriesAgentOps` is not visible from inside Brain.

## Failure Handling

- If Docker cannot connect, start Docker Desktop and retry.
- If the Brain can read the host-only marker, stop. The sandbox mount is too broad.
- If `/workspace/handoff` is missing, fix Docker file sharing and `docker_volumes`.
- If `series` is missing, rerun `hermes profile create series` and reload shell.

## Explicit Do Not Do Notes

- Do not edit `SOUL.md`; only back it up.
- Do not mount `/Volumes/4TB990PRO/SeriesDrive` wholesale.
- Do not mount `_SeriesAgentOps`.
- Do not use the iCloud handoff path for this Brain setup.
- Do not configure Flow Arm here.
