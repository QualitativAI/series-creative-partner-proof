# The Review Rubric

**A reference document for giving structured feedback on generated images, so that your taste memory develops in the direction that's actually yours.**

---

## Why this document exists

Every review session is a chance to sharpen or to blur the agent's model of your taste. Sharpen happens when your feedback is consistent, specific, and anchored in principles you can name. Blur happens when feedback is emotional, generic, or inconsistent batch-to-batch. Over twenty iterations, the difference between sharpening and blurring is the difference between an agent that truly knows you and one that drifts toward average pretty.

This rubric is here so that in the moment, when you're looking at sixty images and deciding what to say, you have a structure to fall back on. Use it as:

- A first-read document to internalize the principles (30 minutes, once)
- A cheat sheet kept open during every review session (glance at the tables, use the vocabulary)
- A source of truth when you feel uncertain about a call (come back to the decision flows)

You already have a distilled Creative DNA document. This is its operational companion.

---

## The foundational principle

Before any specific evaluation, hold this in your head:

> **The axis is truthful vs false. Not beautiful vs ugly.**

A stunning beautiful castle can be false to your world. A broken decaying village can be truthful. A dark corrupted temple can be truthful. A clean over-rendered fantasy palace can be false.

If you only reward beauty, you teach the agent that beauty equals correctness. Then when a legitimately right ruined-sanctuary-under-corruption image comes through, it will score low, and the taste memory will drift toward generic uplift. Your series needs room for both sacred beauty and broken darkness as truthful states of the same world.

The test is not "is this pretty." The test is "does this belong in the world I'm building."

---

## The three layers of evaluation

Every image you review should be considered across three separate layers. Do not collapse them.

### Layer 1: Truthfulness (does this belong?)

Does this image feel like it belongs in your world?

- **Truthful:** The image's materiality, atmosphere, scale, emotional weight, and sensibility all feel native to the world you're building. Even if the state is dark or harsh or broken, the darkness is native.
- **False:** The image belongs to a different aesthetic universe. Might be Marvel-ish, generic fantasy, too clean, too cartoonish, too grimdark-in-a-generic-way, too anime in the wrong way. It doesn't matter why; it's not yours.

This is the most important layer. An image that fails here cannot be redeemed by being beautiful.

### Layer 2: Fit (does this work for the current scene?)

If the image is truthful, does it work for the specific scene you were prompting for?

- **Fits:** The image matches the scene's requirements. If you were prompting a sacred sanctuary, it reads as sacred sanctuary. If you were prompting a corrupted village, it reads as corrupted village.
- **Doesn't fit:** The image is truthful to the world but wrong for this scene. Could be a beautiful sacred space that doesn't belong in the gritty border town you were trying to generate. Could be a dark ruined place that doesn't match the alive city you needed.

This is where the **aspirational** tier matters. A truthful-but-doesn't-fit image shouldn't be discarded. Archive it for when you discover the scene it does belong in.

### Layer 3: Execution (did the model deliver?)

If the image is truthful and fits, did the model actually render it well?

- **Clean execution:** Faces work, hands work, composition is coherent, lighting is deliberate, materials feel right, no weird AI artifacts.
- **Flawed execution:** Distorted anatomy, broken composition, muddy lighting, generic rendering, tell-tale AI artifacts (weird text, strange proportions, implausible physics).

Execution failures are recoverable; you can rerun the prompt. Truthfulness and fit failures usually mean the prompt itself needs to change.

---

## The quality tiers (operational definitions)

These are the tiers you'll actually assign. Be strict about what each means.

| Tier | Definition | Action |
|------|------------|--------|
| **bad** | False to the world, or execution is unsalvageable. | Mark as anti-reference. Informs future avoid patterns. |
| **okay** | Serviceable. Neither wrong nor memorable. | Log it, move on. Neutral data. |
| **great** | Truthful and well-executed, may or may not fit current scene. | Strong positive signal. Consider for aspirational if doesn't fit. |
| **aspirational** | Beautiful, resonant, and truthful, but doesn't fit any current scene. | Archive. Could become reference for a future place you haven't invented yet. |
| **approved** | Truthful, fits the scene, well-executed. On track to be canon. | Pending final canon approval. High-value reference. |
| **canon** | Locked as part of the series. | Reserved for the explicit act of canonization. Rare. |

**Reserve "canon" and "approved" for deliberate decisions, not hot takes.** Most review sessions should produce a lot of okay, some great, occasional aspirational, rare approved, and almost never canon. If you're marking things canon casually, the tier loses meaning.

