# Technical Review — Conflux Atlas

**Reviewer:** (external pass)  
**Date:** 14 July 2026  
**Version reviewed:** `0.0.1` · demo running · ~6,600 processed rows  
**Companion docs:** `STRATEGY.md`, `SCHEMA.md`, `REVIEW.md` (Grok brief review), `NEXT_STEPS.md`

---

## 1. One-paragraph verdict

Conflux Atlas is a **confidence-aware demographic-movement atlas** for MENA + diaspora, currently a Pygame year-scrubber (1900–2025) over cited anchors and migration edges, backed by an unusually strong ingest desk (Pew, OWID, UNHCR, UN DESA, WPP, World Bank, ARDA, WJP, CBS, Arab Barometer, Ottoman). The **architecture is coherent and honest** — confidence is first-class, linear share interpolation is deliberately rejected, and prediction is framed as a falsifiable North Star where *a threshold miss is still a result*. The gap is equally clear: the **modeling engine is thin** relative to the data (3 of ~20 processed files drive the demo; `movement.py`/`learning.py`/`events.jsonl` are specified but unwritten). This is a **publishable approach** — but the publishable unit today is the *uncertainty-propagation + movement-representation methodology*, not prediction. Prediction is a second paper that may honestly fail.

---

## 2. What is genuinely strong

1. **Uncertainty as a first-class citizen.** Every `Anchor`/`MigrationEdge` carries `confidence`; runtime decays it between anchors; the viz encodes it (opacity/alpha). This is the correct epistemic posture for sparse historical demography and is itself a methodological contribution.
2. **Anchors + events + runtime-view separation.** Sparse cited snapshots as the archive, yearly state as a *view* (not the source of truth) is the right data-model decision — and matches the prior REVIEW.md guidance.
3. **Falsifiability baked in.** The 1975-cut forward-prediction protocol with a pre-registered threshold, where a miss is publishable, is rare discipline. It inoculates the project against the "ML on history" critique.
4. **Source discipline.** `BIBLIOGRAPHY.md` + per-record `source_ids` + confidence heuristics by source class give a real path to source-trust learning later.
5. **Explicit anti-patterns.** STRATEGY.md §7 says *do not copy* connascence/patient-graph/MIMIC from ptv-embed-lab and *do not port* price bands/reactor from nakatomi. Naming what not to reuse is a sign the transfer is being done thoughtfully, not cargo-culted.

---

## 3. Principal risks / gaps

| # | Gap | Impact | Fix |
|---|-----|--------|-----|
| 1 | **Engine consumes ~3 of 20 processed files.** UNHCR/DESA/WPP/WJP/CBS/AB ingested but not wired into `ConfluxModel`. | The "strong data desk" does not yet reach the model or any result. | Prioritize overlay wiring over more downloads. Data desk is ahead; stop widening it. |
| 2 | **`events.jsonl` does not exist**, yet edges reference `trigger_event_id`. | The event→migration-delta accounting that would make the sim a *model* (not a scrubber) is absent. | Materialize events for the 3 already-referenced triggers (1923, 1948, 1979) first. |
| 3 | **Edges are cosmetic** — they fade in/out but never mutate node populations. | The "simulation" does not simulate; it animates held anchors. | Even a crude event-delta (edge volume subtracts origin / adds destination with confidence band) turns viz into a testable state model. |
| 4 | **No tests, no CI.** Only `--smoke`. | Ingest regressions are silent; reproducibility rests on manual runs. | Add a tiny `pytest`: schema validation, `view(year)` invariants (shares sum ~1, confidence ∈ [0,1]), one golden smoke snapshot. |
| 5 | **Sparsity vs. velocity.** ~5 share snapshots/polity. | Any "annual volatility" would be fabricated between 1900→1950. | STRATEGY already flags this. Report **inter-anchor Δshare/Δt with gap length**, never annualized vol. |
| 6 | **Bucket collapse distorts groups.** Pew-7 forces Christian Palestinians / Arab→muslim proxies. | Silent misattribution in exactly the contested cases. | Track a `group_note`/uncertainty flag on affected anchors/edges; surface in the paper's limitations. |
| 7 | **`networkx` listed but unused.** | Minor; signals intended-but-absent graph analytics. | Either use it (lineage/succession, path analysis) or drop it from `requirements.txt`. |

---

## 4. Is it publishable? Yes — but scope the claim

**Paper A (defensible now-ish):** *"Confidence-aware representation and comparison of sparse historical demographic movements."* Contribution = the uncertainty-propagation methodology + anchor/event/edge model + movement-vector/place-hash representation + descriptive movement structure (co-occurrence of migration bursts, volatility-by-era). This **does not depend on prediction working**. Venue: computational social science / digital history.

**Paper B (optional, higher risk):** *"Can source-weighted Bayesian settlement forecast MENA demographic movement 1975→present?"* Contribution = the 1975-cut backtest with calibrated confidence and honest baselines (share-reversion, AR, unweighted vectors). **A calibrated failure is a legitimate result** and should be pre-registered as such.

The mistake to avoid is letting Paper A's fate ride on Paper B. STRATEGY.md already internalizes this; keep it that way.

The **most novel and transferable idea** is the through-line you've been building across projects: *a source-weighted, settlement-gated evidence loop applied to a domain where "nobody keeps score."* Demography discussed across many sources with no scorekeeper is a near-perfect fit for that loop. That framing — not the Pygame map — is the paper's hook.

---

## 5. Sparsity → simulation bridge (the interesting technical bet)

Your instinct in the prompt is the right research question: **can dense 1920+ data constrain a simulation that back-fills sparse pre-1920 estimates with calibrated uncertainty?** Concretely:

