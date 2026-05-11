# Series Creative Partner - Kimi Review Proof

This repo is a curated proof snapshot for a working human-centered AI creative partner system built on Hermes.

The project is a two-agent creative production workflow for AI-native worldbuilding and visual development. The core idea is simple: the human stays creative director, while the agent system handles memory, production logistics, visual review, taste learning, and repetitive execution.

Kimi K2.6 is used as part of the Brain-side creative reasoning and worldbuilding loop. The larger system around it provides persistent project memory, structured handoffs, visual review packets, taste-memory indexing, and validation artifacts.

## Best Starting Points

1. Watch the full demo video.
   - X post with video: https://x.com/QualitativAi/status/2051162991962325325?s=20

2. Start with the system flow diagram:
   - `media/flow-diagram.png`

3. Skim the proof map:
   - `docs/PROOF_MAP.md`

4. Read the short project purpose:
   - `source-of-truth/project-purpose.md`

5. Review the actual build plans:
   - `build-plans/series-vault/`
   - `build-plans/flow-arm/`

6. Inspect working code:
   - `working-code/benchmark-scripts/`

7. Inspect proof artifacts:
   - `proof-artifacts/handoff-jobs/`
   - `proof-artifacts/result-manifests/`
   - `proof-artifacts/flow-arm-validation/`
   - `proof-artifacts/review-lightbox/`
   - `proof-artifacts/flow-arm-status/`
   - `docs/FLOW_ARM_PROOF_SUMMARY.md`
   - `docs/EVALUATION_SUMMARY.md`

## What This Proves

- The system was not just proposed. It was planned, implemented, tested, and used.
- The architecture separates creative reasoning from browser execution.
- Job packets and result manifests create an auditable handoff loop.
- Dedicated-device validation jobs include their job packets, status sidecars, result manifests, and output JPEGs.
- Visual outputs are reviewed through structured packets and lightboxes.
- Visual memory is not just folder storage: generated and reference images move through Gemini 3 Flash perception, Gemini Embedding 2 vectorization at 3072 dimensions, and Chroma retrieval for visual similarity, feedback search, and long-term taste memory.
- Taste learning is represented as structured feedback contracts, anchor-set logic, scoring scripts, and review workflows.
- A 31-item blind holdout check improved from a frozen 3/31 exact-label baseline to a 7/31 retest after the taste-memory workflow was implemented.
- Kimi participates in the Brain-side creative/worldbuilding layer rather than being used as a one-off chatbot.

## Scope Notes

This is not the full working vault. It is a compact review package built to show the system clearly without shipping machine-specific state or personal source material that is not needed for evaluation.

Not included:

- live `.env` files and tokens
- API keys
- the Chroma database files
- the full holdout image set and per-item answer rows
- the full evaluation archive
- raw personal creative DNA notes
- local Docker/profile state
- bulky generated-media folders
- the local Director Cockpit prototype, which was outside hackathon scope


## Current Status

The V1 system reached a working validation state: Brain-side memory/review workflows were implemented, Flow Arm completed real Nano Banana Pro handoff jobs from the dedicated device, and Brain ingested returned result manifests. This repo is the public proof package for that work.

The important point is that this is not a static demo. It is a foundation for an adaptive creative partner: each explicit review, anchor promotion, rejection, and correction can become structured memory that makes future retrieval, scoring, and prompt direction more aligned with Aaron's taste. The current Flow Arm proves the bounded-execution pattern; the architecture is designed so additional arms and model routes can be added later without changing the Brain's core role as creative memory, taste layer, and decision partner.
