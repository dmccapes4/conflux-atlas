# HYPOTHESIS — Ingestion window size, model size, and the HMI economy

**Date:** 14 July 2026
**Branch:** `hmi-window-harness`
**Status:** Pre-registered before any harness run. Predictions are frozen at commit time; the results report may not edit this file except to append an outcome table.
**Companions:** `REFLECTION_LLM_AS_HMI.md` (the argument under test), `STRATEGY_CONNASCENCE.md` §3 (proposer contract), `scripts/run_hmi_window_harness.py` (the instrument).

---

## 1. Origin

The bet, as originally stated: *shorter/smaller ingestion windows/batches improve accuracy (less context to confuse parameters on next-token generation) and speed (smaller agents with no think are faster per token). Less context → easier for agent to infer deterministically → tokens spent decoding and formatting with minimal overhead → less total tokens. Easier to infer deterministically → less parameters required → may use smaller model → smaller models typically have faster tokens/sec.*

This decomposes into three testable hypotheses plus one stated-but-untested bet. Where the reviewer (agent) disagrees with the bettor (user), both predictions are recorded — the point of the harness is that one of us is wrong on tape.

---

## 2. Hypotheses

### H-W1 — Accuracy is non-increasing in window size

For a fixed model, task, and deterministic decode (temperature 0, top_k 1, fixed seed), per-item accuracy at window size \(w_1 < w_2\) satisfies \(acc(w_1) \ge acc(w_2)\), with the gap largest for the smallest models.

- **User prediction:** true, and material (not just statistical noise).
- **Agent prediction:** true on average; possibly flat between adjacent windows (1 vs 3) where the context is far from saturating the model.
- **Falsified if:** any model shows accuracy at \(w=12\) exceeding \(w=1\) beyond the Wilson 95% interval overlap, on either task.

### H-W2 — Token economy (adversarial)

Total tokens for a fixed item population as a function of window size.

- **User prediction:** smaller windows → **fewer total tokens** (minimal overhead, deterministic decode, no drift).
- **Agent prediction:** smaller windows → **more total tokens**, because per-call fixed overhead \(F\) (persona + job prompt + schema) is re-paid \(\lceil N/w \rceil\) times and dominates: total prompt ≈ \(\lceil N/w \rceil F + N t_{item}\). Completion tokens per item may shrink at small windows, but not enough to offset prompt multiplication.
- **Shared secondary prediction:** **tokens per *verified* item** (economy that folds in accuracy) may still favor small windows even if raw totals do not.
- **Falsified for the user if:** total tokens (prompt + completion) rise monotonically as windows shrink, for every model.
- **Falsified for the agent if:** any model spends fewer total tokens at \(w=1\) than \(w=12\).

### H-W3 — Model-size × window interaction

The accuracy gap between the largest model (GPT-4.1) and the smallest (llama3.2:3b) shrinks as the window shrinks:
\[ gap(w) = acc_{4.1}(w) - acc_{3b}(w), \qquad gap(1) < gap(12). \]

- **User prediction:** true — small windows make small models sufficient ("less parameters required").
- **Agent prediction:** true in direction; magnitude uncertain. GPT-4.1 may be at ceiling at all windows on Task A (closed vocabulary), in which case the interaction shows only on Task B (extraction).
- **Falsified if:** the gap is flat or widens as windows shrink, on both tasks.

### H-P1 — Parameter subsetting (stated, NOT tested by this harness)

A deterministic, closed-vocabulary job exercises a proper subset of a model's parameter groups (heads / MLP channels / experts). A settlement-gated lifecycle (KEEP / REVIEW / EVICT over parameter groups, evictions reversible, gated by causal ablation against this harness) converges to a loadable subset significantly smaller than the full model with no loss on the job's settlement rate.

- **Status:** pre-registered speculation. Nearest named relatives: lottery-ticket hypothesis, structured pruning, task distillation, MoE conditional compute, contextual-sparsity serving. The novel element is the ledger-governed, reversible eviction loop.
- **v0 test design (future work):** llama3.2:3b; ablate attention heads in groups; re-run this harness as the gate; report heads-required vs settlement-rate curve. This file is the pre-registration hook for that experiment; today's harness builds its gate.

---

## 3. Instrument

Two tasks, both with deterministic gold — no human judging in the loop.

### Task A — Conceptual coupling classification (real data, verifier gold)

The Phase 2b coupling job exactly as production runs it: candidate series pairs (complement / conservation / definition / null, real couplings mixed with decoys) proposed by the model and settled by the deterministic verifiers in `conflux/llm_enrich.py`. Gold = verifier verdict. Population: a deterministic sha1-ordered, family-stratified sample of the full Phase 3 candidate set, identical across all cells.

- **Primary metric:** proposer posterior mean \((verified + 1)/(proposals + 2)\) — the same Beta arithmetic the trust ledger uses.
- **Guard metric:** yield = verified / candidates (an all-abstain model must not win).
- **Also reported:** precision (verified/proposals), abstention rate, malformed-window rate, coverage.

### Task B — Typed evidence extraction from report pages (synthetic gold)

The ingestion task shape the beacon PDFs need, with gold we control exactly: UNHCR OD rows (real numbers already on the desk) rendered into synthetic prose "report pages" by deterministic templates, \(k\) facts per page. The model extracts typed rows `{origin, dest, year, refugees}` from a window of pages. Gold = the planted tuples.

- **Primary metric:** exact-tuple F1.
- **Also reported:** precision, recall, hallucinated rows (extracted tuples not planted anywhere), numeric-error rows (right entity pair, wrong number).

### Sweep

| Factor | Levels |
| --- | --- |
| Window size (items or pages per call) | 1, 3, 6, 12 |
| Models (local, this box) | llama3.2:3b, qwen3:8b |
| Models (API) | gpt-4.1 |
| Models (deferred to 4090 box via `--url`) | qwen3:14b |
| Decode | temperature 0, top_k 1, seed 42, think off |

One run per cell (decoding is pinned; serving nondeterminism is accepted and noted). Every rate ships with a Wilson 95% interval. Telemetry per call: wall-clock latency, prompt tokens, completion tokens, malformed retries.

### Decision rule (frozen)

For each (model, task): **best window** = argmax of the primary metric, tie-break by lower total tokens per verified item (Task A) / per gold fact (Task B). For each task: **best (model, window)** overall = same rule across all cells, with the guard metric ≥ half the best cell's guard value. The winning cells become the default configuration for the beacon PDF ingestion forge ("best version per current algorithm over the model choices").

---

## 4. Interpretation commitments

- A miss is a result. If H-W2 falls to the agent's side, small windows must justify themselves on accuracy per dollar, not raw token count — that changes the forge's default batch size, nothing else.
- Task A and Task B disagreeing is informative, not a failure: A tests discrimination under distraction, B tests extraction fidelity. The forge cares more about B; the connascence proposer cares more about A.
- Results from this box (RTX 3060) and the 4090 box are comparable on accuracy and token counts but **not** on latency; latency comparisons stay within-box.
- GPT-4.1 telemetry includes API-side prompt caching effects; token counts are as billed, which is the operationally honest number.

---

## 5. Outcome

*(Appended after the harness run — see `REPORT_HMI_WINDOW_HARNESS.md`.)*
