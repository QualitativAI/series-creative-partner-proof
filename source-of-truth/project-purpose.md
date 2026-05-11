# Project Purpose: The Human-Centered Creative Partner

**For: understanding what this project is, why it exists, and what it's trying to prove.**

---

## The short version

I'm building an AI creative partner system that does the exhausting, repetitive, administrative work of producing an AI film series so I can stay in the creative flow state instead of drowning in generation management.

This is not an agent that creates for me. It's an agent that clears the way so I can create. The human stays the creative director. The machine handles the grind.

What I'm proving is that a world-builder working alone can have a production partner that scales with them from the first flicker of a story idea all the way through episodic production, learning their taste along the way, compounding the value of every creative decision they make.

---

## The problem this actually solves

On my last major project I spent over 50 hours clicking generate buttons, waiting for renders, dragging files into folders, renaming images, tagging assets, writing tracking spreadsheets, and trying to remember which prompts produced which results. That's 50 hours I could not spend writing, directing, designing, or discovering. 50 hours of friction between me and the work.

AI filmmaking promised to remove production bottlenecks. In practice, it moved the bottleneck from "I can't afford a film crew" to "I am the film crew, the production assistant, the archivist, and the quality control department, all at once, for every single frame."

This is a silent crisis in AI-native creative work that almost no one is talking about. The tools are astonishing. The workflow around them is medieval.

---

## What I'm building

A two-agent system that splits creative direction from creative grunt work.

**The brain.** A Hermes agent profile that lives on my Mac Studio. It knows my creative identity. It maintains my story, my world, my canon, my visual taste. It orchestrates everything. It writes alongside me through Kimi K2.6 for lore and worldbuilding. It evaluates visuals through Seed 2.0 Pro. It generates concept images through GPT Image 2 via OAuth. It remembers every creative decision across sessions.

**The arm.** A second Hermes profile on a MacBook Pro. Its only job is browser execution: signing into Google Flow, running prompt batches through Nano Banana Pro, waiting for 2K upscales, downloading files, organizing them, reporting back. It's a bounded worker. It doesn't make creative decisions. It removes the manual tedium.

**The taste memory.** A Chroma vector database holding embeddings of every image ever generated or referenced, scored against my curated anchor sets through Gemini Embedding 2. The system doesn't just remember what it made. It remembers what I loved, what I rejected, what worked in context and what didn't. Every iteration, this memory gets sharper. The agent gets better at predicting what I'll like before I see it.

**The vault.** An Obsidian-compatible markdown repository on an external SSD holding canon, lore, development notes, review logs, and the creative DNA that shapes every session. It's the project's permanent, human-readable memory.

**The loop.** I give creative direction. The brain drafts visual prompts informed by everything it knows about my taste. Prompts run through two image models in parallel, Nano Banana Pro and GPT Image 2, same prompts both ways. Results come back, get scored automatically, and are presented to me pre-ranked. I give feedback in natural language via speech-to-text. The system parses my feedback into structured metadata, updates the taste memory, and iterates.

---

## The central philosophy: AI does the manual work, not the creative work

There is a seductive pattern in AI tooling right now: "I built an agent that writes my scripts for me." "I built an agent that generates my film end-to-end." "I built an agent that runs my whole creative process."

I don't want that. I don't think anyone who actually cares about creative work wants that.

What I want is a partner that absorbs the tedium so I can give more of myself to the actual creative decisions. Not an agent that makes me a bystander to my own series. An agent that makes me more effective at being the creator.

This distinction is load-bearing. Every design choice in this system reflects it:
- The agent proposes. I approve. Canon only advances by my explicit say-so.
- The agent challenges my ideas when they feel weak or generic. It does not flatter.
- The agent handles the 50 hours of clicking and dragging. I handle the 50 seconds of creative judgment that actually matter.
- The agent remembers my taste so I don't have to re-explain it. I still make the taste.

What this means in practice is that the demo isn't "watch the AI make art." The demo is: watch the AI remove friction so the human stays in the creative flow.

That is a more honest, more sustainable, more interesting story than the AI-does-everything version that has dominated the discourse. And it's a story that world-builders, game designers, indie animators, novelists building IP, anyone trying to build a universe solo, can actually use.

---

## Why this is innovative

Most AI creative tools are point solutions. An image model. A video model. A writing assistant. A generator. Each is a tool. None are partners. None of them grow with you. None of them know what you've tried, what you loved, what you rejected, what you're building toward.

Most creative agents either do everything (taking the human out of the loop) or do nothing (just chat about creative ideas without producing anything).

What's new here:

**Persistent creative identity.** The agent has a distilled document of my creative DNA and uses it actively. Not as a system prompt decoration. As a filter through which every critique, every draft, every evaluation passes. It knows my anti-goals as clearly as my goals. It can call out when an idea drifts toward my anti-brand.

