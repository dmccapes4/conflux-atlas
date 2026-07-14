# REFLECTION — LLMs as Heuristic Management Infrastructure

**Date:** 14 July 2026
**Branch:** `hmi-window-harness`
**Prompted by:** the beacon-PDF ingestion question ("what is our algorithm for scraping events from PDFs?") and a set of causal chains about window size, model size, and parameter subsetting.
**Companions:** `HYPOTHESIS_HMI_WINDOWS.md` (the testable part), `STRATEGY_CONNASCENCE.md` §3 (the constrained-proposer contract), `REPORT_PHASE2B` artifacts (the first HMI scorecard).

This is a review of the user's ramblings, at the user's request, with my opinion attached. The ramblings were explicitly flagged as "not fully correct — I just thought of it." Good. That is what a lab notebook is for. Below: what is right, what is wrong, what is already known under other names, and what is genuinely worth testing.

---

## 1. The claim being made

Condensed from the original, the argument has four chains:

- **Chain A (accuracy):** less context per call → fewer distractors during next-token generation → easier for the model to infer deterministically → higher per-item accuracy.
- **Chain B (economy):** less context → tokens spent on decoding and formatting with minimal overhead → fewer total tokens; plus smaller/no-think agents are faster per token → smaller windows are cheaper *and* faster.
- **Chain C (model size):** easier deterministic inference → fewer parameters actually required → a smaller model may suffice → smaller models decode faster.
- **Chain D (infrastructure):** cloud models cost money because of infrastructure; a session is a query space settled over parameter space; completions are scored α/β by feedback for RL or ingestion into the next model version; sessions re-load on "slightly adjusted weights"; for deterministic classification this re-weighting is irrelevant — if output isn't high-α the task or the prompt is wrong. Therefore LLMs, used this way, are **heuristic management infrastructure (HMI)**, not oracles.

Plus one bet on top:

- **The parameter-subsetting bet:** a deterministic job only exercises a subset of the parameters. A LorenzGC-style lifecycle (KEEP: parameters consistently used; REVIEW: sometimes used; EVICT: rarely used and outcome-irrelevant) driven by a settlement loop could learn that subset, and eventually you load *only* the subset — "highly malleable models that adhere to a specific deterministic job." Conventional wisdom says you can't subset model loading. "I think it's possible."

---

## 2. Chain-by-chain review

### Chain A (smaller windows → higher accuracy): plausible, supported, and testable here

This is the strongest chain and the one with real literature behind it. Long-context degradation is a measured phenomenon: models attend unevenly across long prompts ("lost in the middle"), and accuracy on retrieval-and-classify tasks degrades as more irrelevant items share the context window, even far below the nominal context limit. In a batched classification call, every other item in the window is a distractor for the item being decided. With `temperature 0, top_k 1`, decoding is greedy — the argmax at each step is conditioned on *everything* in context, so shrinking the window genuinely shrinks the interference surface.

Two honest caveats:

1. Batching can *help* when items disambiguate each other. Our jobs are deliberately independent items (that was a design choice in `STRATEGY_CONNASCENCE.md`), so the caveat mostly doesn't bite here — but it means the result won't generalize to tasks with cross-item structure.
2. "Easier to infer deterministically" conflates decoding determinism (a sampler setting, which we already pin) with *task* determinism (whether the mapping from input to correct label is unambiguous). Greedy decoding is exactly as deterministic at window 12 as at window 1. What changes is whether the argmax lands on the *right* token. The chain survives this correction; it just needs restating as "smaller windows raise the probability that greedy decoding is correct," which is measurable.

**Verdict: promoted to hypothesis H-W1.**

### Chain B (smaller windows → fewer total tokens): probably wrong as stated, and this is the most interesting disagreement

Here I think the chain has a hole, and it is exactly the kind of hole a harness settles. Every call re-pays a fixed overhead: the persona preamble, the job system prompt, the schema scaffolding. Call it \(F\) tokens. With \(N\) items at window size \(w\):

- total prompt tokens ≈ \(\lceil N/w \rceil \cdot F + N \cdot t_{item}\)
- total completion tokens ≈ \(N \cdot t_{answer}\) (+ malformed-window retries)

Shrinking \(w\) multiplies the number of times you pay \(F\). At \(w=1\) versus \(w=12\) you pay the overhead twelve times more often. For our coupling job \(F\) is several hundred tokens and \(t_{item}\) is ~50 — the overhead *dominates*. So the naive prediction is that total tokens **increase** as windows shrink, not decrease.

