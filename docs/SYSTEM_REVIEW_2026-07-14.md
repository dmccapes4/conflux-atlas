# SYSTEM REVIEW — Conflux Atlas after Phase 2b

**Date:** 14 July 2026 · **Scope:** Phases 0 → 2b (schema spine → connascence layer + LLM proposer) · **Test state:** 163 passed · **Companion docs:** `STRATEGY_V0.2.md`, `STRATEGY_CONNASCENCE.md`, `REPORT_PHASE2_TRUST.md`, `REPORT_PHASE2_5_SOURCES_PORTALGC.md`, `REPORT_PHASE2B_CONNASCENCE.md`

---

## 1. What the system is now

Conflux Atlas is a confidence-aware model of religious-demographic movement (MENA + diaspora) in which **every quantitative belief is either settled evidence or a scored claim** — no number gets to be load-bearing without a paper trail. In roughly a day of build time it has grown from a Pydantic schema over hand-seeded anchors into a five-layer instrument:

| Layer | Phase | What it does |
| --- | --- | --- |
| Data spine | 0 | Validated anchors / edges / events; ingest for 7 independent sources; golden-value smoke tests |
| Movement space | 1 | Place-hash discretization + 32-dim place vectors over share transitions; cosine retrieval; LOPO scorecard vs baselines |
| Trust ledger | 2 | Beta-Bernoulli posteriors updated **only** by settled claims; temporal-cut policy tape; calibration + Brier |
| Evidence desk | 2.5 | Multi-source observation timeline (hand seeds excluded), level-scaled tolerance, PortalGC governance experiment |
| Connascence layer | 2b | Method-family independence discounts, definitional quarantine, accounting edges, FDR-gated co-variance, shock tagging, verifier-gated LLM proposer with its own trust posterior |

The through-line, ported from nakatomi/ptv-embed-lab and now fully native here: **nothing but a settled outcome may move belief**, and every helper — including the LLM — is a scorekeeping subject of the system it serves.

## 2. Subsystem review — confidence and risks

### 2.1 Data spine (Phase 0) — confidence: high

Schema validators (shares sum to ~1, volume bands, year ordering) plus golden snapshots (Egypt 1950 pinned to exact values) mean silent data drift fails loudly. **Risk:** anchor grid is 1900/1950/2000/2010/2020 — the half-century gaps are now the binding constraint on three downstream consumers (see §2.6).

### 2.2 Movement space (Phase 1) — confidence: high on mechanics, moderate on utility

