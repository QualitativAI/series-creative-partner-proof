# 03 - Provider Auth And Environment Plan

## Purpose

Configure the Brain environment and model/provider access after the sandbox exists. This includes Gemini, GPT-5.5, optional GPT Image 2, Ollama Cloud for Kimi K2.6, and the `brain` launcher alias.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 8.6, 9, 10, 12.18, and 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 5, 6, 7.1, and 20

## Prerequisites

- `02-brain-sandbox-and-hermes-plan.md` has been executed.
- Brain vault exists.
- `series chat` launches successfully.
- Aaron has access to:
  - Google AI Studio Gemini API key
  - ChatGPT/OpenAI OAuth account for GPT-5.5 and possibly GPT Image 2
  - Ollama Cloud account for `kimi-k2.6:cloud`

## Exact Later Execution Steps

1. Create `.env` inside the Brain vault:

   ```bash
   cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
   printf 'GEMINI_API_KEY=PASTE_YOUR_KEY_HERE\n' > .env
   ```

   Then Aaron replaces `PASTE_YOUR_KEY_HERE` with the real key.

2. Update `~/.hermes/profiles/series/config.yaml`:

   ```yaml
   docker_forward_env: ["GEMINI_API_KEY"]
   ```

3. Add the `brain` alias:

   ```bash
   echo 'alias brain="set -a && source /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault/.env && set +a && cd /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault && series chat"' >> ~/.zshrc
   source ~/.zshrc
   ```

4. Verify Gemini env forwarding:

   ```bash
   brain
   ```

   In Brain chat:

   ```text
   Run: python -c "import os; print('GEMINI_API_KEY', bool(os.environ.get('GEMINI_API_KEY')))"
   ```

   Expected: `GEMINI_API_KEY True`.

5. Configure OpenAI OAuth:

   ```bash
   series model
   ```

   - Add or reconfigure OpenAI.
   - Follow browser OAuth.
   - Set GPT-5.5 or the exposed equivalent identifier as Brain default.

6. Configure GPT Image 2 tool if Hermes exposes it:

   ```bash
   series tools
   ```

   - Reconfigure image generation.
   - Choose OpenAI.
   - Follow OAuth if needed.

7. Run:

   ```bash
   series doctor
   ```

   Expected:

   - GPT-5.5 provider works.
   - GPT Image 2 image tool appears if Hermes exposes it.

8. Treat GPT Image 2 unavailability as Yellow, not Red:

   - If GPT-5.5 works but GPT Image 2 is not exposed in Hermes, continue.
   - Do not mark the Brain build failed solely because GPT Image 2 is unavailable.
   - Keep Nano Banana Pro handoff path as the primary image generation route for Arm-side work.

9. Install/start Ollama if needed:

   ```bash
   ollama --version
   ollama serve
   ```

   If port is already in use, test the endpoint before troubleshooting.

10. Aaron signs into Ollama Cloud:

    ```bash
    ollama signin
    ```

11. Test Kimi:

    ```bash
    ollama run kimi-k2.6:cloud
    ```

12. Verify Ollama endpoint from host:

    ```bash
    curl http://localhost:11434/v1/models
    ```

13. Verify from Brain container:

    ```text
    Run: curl http://host.docker.internal:11434/v1/models
    ```

14. Configure Hermes custom OpenAI-compatible provider:

    ```bash
    series model
    ```

    - Provider name: `ollama`
    - Base URL: `http://localhost:11434/v1`
    - API key: blank if allowed, otherwise dummy value `ollama`
    - Default model: `kimi-k2.6:cloud`

15. Test Kimi route in Brain:

    ```text
    Route this task to kimi-k2.6:cloud through Ollama. Write one paragraph of lore about a ruined sanctuary, then tell me which model handled it.
    ```

## Files And Folders Expected

Expected file:

```text
/Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault/.env
```

Expected profile config:

```text
~/.hermes/profiles/series/config.yaml
```

Expected alias:

```text
brain
```

## Aaron Manual Stop Points

- Aaron must paste the Gemini API key into `.env`.
- Aaron must complete OpenAI OAuth in the browser.
- Aaron must complete Ollama Cloud signin.
- Aaron must confirm GPT Image 2 status is understood as Green or Yellow.

## Validation Commands

Gemini env:

```text
Run: python -c "import os; print('GEMINI_API_KEY', bool(os.environ.get('GEMINI_API_KEY')))"
```

OpenAI:

```bash
series doctor
```

Ollama host:

```bash
curl http://localhost:11434/v1/models
```

Ollama container:

```text
Run: curl http://host.docker.internal:11434/v1/models
```

GPT Image 2 test if exposed:

```text
Generate an image using GPT Image 2 with this prompt: "A single candle burning on a wooden table in a dark room." Save it to /workspace/series-vault/working/drafts/gpt-image2-test.png
```

## Expected Outputs

- `GEMINI_API_KEY True` inside Brain.
- GPT-5.5 routes successfully.
- Kimi route works through Ollama.
- GPT Image 2 either works or is marked Yellow.

## Failure Handling

- If `.env` is not visible inside Brain, check `docker_forward_env` and `brain` alias.
- If Ollama works on host but not inside container, use `host.docker.internal` inside container.
- If Kimi responses look like GPT, verify Hermes provider routing.
- If GPT Image 2 is unavailable, record Yellow and continue.

## Explicit Do Not Do Notes

- Do not commit `.env`.
- Do not paste secrets into Markdown plans or logs.
- Do not mark GPT Image 2 unavailable as Red if GPT-5.5 is healthy.
- Do not configure Flow Arm here.