---

## The failure modes (when it's bad, why?)

When you mark something bad or okay, the question the system needs is: **why did it fail?**

| Failure mode | What it means | What it tells the system |
|--------------|---------------|--------------------------|
| **execution** | The concept was right, the model just fumbled the rendering. Faces are weird, composition is off, artifacts are visible. | Keep the prompt, maybe rerun. Don't abandon the direction. |
| **concept** | The prompt itself was wrong. The idea it was testing isn't actually right for the world, regardless of how well rendered. | Retire this prompt. Don't rerun it. Shift direction. |
| **partial** | Some elements work, others don't. Right atmosphere but wrong architecture. Right palette but wrong materials. | Iterate the prompt. Keep what worked, change what didn't. |

This distinction is load-bearing for prompt iteration. If you never tell the system "this failed because the concept was wrong," it will keep generating variations of a dead direction.

---

## The state awareness layer

Your scoring system is state-aware. When you feed back on an image, note its world state so the system knows which state-specific anchors it should be compared against.

### The state vocabulary

| State | What it means |
|-------|---------------|
| **flourishing** | Thriving. Alive. In its prime. Prosperous. |
| **sacred** | Holy, reverent, uplifting. Places of peace, ritual, awe. |
| **broken** | Decayed, ruined, still partly standing. History visible in the damage. |
| **corrupted** | Twisted by spiritual or environmental wrongness. Distorted version of something that was once right. |
| **abandoned** | Empty, quiet, ancient. Forgotten by the living. |
| **harsh** | Wild, unwelcoming, high-stakes terrain. Nature as antagonist. |
| **neutral** | State isn't distinctive or relevant. Default if uncertain. |
| **dna-core** | Image teaches world DNA regardless of state. Always relevant in scoring. |

### The tone vocabulary

| Tone | What it means |
|------|---------------|
| **hopeful** | Warmth, possibility, light breaking through. |
| **awe-filled** | Wonder, scale, spiritual weight. |
| **mournful** | Loss, sorrow, what once was. |
| **eerie** | Unease, wrongness, something is off. |
| **tense** | Threat, coiled energy, danger imminent. |
| **oppressive** | Weight, crushing atmosphere, overwhelming. |
| **still** | Silence, quiet, contemplation. |
| **neutral** | Tone isn't distinctive or relevant. |

When you review an image, ideally note its state and tone. This helps the system cluster feedback correctly. If you're unsure, use "neutral" and move on; don't over-agonize.

---

## Dark-but-right vs dark-but-wrong

This is the single most common place feedback goes wrong. The question is not "is this image dark?" The question is "is this darkness native to my world?"

### Dark-but-right (counts as truthful, belongs in gold or approved territory)

- A ruined sanctuary where the weathered sacred stone is still legible
- A dead forest with remnants that suggest something meaningful once lived here
- A city under spiritual corruption where the original architecture is still readable beneath the decay
- A cold grim place that feels mythic, intentional, and lived-in
- A lonely wasteland with a sense of lost civilization
- An interior of a decaying temple where you can feel the history in the dust

The test: does the darkness connect to the world's DNA? Does it feel like it grew from the same soil as the flourishing scenes?

### Dark-but-wrong (counts as false, belongs in anti)

- Generic grimdark sludge with no thematic connection
- Over-the-top edgy fantasy aesthetic
- Muddy brown visuals with no clear design language
- Random horror imagery grafted onto a non-horror world
- Ugly-in-a-cheap-way rather than ugly-in-a-meaningful-way
- Shock value without emotional truth
- Dark just to be dark, with no story or world logic

The test: is this darkness generic, or does it feel native? Would it look at home on the cover of a random fantasy metal album, or would it look like your world in a dark chapter?

---

## The feedback decision flow

When you're looking at a single image and not sure how to rate it, walk through these questions in order. Stop at the first definitive answer.

### Step 1: Is it truthful to the world?

- **No:** Mark as **bad**. Note failure_mode as **concept** if it's the prompt's fault, **execution** if it's the model's fault. Consider whether it belongs in **anti** if it's a strong example of what's wrong. Stop here.
- **Yes:** Continue to Step 2.

### Step 2: Is the execution clean?

- **No, unrecoverably bad:** Mark as **bad** with failure_mode **execution**. Note what went wrong (faces, composition, artifacts). The prompt was right, the model stumbled. Stop here.
- **No, partially:** Mark as **okay** with failure_mode **partial**. Note specifically what worked and what didn't. This is salvageable with prompt iteration.
- **Yes:** Continue to Step 3.