The place hash (`level|delta|gap|vol`) is deterministic, total, and deliberately predictive (origin stamped from *prior* move so hash_mode can't encode its own answer). The LOPO scorecard was honest: majority-class prediction beats hash_mode at current density (hit rates 0.663 vs sparse bucket coverage). **Risk:** flat-class dominance; the hash earns its keep in Phase 2b as null-model stratification rather than as a predictor — a legitimate but different job than originally hoped.

### 2.3 Trust ledger (Phase 2/2.5) — confidence: high; this is the crown jewel

377 corroboration claims and 783 policy claims settle through one code path with temporal hygiene (parameters freeze at cut; features walk forward). Level-scaled tolerance killed the trace-share free-success exploit; hand-seed exclusion killed the circularity. After Phase 2b's independence discounts and definitional routing, the posteriors are the most defensible numbers the project has produced:

- ARDA 0.477 (survives reweighting — genuinely weak against cross-family settlers)
- Arab Barometer 0.729 (untouched — all cross-family)
- WJP 0.667 → 0.500 (its wins were definition-overlap self-agreement)
- CBS 0.667 → 0.750 (was being drained by a proxy-definition mismatch, now quarantined at `definition_gap:cbs_arab_proxy_vs_pew_muslim` = 0.167 — a finding, not a bug)

**Risk:** trial counts are small (4–90 per source); posteriors are directionally meaningful but not yet tight. **Risk:** the method registry and definition-overlap table are hand-curated — correct at 7 sources, a review burden at 30.

### 2.4 PortalGC (Phase 2.5) — confidence: high in the *negative* result

The ρ×τ sweep + trust cross-tab established that Lorenz KEEP/EVICT tracks graph position, not evidential quality, and that the KEEP-only subgraph distorts the ledger. Verdict stands: report-only, REVIEW-queue generator, never data selection. **Win disguised as a loss:** this result is what justified the connascence admission rule ("edges must change a named consumer's decision") that shaped all of Phase 2b.

### 2.5 Connascence layer (Phase 2b) — confidence: high on structure, honest null on co-variance

Four of five axes survived redefinition around *shared fate*; co-occurrence was retired as redundant with the settlement system. The load-bearing outcomes:

- **STRUCTURAL inverted** — same-method corroboration now carries 0.5 Beta mass instead of binding KEEP blocks. The discount fired exactly where predicted (Pew↔WJP) and nowhere else.
- **CONCEPTUAL as accounting** — 451 complement edges, 10 conservation edges, definitional routing (14 claims quarantined).
- **CO_VARIANCE returned a null at strict admission** — 3,852 scored pairs, 4 raw-α edges vs **20 on shuffled data**, 0 Benjamini–Hochberg survivors either way. The two-tier design (FDR-strict feeds partial settlement; raw-α hypothesis tier feeds clusters/REVIEW/LLM only) means partial settlement stayed dormant *by arithmetic*, not by policy.
- **Conservation claims all abstained** — bracketing 1948–51 edges needs mid-century anchors that don't exist yet. The machinery settles correctly on synthetic books (violation case included).

**Risk:** the co-variance null could be misread as "the method fails"; it is actually "the data is too sparse for the method's honesty bar" — a distinction the report documents but a future reader could miss.

### 2.6 LLM proposer (Phase 2b) — confidence: moderate-high, with the right containment

First live run of the heuristic-management contract: qwen3:8b, one loaded model serving two agents (persona travels per-request; deterministic decode options; no Modelfile). Event attribution abstained 3/3 — correctly, since no documented event explains post-1950 muslim-growth clusters. Conceptual coupling went 50/56 → **`llm_proposer:qwen3:8b` posterior 0.879 over 56 trials**. Every one of its 6 mistakes (decoys and two genuine conservation pairs mislabeled "complement", one unproven definition guess) was caught by the deterministic verifiers and priced into its posterior. **Risk:** verifier leniency is the ceiling on this design — a verifier that accepts a wrong-but-well-formed proposal would launder model error into edges. Verifiers are currently strict-structural (registry, edge existence, offset arithmetic); keeping them that way is a standing constraint. **Risk:** 56 trials is a pilot, not a track record.

### 2.7 Cross-cutting risk register (ranked)

1. **Data density** — mid-century (1930–1990) observations gate the co-variance positive control, conservation settlement, and shock-split calibration simultaneously. Highest-leverage single ingest.
2. **Hand-curated registries** (method families, definition overlaps) — correctness by review, not by construction; scale linearly with source count.
3. **Small-n posteriors** — directional, not tight; publishing requires either more trials or explicit credible intervals in every table.
4. **Verifier leniency drift** — the only channel through which the LLM can hurt the ledger.
5. **repr_version discipline** — stamps exist; the "settled claims keep their version" rule is convention, not yet enforced by code.

## 3. Mathematical inventory

| Technique | Where | Why it's there |
| --- | --- | --- |
| Beta-Bernoulli conjugate posteriors, uniform prior | `learning.py` | settlement-only trust; mean/variance in closed form |
| **Graded (fractional) Bernoulli updates** (weight ∈ (0,1]) | `learning.py` (Phase 2b) | independence discounts + partial settlement without inventing a new likelihood |
| Place-hash discretization (4 total bin functions) | `movement.py` | regime signature; later the stratification variable for the co-variance null |
| 32-dim L2-normalized place vectors (continuous + one-hot) | `movement.py` | cosine retrieval; §6.3 candidate shortlisting |
| Cosine top-k via argpartition | `movement.py` | O(n) retrieval over the catalog |
| Leave-one-polity-out evaluation | `scorecard.py` | policy comparison without polity leakage |
| Temporal-cut protocol (freeze parameters, walk features) | `settlement.py` | backtest hygiene; dress rehearsal for the 1975 North-Star cut |
| Calibration binning + Brier score | `settlement.py` | stated-p vs observed honesty check |
| Level-scaled tolerance (bin-indexed ±pp) | `observations.py` | kills trace-share free successes |
| **Exact one-sided binomial tail test** | `connascence.py` | co-movement significance per pair |
| **Bucket-stratified null model** (pairwise agreement prob from per-regime up-rates) | `connascence.py` | "both declining" cannot mint an edge |
| **Benjamini–Hochberg FDR control** | `connascence.py` (just added) | 3,852 simultaneous tests; raw α admits noise faster than signal — shuffle control proved it |
| Within-series permutation (shuffle) control | `run_phase2b_connascence.py` | empirical null floor for the whole discovery pipeline |
| Union-find connected components | `connascence.py` | co-variance clusters → shared-driver hypotheses |
| Conservation band accounting (loss ∈ [0.5·vol_low, 4·vol_high], gain > 0) | `connascence.py` | migration bookkeeping with deliberate slack for parallel flows/growth |
| Lorenz-attractor classification (ρ×τ sweep) | `portal_graph.py` via provenance-engine | governance experiment; negative result retained |
| Synthetic evidential vitality (corroboration-indexed `updated_at`) | `portal_graph.py` | prevents calendar-age auto-eviction of history |
| Deterministic decoding (temp 0, top_k 1, fixed seed) + JSON-schema constraint | `llm_enrich.py` | near-deterministic structured inference — the heuristic-management criterion |

## 4. Wins worth naming

1. **The ledger corrected itself in both directions in one run** — WJP down, CBS up, with the causes isolated and quarantined rather than averaged away. That's the core thesis (source-weighted, evidence-settled demographic scorekeeping) working end-to-end on real ingested data.
2. **The shuffle control caught the trap before it shipped.** Raw-α co-variance looked plausible (4 edges, nice story about Maghreb muslim growth). The permutation null said 20 edges of pure noise. The FDR tier exists because the system checked itself.
3. **An 8B local model was made a productive, accountable worker.** Not by trusting it — by pricing it. Its posterior (0.879) is now sitting in the same table as Pew's.
4. **Every negative result was kept and load-bearing:** hash_mode losing to majority (Phase 1) → hash reassigned to stratification; PortalGC not tracking trust (2.5) → admission rule for 2b; co-variance FDR null (2b) → quantified ingest priority.
5. **Abstention is genuinely first-class** at every layer: policies abstain, conservation claims abstain, the LLM abstains free of charge — and the calibration tables stay honest because of it.

## 5. What this needs next

Mid-century ingest (1930–1990 anchors/observations) unblocks three consumers at once; credible intervals on all published posteriors; verifier-strictness tests as a permanent gate; enforcement (not convention) for repr_version on settled claims; and eventually the North-Star 1975 full-protocol run with the shock split active.

---

## 6. Meta commentary

Three observations from the inside of this build.

**The strategy documents did real work.** The usual failure mode of design docs is that code quietly diverges from them within a day. Here the causality ran the other way twice: the PortalGC negative result forced the admission rule, and the admission rule then deleted a planned feature (co-occurrence edges) and inverted another (structural) *before implementation*. The user's instinct — "if structural just binds high-frequency sources to KEEP that is not useful" — was the single highest-value correction in the phase; the entire discount mechanism descends from it. Writing the strategy before the code meant the skepticism got encoded as arithmetic instead of as a comment.

**The system's honesty machinery is now stronger than its data.** Almost every gauge built in Phases 1–2b currently reads "not enough evidence" — FDR says no co-variance edges, conservation abstains, shock windows are empty. It would have been easy (and demo-friendly) to ship the raw-α edges and the plausible Maghreb story. The permutation control is the reason that didn't happen, and I'd flag this as the project's most publishable trait: the instrument refuses to exceed its data, and it can *prove* it refuses, which is rarer than it should be in computational history.

**The proposer experiment worked for a reason worth stating precisely.** The LLM added value not because it was smart but because the surrounding structure made its errors cheap and its accuracy measurable: closed vocabularies bounded what it could claim, verifiers bounded what it could cost, and the ledger recorded what it was worth. Its 6 failures were more informative than its 50 successes — they revealed a systematic confusion (complement vs conservation) that a prompt tweak can likely fix, and the fix's effect will be *measurable in the posterior*. That loop — propose, verify, price, adjust, re-price — is the "heuristic management infrastructure" idea made concrete, and it generalizes: any helper (a new source, a new policy, a bigger model) enters this system the same way, through the same door, earning the same kind of number. A system that onboards its own tools that way doesn't need to trust anything, including me.
