# Video Script: openclaw-trace

**Duration target:** 2-3 minutes  
**Tone:** Direct, technical, confident. No fluff.

---

## INTRO (0:00 - 0:15)

**[Screen: Title slide]**

> AI agents make mistakes. They frustrate users. They miss opportunities.
> 
> Most agents can't learn from their own work.
> 
> What if they could?

---

## THE PROBLEM (0:15 - 0:30)

**[Screen: Pipeline overview]**

> Every agent session is a training signal. Errors, friction, missed opportunities—it's all evidence.
> 
> But nobody's mining it. Fixes are ad-hoc. Improvements don't compound.
> 
> openclaw-trace changes that.

---

## THE LOOP (0:30 - 1:00)

**[Screen: Architecture diagram, animate the flow]**

> Here's the loop.
> 
> We take session traces—JSONL logs from real agent work—and mine them for signals.
> 
> *[Highlight mine-signals box]*
> 
> The miner extracts seven signal types: errors, user frustration, improvement suggestions, experiment ideas, proactive opportunities, and moments of delight. Each signal includes exact quotes from the trace. Grounded evidence.
> 
> *[Highlight rollup box]*
> 
> Signals get clustered into rollups—ranked by frequency and severity. Fingerprints make updates idempotent.
> 
> *[Highlight research briefs box]*
> 
> Top rollups become research briefs. We use an actor-critic loop: Claude drafts, Codex critiques, Claude revises. Evidence-first—we draft the facts before the claims.
> 
> *[Highlight experiments box]*
> 
> Briefs drive experiments. Experiments produce fixes. Fixes ship. We measure the delta.
> 
> *[Show feedback loop arrow]*
> 
> Then we mine again. The loop compounds.

---

## EVIDENCE-FIRST (1:00 - 1:20)

**[Screen: Code block showing signal JSON]**

> The key insight: evidence-first.
> 
> Every signal links back to exact quotes from real sessions. If we can't ground a claim, we mark it "Unknown."
> 
> No hallucinated improvements. No fake metrics. Just grounded evidence.

---

## WEAVE INTEGRATION (1:20 - 1:40)

**[Screen: Weave traces screenshot or Weave slide]**

> The whole pipeline is traced with W&B Weave.
> 
> Signal extraction, LLM calls, rollup clustering, brief generation—every step is observable.
> 
> When something goes wrong, we can see exactly where and why. When something works, we can measure it.

---

## WHAT WE BUILT (1:40 - 2:00)

**[Screen: CLI demo or results slide]**

> Here's what we have:
> 
> A working CLI—`openclaw-trace mine-signals`, `rollup-signals`. Mined over 100 sessions from my personal AI assistant.
> 
> Clustering with fingerprints for idempotent ticket updates. Actor-critic research briefs. Full Weave integration.
> 
> It's a prototype, but the core loop works.

---

## VISION (2:00 - 2:20)

**[Screen: Vision slide]**

> The vision is bigger.
> 
> Many agents. Shared, sanitized rollups. Evidence-backed improvements that propagate across deployments.
> 
> A distributed R&D engine—where the best fixes spread because they actually work.
> 
> Compounding capability growth, grounded in real evidence.

---

## CLOSE (2:20 - 2:30)

**[Screen: Final slide with project name]**

> openclaw-trace. Recursive self-improvement, grounded in evidence.
> 
> Built on Clawdbot. Traced with Weave.

---

## NOTES FOR RECORDING

- **Pacing:** Brisk but not rushed. Let the architecture diagram breathe.
- **Delivery:** Confident, matter-of-fact. You're explaining how it works, not selling.
- **Visuals:** Keep slides advancing with the script. Use cursor to highlight boxes on architecture.
- **B-roll ideas:** Terminal showing CLI run, Weave dashboard, code scrolling.