- Fit movement dynamics (share-transition kernels, migration-response to event deltas, volatility-by-regime) on the **dense modern window** where anchors are frequent.
- Run those dynamics **backward/forward into sparse eras** as a *generative prior*, producing distributions (not point estimates) whose spread widens with anchor distance — exactly your "pre-1920 lower confidence, spaced farther" intuition.
- **Settle** the simulated estimates wherever a real anchor exists (Ottoman census row, WJP Jewish series 1880+). Each hit/miss bumps trust on the dynamics, not on the data.

This is the demographic analogue of the MIMIC↔RISE sparsity story from ptv-embed-lab: sparse, older, wider-spaced observations (MIMIC ICU / pre-1920) vs. dense, structured feeds (RISE full EHR / 1920+ census+UN). The transfer is real and worth stating explicitly in the methods paper — it generalizes the "objective spine + place-hash + settlement" pattern beyond medicine.

Caveat: a backward-run generative simulation over contested history is politically loaded. Keep it framed as *"what the modern-fit dynamics imply, with widening confidence bands"* and always dominated by cited anchors where they exist.

---

## 6. Could PortalGC / `provenance-engine` help? Partly — as governance, not as the predictor

`provenance-engine` (PyPI 0.2.0) is a Lorenz-attractor graph lifecycle manager: map nodes → (x₀,y₀,z₀) from connectivity/association/temporal-vitality, RK4-integrate, classify **KEEP / EVICT / REVIEW**, with load-bearing protection and LLM governance. Notably it already speaks the **same connascence edge vocabulary** (STRUCTURAL 1.2 … TEMPORAL 0.4) — a shared lineage with ptv-embed-lab.

Honest fit assessment for Conflux:

- **Not a demographic predictor.** It decides what a knowledge graph remembers/forgets; it does not forecast shares or migration volumes. Do not wire it into Paper B.
- **Plausible fit as source/anchor governance (Paper A infra, optional).** Conflux has a growing, heterogeneous, contradictory source graph (Pew vs ARDA vs WJP vs surveys vs Ottoman wiki). Mapping *sources/anchors* as nodes — connectivity = how many series they support, vitality = recency/citation, association = agreement with corroborating anchors — and running KEEP/EVICT/REVIEW could triage which low-confidence anchors to **retain, retire, or send to manual review**. `load_bearing` maps naturally to "only cited anchor for a polity-era → never auto-evict."
- **Temporal-vitality decay ≠ demographic decay.** Its z₀ inverse-log recency decay is about *memory freshness*, which is a reasonable proxy for "is this source still the best we have," but it must not leak into demographic confidence math.

**Recommendation:** interesting as an *experiment* for source-graph curation once the source graph is large enough to need pruning — explicitly *after* Phases 0–2. It is a governance layer, not a modeling layer. Filing it under "cross-project pattern to try later" is correct; do not let it pull focus from wiring overlays + events now.

---

## 7. Concrete next-7-days (agrees with STRATEGY §6, reordered by leverage)

1. **`events.jsonl`** for the 3 already-referenced triggers; give each an effect (migration burst + confidence reset).
2. **Wire edge → node-delta** accounting behind a flag; even crude turns scrubber into model.
3. **Wire 2–3 unused overlays** (WPP totals, WJP Jewish series) into `ConfluxModel` so ingested data reaches a result.
4. **"Shape of the data" report** under `docs/`: per-polity anchor counts, gap lengths, confidence distribution, missingness. This is Paper A's Figure 1 and it exists the moment you write the script.
5. **Minimal `pytest`** (schema + view invariants + golden smoke).
6. **Port Beta `TrustStore`** thin, keyed on `source_trust:*`; do not port connascence/patient graph.

---

## 8. Bottom line

The approach is publishable and the epistemics are unusually honest. The project is **over-invested in ingest and under-invested in the engine** — which is fine at day-one, but the next marginal hour should go to *events + overlay wiring + a shape-of-data report*, not another downloader. Keep prediction as a falsifiable North Star, ship the uncertainty-methodology paper independent of it, and treat PortalGC as a later source-governance experiment rather than part of the modeling core.

---

## 9. Meta commentary (author / Cursor Grok — same day)

**On the review itself.** Agree with the leverage reorder. Gap #1 (engine consumes ~3/20 files) and #3 (edges cosmetic) are the real critical path; PortalGC correctly stays off the modeling core. Paper A vs Paper B split is the right inoculant against tying the whole project to a forecast hit.

**Stale bits (already moved since this pass).** Gap #2 is partly closed: `events.jsonl` now exists with the three referenced triggers (Lausanne 1923, 1948 war, Iran 1979) and edge→event IDs resolve. What remains is *runtime application* — events still do not drive node deltas. STRATEGY §6 is updated to put edge→node wiring and overlay consume ahead of more ingest; `make verify-all` now emits the living shape-of-data / infrastructure report under `data-validation-reports/`.

**Origin loop (`REFLECTION_CROSS_DOMAIN_LOOP.md`).** The Iranian-militias / policy / atrocity question that started as an objective browser-Grok pass and then got refined into a confidence-weighted demographic system is exactly the “nobody keeps score” problem in costume: contested claims, heterogeneous sources, no settlement ledger. Demography is the tractable spine because censuses and stock series *do* resolve on a clock; the militia/atrocity layer stays event-shaped and multi-source-banded, not a point estimate the model invents. That is why confidence-first + falsifiable North Star felt natural here rather than bolted on.

**Caution from the reflection, applied.** Breadth is already outrunning settlement. The data desk won the morning; the next marginal hour should settle something the engine can hear (edge deltas, one overlay in `view(year)`, a green verify report) rather than another downloader or OCR page range — unless that OCR page is the settlement for a sparse anchor we already claim.