### Step 3: Does it fit the current scene?

- **No, but it's beautiful and resonant:** Mark as **aspirational**. Set fits_current_scene to false. Note the tone and materiality so it's searchable for future scenes. Stop here.
- **No, and it's just fine:** Mark as **okay**. Log it, move on.
- **Yes:** Continue to Step 4.

### Step 4: How strongly does it hit?

- **It's good but not memorable:** Mark as **great**. Note fits_current_scene true. Good positive signal.
- **It hits hard. This is the scene:** Mark as **approved**. fits_current_scene true. Consider promotion to gold anchor.
- **This is canon. Locked.** Reserve this for deliberate canon decisions, not hot takes.

---

## The seven questions to ask every image

Once you're comfortable with the rubric, these are the seven questions that should run through your mind for each image. Most take a half-second to answer. Dictate the answers only for the ones that matter.

1. **Does this belong to my world?** (truthfulness)
2. **What state is this image showing?** (state awareness)
3. **What tone is it carrying?** (tone awareness)
4. **Did the model execute cleanly?** (execution quality)
5. **Does this fit the scene I was generating for?** (scene fit)
6. **Would I promote this to an anchor?** (anchor signal)
7. **What specifically worked or failed, and why?** (actionable tags)

The first three take a second each. Four through six are judgments. Seven is where the real learning lives.

---

## How to actually dictate feedback

Speech-to-text feedback has constraints. You want structured enough that the brain can parse it reliably, loose enough that you can maintain creative flow without reading from a script.

### The structure

Per image:

```
Image [ID-or-number]. Score [0-10]. Quality tier [tier]. 
[One sentence on what's working or failing.]
[State: X, tone: Y.] (Skip if neutral or unclear.)
[Fits scene: yes/no. Promote to anchor: gold/anti/aspirational/no.]
[Tags: comma-separated keywords.]
[Failure mode if applicable: execution/concept/partial.]
```

### Concrete example

Good dictation:

> Image gpt-image-2 job 007 prompt 03 img 05. Score 8. Quality tier great. Love the weathered stone and the late golden light, feels sacred and lived-in. State sacred, tone still. Fits scene yes. Tags: weathered-materiality-good, late-light-good, character-feels-posed. Not promoting.

> Image nano-banana-pro job 007 prompt 04 img 02. Score 4. Quality tier okay. Lighting is right but the architecture feels too clean and Marvel-ish. State was supposed to be broken but it's reading flourishing and sterile. Fits scene no. Failure mode partial. Tags: lighting-right, architecture-too-clean, reading-sterile.

> Image nano-banana-pro job 007 prompt 05 img 04. Score 9. Quality tier approved. This is exactly what I want for the sanctuary opening. Captures mythic scale and the sense of a place that has waited a thousand years. State sacred, tone awe-filled. Fits scene yes. Promote to gold. Tags: mythic-scale-locked, waiting-feeling, stone-breathing.

### The anti-pattern

Bad dictation:

> Image 42. Meh. It's fine I guess. Maybe a 6. Kind of generic.

This gives the system almost nothing. No tier, no failure mode, no tags, no reason. Over twenty iterations of feedback like this, the taste memory will barely learn anything.

### The rules of good dictation

1. **Always include a numeric score.** 0-10. This is the single most important data point.
2. **Always include a quality tier.** Forces the decision.
3. **Always give at least one specific observation.** "Too posed." "Light is right." "Reading as sterile." One concrete thing that can become a tag.
4. **Note the failure mode when it's not great or approved.** Tells the prompt iteration what to do next.
5. **Flag canon candidates explicitly.** "Promote to gold." "Canon-candidate." The system shouldn't have to guess.
6. **Don't over-explain the obvious.** If a bad image is obviously bad, you don't need a paragraph. "Score 2, tier bad, concept failure, too generic Marvel." Done.
7. **Use your own vocabulary consistently.** Over time, tag vocabulary hardens into real signal. Don't invent new phrasings for the same concept each time.
8. **Flag model-specific observations when you see them.** If a failure feels like a model-specific pattern (not just one bad generation), say so. "This is a classic GPT Image 2 flattening problem." "Nano Banana Pro over-rendered the stone again." These observations feed directly into the per-model prompting playbooks.

### Model-attribution observations

Separate from image-level feedback, some failures (and successes) are specific to the model that generated them. When you see one, call it out. The brain uses these observations to update the experiment logs in `wiki/prompting/`, which over time sharpen into distilled prompting rules for each model.