**Dual-model parallel generation.** Every prompt runs through Nano Banana Pro (on Google Flow via arm) AND GPT Image 2 (via brain OAuth), same prompt both ways. Built-in A/B comparison every iteration. Over time, data emerges about which model scores higher on which prompt types. The system learns my model taste as well as my visual taste.

**Measurable taste learning.** The taste alignment score is a real number. Anchors are curated. Similarity is quantifiable. Improvement over time is chartable. I'm not just claiming "the system gets better at knowing me." I'm showing it.

**Brain-arm separation with boundaries.** The arm runs on a different device with bounded authority. It can't touch the brain's memory, canon, or vault. It receives job packets, executes, returns result packets. The architecture enforces the philosophy: the creative intelligence stays protected, the grunt work gets offloaded.

**Aspirational asset tier.** Most scoring systems are binary: good vs bad. This system has a third bucket for "beautiful but doesn't fit a current scene." Images you love that aren't right for the town you're building today become a library of inspiration for the place you haven't invented yet. Nothing good gets wasted.

**State-aware taste memory.** The scoring system distinguishes between world DNA (what fundamentally makes this world THIS world) and world state (flourishing, sacred, broken, corrupted, abandoned, harsh). A ruined sanctuary under spiritual corruption doesn't get penalized for not looking like a flourishing valley. Both are truthful to the same world. The axis is truthful vs false, not beautiful vs ugly. Most naive taste systems would teach the agent that beauty equals correct and darkness equals wrong. This one knows better.

**Genuinely modular.** Every piece can be swapped. The browser execution layer has three fallback tiers. The models can be replaced as better ones appear. The vault doesn't depend on Obsidian (Obsidian just opens it). The database is standard Chroma. The embedding model is standard Gemini. The whole system is built to evolve with the tools, not be locked to any one vendor.

---

## Why this matters for world-builders

The people who will benefit most from this aren't AI researchers or agent enthusiasts. They're world-builders.

Anyone trying to build a compelling fictional universe alone faces the same impossible math: a world worth inhabiting has thousands of details, and you are one person. Every detail you generate needs to be tracked, remembered, checked for consistency, integrated with what came before. The mental overhead of holding a universe in your head while also producing it is what breaks solo creators.

This system is a scaffold for that.

- Every character design the agent helps propose gets versioned
- Every location described in Kimi K2.6's prose gets cross-referenced with existing canon
- Every visual that hits the aspirational tier gets remembered for the region of the world it might eventually fit
- Every feedback moment sharpens the agent's model of your sensibility
- Every generation session adds to the searchable library of what your world looks like, feels like, sounds like

What this enables: a solo creator can develop worlds that rival what studios used to need departments to track. Not because the agent is doing the creative work, but because it's absorbing the administrative load that would otherwise kill the creator.

This is infrastructure for solo-built universes. I'm building it to develop my series. I'm sharing the pattern because every world-builder needs something like it.

---

## Where this expands

V1 is image generation and worldbuilding support. The architecture is built to grow.

**Near-term arms I can add:**
- Video generation arm on another dedicated device running next-gen video models, same job-packet pattern
- Reference gathering arm that trawls specific sources and surfaces visual material
- Sound design arm that generates and iterates on ambient, dialogue, score sketches
- Editorial arm that takes approved visual and video assets and assembles rough cut sequences

**Medium-term capabilities:**
- Character reference workflows, where the arm uses character reference images in generation to maintain visual consistency across scenes
- Storyboard generation from script passages, with the brain pulling relevant scoring candidates from the taste memory to pre-populate shots
- Automatic continuity checking, where the agent cross-references new lore additions against the entire canon to flag contradictions

**Long-term:**
- The taste memory becomes rich enough that the agent can pre-select from thousands of stored generations which fit any given scene, letting me storyboard episodes by drawing from my own curated visual library
- Multi-season arc planning where the agent holds the whole universe's continuity and flags when new ideas conflict with foundations laid seasons ago
- Cross-medium consistency when the series eventually expands into books, graphic novels, or games

Nothing in V1 is a throwaway. Every iteration of taste data, every piece of canon, every anchor set compounds. The system I'm building now is the same system I'll be using in five years, just with more arms attached and more data accumulated.

---

## The methodology

The methodology is specific and worth naming:

**Brain-and-arms separation.** Intelligence is centralized. Execution is distributed. The brain owns taste, canon, routing, and judgment. Arms are bounded workers on separated devices.

**Structured handoffs through shared state.** The brain writes job packets. The arm reads them, executes, writes result packets. Communication happens through versioned structured files in a shared folder, not through real-time remote control. This makes the system debuggable, auditable, and resilient.

**Retrieval-augmented creative reasoning.** Before drafting prompts or evaluating batches, the brain retrieves from taste memory: similar past successes, similar past failures, relevant canon, applicable feedback patterns. It composes its reasoning from real precedent, not just the current context.

**Explicit canon states.** Nothing becomes truth by accident. Open Idea becomes Promising becomes Approved Working Canon becomes Locked Canon only through explicit human approval. The system can't drift canon on me.