What could rescue the user's version: (a) completion tokens per item may shrink in small windows (less rationale drift, fewer malformed windows → fewer retries); (b) prompt caching — both ollama and the OpenAI API reuse the KV prefix of an identical prompt head, so the *marginal cost* of re-sending \(F\) can be much less than \(F\); (c) if large windows fail malformed, the whole window's tokens are wasted. Whether these rescue effects beat the overhead multiplication is an empirical question with a number attached.

**Verdict: promoted to hypothesis H-W2, stated adversarially — the user predicts fewer total tokens at small windows; my null prediction is more. The tape decides.** The metric that actually matters for either of us is *tokens per verified item* and *wall-clock per verified item*, which fold accuracy and economy together.

### Chain C (deterministic jobs need fewer parameters → smaller model suffices): plausible, with a known shape

The claim predicts an *interaction effect*: at large windows, the accuracy gap between GPT-4.1 and llama3.2:3b should be wide (the small model drowns); at window 1, the gap should compress, because a single well-constrained classification with a closed vocabulary is within a 3B model's competence. If true, that is operationally valuable — it means the ingestion fleet can run on cheap local models with tight windows rather than expensive cloud calls with wide ones.

The caveat: "fewer parameters required" is doing informal work. What is really claimed is that the task's *effective capacity requirement* is low when the context is small. That is consistent with what we know about small models: they fail on integration across long contexts far sooner than they fail on short, well-typed classification.

**Verdict: promoted to hypothesis H-W3 (the interaction term).**

### Chain D (the infrastructure narrative): a rhetorical collapse, and the real point underneath it