Examples of model-attribution observations:

- "GPT Image 2 is flattening composition on every sacred prompt this batch. That's a pattern, not one image."
- "Nano Banana Pro nailed the materiality on prompts that mentioned specific stone textures. When prompts were vaguer, it drifted generic."
- "Both models failed the same way on prompt 04, which tells me the prompt itself is wrong, not the model."
- "GPT Image 2 consistently handles intimate scale better than Nano Banana Pro in this batch."

Model-attribution observations are hypotheses unless they show up across multiple batches. A single-batch observation goes into the experiment log as a hypothesis with evidence count 1. It gets strengthened or rejected as more data comes in. Never promote a single-batch observation to a distilled playbook rule.

---

## Tag vocabulary

Tags are the fast-retrieval layer. They let the system find similar feedback patterns across thousands of images. For tags to work, they need to be consistent.

### Recommended tag categories

**Materiality:** weathered-stone-good, materiality-tactile, surfaces-too-clean, plastic-quality, stone-breathing, weathered-materiality-good

**Lighting:** late-light-good, lighting-too-flat, lighting-dramatic, god-rays-working, golden-hour-right, lighting-generic, moonlight-convincing

**Composition:** composition-strong, composition-cluttered, depth-layers-working, foreground-empty, framing-deliberate, framing-random

**Scale and atmosphere:** mythic-scale-locked, scale-unconvincing, atmosphere-on-point, atmosphere-muddy, vast-but-intimate, intimate-but-cold

**World-feel:** feels-native, feels-grafted, sacred-convincing, sacred-performative, corruption-reads, corruption-generic

**Character and figure issues:** character-posing-issue, character-generic, character-fits-world, character-too-modern, face-broken, anatomy-off

**AI tells:** reading-sterile, reading-fortnite, reading-midjourney, reading-generic-fantasy, AI-hands, AI-text, symmetrical-too-perfect

**Emotional truth:** emotional-weight-present, emotional-weight-missing, resonance-strong, resonance-absent, sincere, performative

**Architecture and design:** architecture-specific, architecture-generic, design-language-coherent, design-language-random, marvel-ish, studio-fantasy-ish

You don't need to use all of these. You need to use the same ones consistently across sessions. Write new tags when something genuinely doesn't fit the existing vocabulary, not when you feel like varying the phrasing.

---

## Anchor promotion

An anchor is an image whose embedding becomes part of the reference set that scores all future images. Promotion is a big deal. A bad anchor promoted early poisons the scoring for dozens of iterations.

### Rules for promotion

1. **Only promote images that you would still stand behind in a month.** If you're not sure, don't promote. You can always promote later.
2. **Promote sparingly.** One or two per session at most, in early iterations. The anchor set should grow slowly and deliberately.
3. **Think about what the image teaches.** An anchor isn't just "this is a nice picture." It's an explicit lesson the system will use to judge future work. What specifically does this image teach about your world?
4. **Promote across states, not just flourishing.** If you only promote beautiful hopeful images, you reinforce the beauty-equals-correct bias. Deliberately promote truthful dark, truthful broken, truthful harsh images too.
5. **Don't promote by committee.** If an image is borderline, it's not an anchor. Anchors are things you're clear about.

### When to promote to gold

- The image is a concrete example of what the world looks like in a specific state
- The image's execution is clean
- The image teaches something you want the system to absolutely learn
- You would happily include this image in a pitch deck or mood reel for this project

### When to promote to anti

- The image is a strong, clear, unambiguous example of what's wrong for this world
- Not just "bad execution." Bad concept, wrong aesthetic family, generic, sterile.
- Seeing more images like this would be a problem
- Useful because it gives the system a concrete "not this" reference

### When to promote to aspirational

- The image is beautiful and resonant
- But it doesn't fit the current scene you were generating for
- You don't want to lose it
- You think it might inform a scene or place you haven't invented yet

Aspirational is the tier that protects beautiful-but-wrong-scene images from being rejected or forgotten. Use it freely. It costs nothing and it may unlock future work.

---

## Batch-level awareness

Individual image feedback is only half the practice. The other half is batch-level awareness: across these 60 images, what patterns do you see?

### Questions to ask after finishing a batch

