# 09 - Aaron Manual Checkpoints

## Purpose

Collect every point where Aaron must act manually during the later Brain build. This keeps the build moving without pretending an agent can complete OAuth, taste curation, Obsidian inspection, or creative approvals on Aaron's behalf.

## Legacy Inputs Used

- `Build-Guide-FINAL.md` sections 1, 4, 7, 9, 10, 11, 13, 14, and 15
- `BUILD-VALIDATION-CHECKLIST-FINAL.md` sections 5, 6, 9, 11, 17, 18, and 20
- `creative-dna-final.md`
- `review-rubric (Final).md`

## Prerequisites

- This file is used throughout execution, not as a final-only checklist.
- Aaron should expect the executing agent to pause at each manual gate and report exactly what is needed.

## Exact Later Execution Steps

### 1. Docker Desktop

Aaron action:

- Launch Docker Desktop.
- Approve macOS prompts.
- Set resources to at least 8 GB memory and 4 CPU cores.
- Add Docker file sharing paths:

  ```text
  /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
  /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/SeriesHandoff
  ```

Agent resumes after:

- `docker version` and `docker run hello-world` pass.

### 2. Gemini API Key

Aaron action:

- Create or retrieve a Gemini API key from Google AI Studio.
- Paste it into:

  ```text
  /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault/.env
  ```

Expected variable:

```text
GEMINI_API_KEY=<real key>
```

Agent resumes after:

- Brain prints `GEMINI_API_KEY True`.

### 3. OpenAI OAuth

Aaron action:

- Run OAuth through Hermes when prompted by `series model`.
- Confirm GPT-5.5 or the exposed equivalent is available.
- Run image tool OAuth through `series tools` if Hermes exposes GPT Image 2.

Agent resumes after:

- GPT-5.5 works.
- GPT Image 2 is either Green or documented Yellow.

### 4. Ollama Cloud

Aaron action:

- Start or allow Ollama daemon.
- Run `ollama signin`.
- Verify `ollama run kimi-k2.6:cloud` responds.

Agent resumes after:

- `curl http://localhost:11434/v1/models` works.
- Brain can reach `http://host.docker.internal:11434/v1/models`.

### 5. Reference Image And Anchor Curation

Aaron action:

- Provide initial style/reference images before meaningful taste scoring.
- Curate 25-30 gold images and 25-30 anti images.
- Keep aspirational empty until real generations unless explicitly choosing otherwise.
- Approve state/tone tags in `benchmark/anchors/manifest.json`.

Use exact state vocabulary:

```text
flourishing
sacred
broken
corrupted
abandoned
harsh
neutral
dna-core
```

Use exact tone vocabulary:

```text
hopeful
awe-filled
mournful
eerie
tense
oppressive
still
neutral
```

Agent resumes after:

- Anchor manifest matches actual files.
- `embed_anchors.py` succeeds.

### 6. Obsidian Vault Opening

Aaron action after `series-vault` exists:

- Open Obsidian.
- Choose "Open folder as vault."
- Select:

  ```text
  /Volumes/4TB990PRO/SeriesDrive/SeriesAgent/series-vault
  ```

- Verify expected folders are visible.
- Open `source-pack/creative-dna.md`.
- Open `source-pack/review-rubric.md`.
- After fake validation, open `reviews/visual/jobs/job-001/review-manifest.json` and `reviews/visual/jobs/job-001/images/`.
- Enable or verify Dataview, Templater, and Recent Files if needed.

Agent resumes after:

- Obsidian opens the vault normally.

### 7. Job Packet Approval

Aaron action:

- Review draft job packets in `working/job-packets/drafts/`.
- Approve or request revisions.

Agent resumes after:

- Aaron explicitly approves moving the packet to `ready`.

### 8. Dispatch Approval

Aaron action:

- Review Brain preflight notes.
- Confirm model targets and rendered prompts.
- Approve dispatch.

Agent resumes after:

- Aaron explicitly approves dispatch.
- Brain moves packet to `working/job-packets/dispatched/`.
- Brain copies packet to `/workspace/handoff/jobs/outgoing/`.
- Brain creates `/workspace/handoff/jobs/status/<job_id>.status.json`.
- Brain gives Aaron the exact `@FlowArm claim job-XXX` command for `#flow-arm-log`.

### 9. Review Feedback Confirmation

Aaron action:

- Review generated images.
- Write feedback using the rubric.
- Confirm the Brain's parsed structured feedback before persistence.

Feedback should include when possible:

```text
image ID
score 0-10
quality tier
specific observation
state and tone
fits scene yes/no
promote to anchor yes/no and type
feedback tags
failure mode
```

Agent resumes after:

- Aaron confirms the structured feedback JSON.
- `apply_feedback.py` can run.

### 10. Promotion Decisions

Aaron action:

- Approve or reject anchor promotions.
- Approve or reject canon promotions.
- Approve or reject experiment-log entries.
- Approve playbook promotions only after repeated evidence unless Aaron explicitly chooses otherwise.

Agent resumes after:

- Approved changes are written to the correct durable location.

## Aaron Manual Stop Points

This entire file is the manual-stop companion for the build. The executing agent must pause for Aaron at these points:

- Docker Desktop launch, resource configuration, and file sharing approval
- Gemini API key creation and `.env` insertion
- OpenAI OAuth for GPT-5.5 and GPT Image 2 if exposed
- Ollama Cloud signin and `kimi-k2.6:cloud` confirmation
- Initial reference image curation and anchor manifest approval
- Obsidian vault opening after `series-vault` exists
- Job packet approval before `ready`
- Dispatch approval after preflight
- Structured feedback confirmation before `apply_feedback.py`
- Anchor, canon, experiment-log, and playbook promotion decisions

## Files And Folders Expected

Manual gates touch or verify:

```text
.env
benchmark/anchors/
benchmark/anchors/manifest.json
source-pack/
working/job-packets/
/workspace/handoff/jobs/outgoing/
reviews/visual/jobs/
prompting/experiments/
prompting/playbooks/
canon/
```

## Validation Commands

Gemini:

```text
Run: python -c "import os; print('GEMINI_API_KEY', bool(os.environ.get('GEMINI_API_KEY')))"
```

Anchors:

```text
Run: python /workspace/series-vault/benchmark/scripts/embed_anchors.py
```

Obsidian:

Manual visual confirmation by Aaron.

Feedback:

```text
Run: python /workspace/series-vault/benchmark/scripts/apply_feedback.py /workspace/series-vault/benchmark/logs/pending-feedback.json
```

## Expected Outputs

- Agent does not block on hidden manual assumptions.
- Aaron knows exactly when to act.
- Creative approvals remain with Aaron.
- The system can Boot Clean before real curation, then become meaningful after Aaron adds references and feedback.

## Failure Handling

- If OAuth fails, rerun Hermes provider/tool config and do not continue with provider-dependent validation.
- If anchor curation is incomplete, Boot Clean can pass but meaningful scoring remains pending.
- If Obsidian cannot open the vault, verify the folder exists and permissions are normal.
- If Aaron rejects parsed feedback, revise the structured JSON before applying.

## Explicit Do Not Do Notes

- Do not paste secrets into chat or committed files.
- Do not approve dispatch on Aaron's behalf.
- Do not promote canon on Aaron's behalf.
- Do not promote anchors without explicit approval.
- Do not treat missing reference images as a broken build; it is a pending manual taste-memory gate.