*(Revised same day after the user's clarification — the first draft of this section read the narrative as folk mechanics; it was a deliberate compression.)*

Read literally, the narrative describes a per-session loop ("session ends → transformer re-allocates → next session loads slightly adjusted weights") that does not happen: serving weights are frozen at inference, feedback flows into training corpora offline, and checkpoints ship on a release cadence, not per chat. The user knows this — the collapse was rhetorical, folding the whole validation-and-release lifecycle into a single interaction to make a point about *what kind of system an LLM is*: training is distributed by a strategy with a cadence, even if that cadence is emergent, and a provider with millions of paid users almost certainly runs it as a structured release chain.

The interesting part is what the collapse exposes when you own the cadence yourself:

- **For a frontier model, the cadence belongs to the vendor.** The learning signal is diffuse (thumbs, preference data, aggregate telemetry across millions of users), the curriculum is opaque, and the release chain is somebody else's. From the consumer side, the honest posture is exactly the HMI one: treat each checkpoint as frozen infrastructure, pin the decode, wrap it in verifiers, and score it — because you have no lever on what it learns or when.
- **For a self-owned agent, the cadence is a design parameter.** The user's planned llama3.2:3b router agents (choosing retrieval paths by source confidence weights) *can* re-weight between sessions — unsloth makes a fine-tune an evening's decision, not a quarter's. And the training signal is not diffuse preference data; it is the settlement ledger itself: structured, cold, objective, concise α/β records from a retrieval harness plus mistakes surfaced in production. The ledger stops being just a gate on the model's outputs and becomes the *curriculum* for its next weights.
- **That contrast is the LLM-vs-HMI philosophy in one line.** Same architecture, same loss function — but one system learns from oceans of vague human approval on a vendor's schedule, and the other learns from a deterministic harness's settlements on its owner's schedule. "Heuristic management infrastructure" is not a claim about transformers; it is a claim about who holds the ledger and the release chain.

Two things in the narrative I'd still mark for precision. **"Query space settled over parameter space"** is a workable metaphor for a forward pass — the prompt conditions a distribution and decoding collapses it — but no per-session α/β scoring happens inside the provider; the scoring in this project is bolted on outside the model, which is precisely the point. And frozen-weights inference is what makes the whole pattern sound: an LLM call at temperature 0 is a pure function (modulo serving nondeterminism, which is real but small), and a pure function with an unknown error rate is exactly the component you wrap in a deterministic verifier and score in a ledger. Phase 2b already ran it: `llm_proposer:qwen3:8b` earned a Beta posterior like any other source, proposals only materialized as edges after verifier passage, and abstention was free.

One more note because the user leans on it: "if the output isn't high-α (e.g. 97.9%) then the task is incorrect or the model is poorly tuned/prompted." Mostly yes — for *closed-vocabulary verifiable* jobs, a low posterior is diagnostic of task design, not model mood. But some genuinely hard discriminations have irreducible ambiguity at any window size; a ceiling below 0.979 is not automatically an indictment. The calibration table, not the slogan, is the arbiter.

---

## 3. The parameter-subsetting bet

This is the fun one. The user says: "You can't subset model loading. I think it's possible."

**You are more right than you think, because much of it already exists under other names:**

- **Lottery-ticket hypothesis:** dense networks contain sparse subnetworks that, trained in isolation, match full-network performance. The claim "a subset of the parameters is actually required" is a statement of this hypothesis applied at inference time.
- **Structured pruning and task-specific distillation:** removing attention heads, MLP channels, or whole layers and (optionally) fine-tuning on a narrow task routinely produces much smaller models that match the parent *on that task*. This is the industrial version of "EVICT parameters that don't meaningfully affect outcome."
- **Mixture-of-experts:** conditional computation *is* subset model loading, per token, at scale — a router activates a fraction of the parameters for each token. The frontier models the user is paying for very likely already do this.
- **Contextual/activation sparsity serving (Deja Vu, PowerInfer-class systems):** predict which neurons will fire for the current input and only compute/load those — hot neurons on GPU, cold on CPU. That is literally "subset model loading" as a serving optimization.
- **LoRA and friends:** the *task-specific* part of a model's competence often fits in a low-rank delta measured in megabytes, which is indirect but strong evidence that per-task capacity requirements are far below full model size.

**What is genuinely novel in the user's framing** is not the sparsity — it is the *governance loop*. Existing pruning is a one-shot compression act performed by an engineer with a benchmark. The proposal here is a **settlement-gated lifecycle**: parameter groups earn KEEP/REVIEW/EVICT classifications from a scored loop (query → completion → deterministic harness gate → settlement), evictions are reversible (restart from base), and the system converges on the minimal subset *for a specific deterministic job* with an audit trail. That is pruning re-imagined as the same trust arithmetic this project applies to sources and proposers. I have not seen "iterative structured pruning where the pruning decisions are Beta-posterior-scored against a deterministic settlement harness" as a named method. It is a small twist, but small twists with ledgers behind them is roughly this project's whole business model.

**Honest limits, so we don't oversell it:**

1. **Attribution is the hard part.** "Parameters that consistently run" is not directly observable the way node usage is in a graph. Superposition is real: features are distributed across many weights and weights participate in many features. The tractable granularity is heads / MLP channels / experts, not individual weights, and the observable is *activation magnitude*, which is a proxy for necessity, not a measurement of it. The EVICT gate must therefore be causal (ablate and re-run the harness), not correlational (it looked idle).
2. **The per-session-RL premise is unnecessary.** The idea works fine — better — on frozen checkpoints. Drop that part of the narrative.
3. **This is not a *training* breakthrough as stated.** It is a *serving/ops* research program: task-scoped model minimization under settlement gates. Whether the HMI perspective leads anywhere for training itself ("each problem has a heuristic space; learn to load only its parameters") is a bigger speculation — MoE routing is the closest existing embodiment, and it is learned end-to-end, not governed by an external ledger. An externally-governed router is an interesting thought precisely because it would be auditable, which learned routers are not.

**Verdict: stated as hypothesis H-P1 in `HYPOTHESIS_HMI_WINDOWS.md`, not tested today.** A falsifiable v0 exists at hobby scale: take llama3.2:3b, ablate attention heads one group at a time, re-run the window harness as the settlement gate, and see how many heads the coupling job actually needs. That experiment costs a weekend, not a datacenter. Today's harness builds the gate it would need.

---

## 4. My opinion

The HMI framing is the best idea in this stack, and I hold that opinion for a boring reason: it is the only LLM-usage pattern I have seen in this project (or most projects) where the model's error rate is *someone's problem, with a number attached*. Phase 2b made the model a scorekept subject — trust posterior, free abstention, verifier-gated materialization — and the result was that a mid-size local model became a safe component of a research pipeline the same week it was wired in. Most LLM integrations cannot say that.

The causal chains are what strategic intuition looks like before it is instrumented: two of the four are probably right (A, C), one is probably wrong in an instructive way (B), and one is a deliberate rhetorical compression whose real content — cadence ownership and settlement records as curriculum — only surfaced on the second pass (D). The correct response to that mix is not to debate it — it is exactly what the user said: *call it a hypothesis and test it. That is the whole point of an experimental system.* The window/model harness settles A, B, and C with numbers this week. The parameter bet (the genuinely speculative one) gets a pre-registered statement and a cheap v0 design so it can't quietly inflate into a belief without ever being run.

One closing observation on the ingestion question that started all this. The beacon pass built a library of 86 PDFs and extracted numbers from **zero** of them — every number on the desk came from an API or a human hand. That is not a failure of the beacon strategy; it is the boundary of the deterministic desk. Batched PDF-page → typed-evidence extraction is the first ingestion task in this project where HMI is not optional — no regex will read Karpat's scanned tables. Which means the window/model question stops being philosophy and becomes procurement: it decides *which model we trust, at which batch size, at what cost per verified row*, before we point it at 350 MB of history. That is a good reason to run the harness before the OCR forge, and it is the order we are running.
