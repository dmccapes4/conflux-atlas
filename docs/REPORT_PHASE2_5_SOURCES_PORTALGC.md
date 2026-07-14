# REPORT — Phase 2.5: Expanded Source Ledger + PortalGC Experiment

**Date:** 14 July 2026  
**Artifacts:** `data-validation-reports/PHASE2_5_TRUST.json`, `PHASE2_5_PORTAL_GRAPH.jsonl`, `PHASE2_5_PORTALGC.json`  
**Reproduce:** `make phase2-5` / `.venv/bin/python scripts/run_phase2_5_expansion.py`  
**Code:** `conflux/observations.py` (multi-source timeline), `conflux/portal_graph.py` (PortalGC bridge)

## 1. What changed vs Phase 2

Phase 2's ledger had one settled edge (hand_seed → Pew) and two known defects: hand seeds are authored in-house (circular, and nobody cares), and the flat ±5pp tolerance minted free successes on trace shares. Phase 2.5 fixes both and widens the desk:

- **Hand seeds excluded** from the source ledger entirely (`EXCLUDED_SOURCES`).
- **Level-scaled tolerance** (`level_tolerance`): ±0.5pp at trace, ±1pp minority, ±3pp significant, ±5pp plural+ — reusing the Phase 1 level bins. Shares < 0.5% are treated as "not reported" and never enter the ledger.
- **Seven real sources on one timeline:** Pew, ARDA 2005, Arab Barometer (waves II–VIII), CBS Israel, WJP country CJP (jewish share = CJP/total), McCarthy Six Vilayets, Ottoman 1914 provinces.
- **Same-year cross-source pairs settle** — zero world movement between measurements is the cleanest corroboration.
- **Policy tape widened** to all 201 anchor polities (was 13).

Desk size: **1,191 observations · 377 corroboration settlements · 783 policy settlements** (vs 36 + 219 in Phase 2).

## 2. The source ledger (the real "who to believe" table)

| Source | Trust mean | Trials | Reading |
| --- | ---: | ---: | --- |
| `arab_barometer` | **0.729** | 46 | survey self-ID agrees with next independent source ~3/4 of the time |
| `pew_global_religious_composition_2010_2020` | **0.700** | 38 | **Pew is finally settled, not just a settler** — mostly by AB/CBS observations that post-date it |
| `cbs_population_madaf` | 0.667 | 7 | thin but positive |
| `jewishdatabank_world_jewish_population` | 0.667 | 1 | single settlement; effectively unsettled |
| `arda_national_profiles_2005` | **0.477** | 285 | **the headline** — see below |
| `mccarthy_armenian_pop_ottoman`, `ottoman_demographics_wiki` | — | 0 | sole sources on their polity timelines; nothing independent settles them |

**The ledger did its job.** ARDA's WCD-derived counts disagree with the next independent source roughly half the time over 285 settlements — and this is a *known* property of that dataset (our own ingest note says "Often differs from Pew; Egypt Christian % typically high vs Pew"). The system recovered a documented methodological divergence from settlement mechanics alone, without being told. That is the first substantive validation of the source-trust loop on data we actually care about.

Two honest caveats:

1. **Attribution is asymmetric.** When Pew disagrees with a later Arab Barometer wave, the failure lands on Pew (the claimer), though AB (survey self-ID, conf 0.40) may be the wrong one. Symmetric or confidence-weighted attribution is the obvious next refinement.
2. Ottoman-era sources can't be settled until a second independent series lands on their polity timelines (Karpat appendix extraction would do it).

Policy posteriors on the widened tape barely moved (majority 0.663 @ 639 trials, persistence 0.662, reversion 0.608, hash_mode still silent) — Pew-only polities contribute one transition each, so the extra polities feed `majority` only. Calibration: Brier 0.238; low-confidence claims remain underconfident (stated 0.40 → observed 0.71), and the top bin is now slightly overconfident (stated 0.87 → observed 0.71, n=38).

## 3. PortalGC experiment (report-only, per STRATEGY v0.2 §8.C)

Evidence graph: **1,198 nodes** (1,191 observations + 7 source hubs); edges SOURCE / CO_OCCURRENCE / CO_VARIANCE (settled corroborations) / TEMPORAL. Two guardrails engineered in and test-pinned: **vitality is evidential, not calendar** (corroborated → fresh, contradicted → stale, unsettled → old — pre-1920 does not auto-evict for being old), and **sole-source timelines + trusted source hubs are load-bearing** (never auto-evicted).

**ρ × τ sweep:** the governance-stable band (evict < 30%, zero load-bearing evictions) starts at ρ=32; zero load-bearing evictions across the entire grid. Chosen config ρ=32, τ=2.0 → **KEEP 376 · REVIEW 599 · EVICT 223**.

### 3a. Does the Lorenz geometry track evidential trust? **No.**

| Source | KEEP % | Trust mean |
| --- | ---: | ---: |
| arab_barometer | 47% | 0.729 |
| wjp | 60% | 0.667 |
| arda_2005 | 37% | 0.477 |
| **pew** | **28%** | **0.700** |
| cbs | 0% | 0.667 |

The most-trusted source (Pew) has a *lower* keep rate than the least-trusted (ARDA). The classification is driven by graph position (degree, edge mix, corroboration recency), not by settlement quality. **Cross-validation verdict: PortalGC's KEEP/EVICT is not a trust proxy on this mapping and must not be used as one.**

### 3b. Is the non-evicted graph safe to analyze? **No.**

Rerunning the corroboration ledger on the KEEP-only subgraph (375/1,191 observations) *changes the conclusions*: ARDA collapses to 0.116 (from 0.477), AB inflates to 0.818 (from 0.729), Pew drifts to 0.647. The filter selectively removes the very disagreements the ledger exists to count — pruning bias, directly measured. **Do not run trust analyses on the non-evicted graph.**

### 3c. What PortalGC *is* good for here

The **REVIEW set (599 observations)** is a reasonable triage queue — it concentrates uncorroborated and single-source evidence (all Ottoman provinces land there via load-bearing escalation, correctly: contested, sole-source, needs human eyes). Used as "what should a human look at next," it's defensible. Used as data selection or trust signal, it isn't. Per the strategy's own clause, *a component that doesn't help is a result*: this experiment answered its question and the answer is scope-limiting.

## 4. Next steps

1. **Symmetric/confidence-weighted attribution** in corroboration settlement (biggest ledger refinement).
2. **Karpat appendix extraction** — gives the Ottoman timeline a second source, unlocking pre-1920 settlements.
3. Keep PortalGC as an optional REVIEW-queue generator; do not wire it further.
4. Credible intervals on all reported posteriors (persistence-vs-majority is still ~1σ).

## 5. Gates

- `make test` green — 128 passed (Phases 0 + 1 + 2 + 2.5 tests, incl. level-tolerance, exclusion, portal-graph guardrails).
- All artifacts regenerable via `make phase2-5`.