**Benchmarkable improvement.** Taste alignment scores are real, not vibes. Anchor sets are curated. Similarity is quantifiable. The claim "this system is learning my taste" is backed by charts, not adjectives.

**World DNA vs world state.** Visual taste is encoded in two layers. World DNA is what makes this world THIS world regardless of its condition: materiality, scale, atmosphere, emotional truth. World state is how that world can transform: flourishing, sacred, broken, corrupted, abandoned, harsh. The scoring system respects both. A dark or broken image can be truthful if its darkness is native to the world, and the scoring doesn't punish it for failing to look like flourishing anchors. The axis is truthful vs false, not beautiful vs ugly. This is what lets the system hold an emotionally honest range of states without collapsing into "pretty = right."

**Parallel model evaluation.** Same inputs, different models, scored against the same anchors. The system generates per-model performance data organically through use, not through a separate benchmarking phase.

**Model-agnostic infrastructure.** Every model in the stack can be swapped. When the next frontier image model appears, it becomes a new challenger evaluated on the same prompts against the same anchors. The champion for any category can change without rebuilding the system.

---

## The idea's origin

I came to this by being frustrated.

I'm an AI filmmaker. I've won festival awards for work made largely with AI tools. I've done paid collaborations with ByteDance on AI film projects. I know what this technology can do at the output layer. I also know what it takes to get there, and the cost is hidden in hours of manual labor that nobody puts in the demo reels.

The realization that changed everything: I was spending most of my creative time as a file clerk, a queue operator, a prompt typist, and a results rater. The creative work, the actual decisions that make a film feel like mine, was a small slice of my actual hours.

I tried the obvious fixes. Prompt libraries. Spreadsheets. Filename conventions. Screenshots in folders. They helped at the margin. They didn't fix the fundamental problem, which is that a human memory cannot hold a growing universe plus the production workflow plus the evaluation work plus the creative decisions all at once.

The unlock was recognizing that this is exactly what agents are supposed to do. Not "make the art." Make the artist effective. Hold the context. Run the queues. Remember the preferences. Surface the right references. Leave the human in the creative flow.

The Nous Research Hermes Agent platform gave me a substrate that could actually do this. Persistent profiles, cross-session memory, skill systems, multi-model routing, browser execution, Docker sandboxing. It was purpose-built for this kind of long-horizon, memory-rich, multi-component system.

The Kimi K2.6 integration gave me a writing partner strong enough to handle real creative text work. The GPT Image 2 OAuth integration (added to Hermes very recently) gave me a second image model I could run through the brain directly. The Browser Harness project gave me a path for making the arm's execution self-healing and learned over time.

The final piece was Gemini Embedding 2's multimodal embedding layer making taste memory quantifiable. Before that, "the agent learns your taste" was a vibe. After that, it's a chart.

The timing is what's novel. All these pieces landed in the same narrow window. V1 of this kind of system wasn't possible 18 months ago. It's barely possible now. That's why this is a frontier build.

---

## What I'm trying to demonstrate

For the hackathon, three things:

**1. This system is real and working.** Not a mockup. Not a proposal. A running, sandboxed, dual-model, recursive creative partner that I actually use to develop a real series.

**2. Taste learning is measurable.** The taste alignment chart climbs across real iterations. Same prompt categories, same anchors, different days, higher scores. The system's model of my sensibility is improving. This is the kind of claim most AI demos make without evidence. I'm bringing evidence.

**3. The human-centered pattern works.** I stay the creative director. Every canon decision is mine. Every visual promotion is mine. The agent's job is to remove friction, not to replace judgment. The demo shows a human more productive, not a human replaced.

---

## What I want people to take away

If you're an AI researcher, I want you to see that the interesting work is not in making agents more autonomous. It's in making them better partners. The architecture decisions that matter are the ones that preserve human agency while absorbing human tedium.

If you're a world-builder, solo creator, game designer, or indie animator, I want you to see that the scaffold you need to build the universe in your head actually exists now. This pattern is replicable. The tools are accessible. The workflow compounds.

If you're building on Hermes or any agent framework, I want you to see what's possible when you treat memory, routing, bounded execution, and structured feedback as first-class primitives instead of afterthoughts.

If you're watching to see whether AI-made creative work has a future that respects the work, I want you to see that it does. Not by having the AI do the creating. By having the AI clear the path so the human can.

---

## The creative flow state is the entire point

I'll end with this.

The reason any of this matters is that creative flow state is rare, fragile, and the only condition under which the best work happens. Everything that breaks flow, context switching, administrative overhead, manual repetition, friction between tools, trying to remember what you did last time, degrades the final output.

A creative partner that removes friction doesn't just save time. It protects the state in which the real work becomes possible. It keeps the creator in the mode where the series comes alive.

That's what I'm building. A partner that protects the flow. A system that compounds every decision. A workflow that scales with me as my ambition grows. An infrastructure for the kind of AI filmmaking that hasn't been possible before because nobody could hold all the pieces at once.

This is V1. The series that emerges from working this way is the real proof.