- **Did the batch skew in one direction?** If 50 out of 60 feel off, the prompts themselves need revision, not just the individual images.
- **Is one model outperforming the other, and is the gap consistent or prompt-type dependent?** Nano Banana Pro and GPT Image 2 won't score identically. More importantly, the gap may differ by prompt type. Maybe GPT Image 2 scores higher on sacred prompts but Nano Banana Pro wins on harsh wilderness. That pattern is a direct input to the per-model prompting playbooks. Note it explicitly: which model won, on which prompt types, and what does that tell you about the respective playbook entries? Are there distilled rules that now look solid, or rules that need revision?
- **Are specific prompt types consistently missing?** Maybe every "sacred sanctuary" prompt produces good results but every "corrupted village" prompt produces generic grimdark. That's a prompt-engineering signal.
- **Is the system's pre-ranking aligning with your intuition?** If the images the brain flagged as high-score mostly feel right to you, the taste memory is working. If they feel off, the anchor set needs reconsideration.
- **Is there a pattern in your anchor promotions?** Over several batches, what are you promoting? That's your emerging visual language.

Dictate a short batch summary at the end of each review session:

> Batch summary for job 007. 12 approved, 18 great, 8 aspirational, 22 okay, 0 bad. GPT Image 2 scored higher on sacred prompts, Nano Banana Pro scored higher on harsh wilderness. One concept failure on prompt 04, the whole set felt generic. Prompt 04 needs rework. Two anchor promotions: gold for job 007 prompt 05 img 04, gold for job 007 prompt 02 img 07.

This becomes part of the reviews log and feeds directly into the next iteration's prompt drafting.

---

## Protecting your taste over time

Over 20 batches, drift is the real enemy. Here's how to protect against it.

### Stay anchored to the Creative DNA

Before a review session, re-read the Creative DNA document. Not the whole thing. Just the sections relevant to what you're reviewing. If the batch is about sacred locations, re-read the emotional signature and the world themes. Prime yourself.

### Re-curate anchors every 5 iterations

Every 5 batches, look at the current anchor set. Ask:

- Are these still the right references?
- Are there images in here that I wouldn't promote again today?
- Are there gaps? States that are underrepresented?
- Has my sense of the world shifted? If so, should anchors shift with it?

You can demote anchors too. An early-iteration promotion that no longer feels right can be removed. The anchor set is a living document.

### Watch for flattening

If your scores are drifting toward the middle (lots of 5s and 6s, fewer extremes), that often means you're being cautious rather than honest. Push yourself to mark more 2s and more 9s. Decisive feedback is better data than hedged feedback.

### Watch for beauty drift

If you notice your recent promotions are all flourishing/hopeful images, that's beauty drift. Deliberately promote a truthful dark or truthful broken image next chance you get, even if it feels less emotionally satisfying in the moment. Your world needs the full range represented in its anchor set.

### Watch for feedback inflation

Over time, 7s start feeling like 5s because the bar rises with the system's competence. Recalibrate occasionally. Look back at early gold anchors and ask: would I still give these the same scores today? If not, reset your internal scale.

---

## When in doubt

You will hit cases where the rubric feels insufficient. The image is weird, the reading is ambiguous, the state is unclear. Here's the hierarchy of fallbacks:

1. **Come back to truthful vs false.** Does it belong in the world? That alone often resolves the call.
2. **Come back to the three layers.** Truthfulness, fit, execution. Walk through them.
3. **When all else fails, be decisive.** Any score with specific observations is more useful than no score. Err toward honest over polished.
4. **Don't promote if you're not sure.** Anchors have high signal. Only promote when you're clear.
5. **Use aspirational generously.** If an image is good but you can't place it, that's what aspirational is for. It removes the pressure to force a decision.

---

## The one-page cheat sheet

When you're in a review session and want a reminder fast, this is all you need:

**The axis:** truthful vs false, not beautiful vs ugly.

**Layers:** truthful → fits → well-executed.

**Tiers:** bad → okay → great → aspirational → approved → canon.

**Failures:** execution / concept / partial.

**States:** flourishing / sacred / broken / corrupted / abandoned / harsh / neutral / dna-core.

**Tones:** hopeful / awe-filled / mournful / eerie / tense / oppressive / still / neutral.

**Dictation template:** ID, score, tier, observation, state+tone, fits, promote?, tags, failure mode.

**Anchor rule:** only promote what you'd still stand behind in a month.

**Drift check:** watch for flattening, beauty drift, and inflation.

---

## Final principle

Feedback is an act of teaching. The agent learns what you teach it. Teach deliberately. Teach with the whole range of your world represented. Teach with specific vocabulary. Teach with consistency across sessions.

The quality of your series is bounded by the quality of your taste memory. The quality of your taste memory is bounded by the quality of your feedback. Make the feedback count.
