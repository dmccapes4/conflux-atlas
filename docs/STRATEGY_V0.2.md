# Conflux Atlas — Strategy Document (v0.2)

**Date:** 14 July 2026  
**Supersedes:** `STRATEGY.md` (v0.1, same day — kept intact for provenance)  
**Inputs to this revision:** `REVIEW_TECHNICAL_2026-07-14.md` (external technical pass), `REFLECTION_CROSS_DOMAIN_LOOP.md`, and same-day ingest progress (events seeded; Karpat/Basihos/McCarthy; DESA origin×destination).  
**Status:** Demo running. Data desk ahead of engine — **v0.2's central re-prioritization: wire the engine before widening the desk.**

## Changelog v0.1 → v0.2

1. **Publication strategy formalized as two separable papers** (Paper A methods / Paper B prediction) instead of phases-with-publishability-notes.
2. **Engine-first re-prioritization:** ~3 of ~20 processed files reach `ConfluxModel`; edges are cosmetic (never mutate node totals). Event-delta accounting promoted to the top of the queue — it is what turns the scrubber into a model.
3. **New research track (§4): the sparsity→simulation bridge** — fit movement dynamics on the dense 1920+ window, run them into sparse eras as a generative prior with widening confidence bands, settle wherever real anchors exist.
4. **The scorekeeping ledger elevated to a first-class deliverable:** the calibrated source-trust ledger ("who turned out to be right about demography") may be the more publishable artifact than the estimates themselves.
5. **PortalGC / `provenance-engine` added to reusable code (§8.C)** as an *optional Phase 2+ source-graph governance experiment* — never part of the predictor.
6. **Reproducibility gate hardened:** minimal `pytest` + golden smoke required before Phase 1 claims; `networkx` either used or dropped.
7. **New named risk: breadth outrunning settlement.** Prefer the next settlement over the next hypothesis.
8. Fixed v0.1 §6 duplication; refreshed current-state tables.

---

## 1. Vision & Scope (unchanged in substance)

Conflux Atlas is a **confidence-aware computational framework** for modeling religious and demographic regime shifts and movements across the MENA region + key diaspora nodes from ~1800 to present (with planned backfill).

**North Star — prediction, held loosely.** The home-run outcome is a learning loop that forecasts demographic movements with **calibrated** confidence and can be **falsified**: freeze knowledge at ~**1975**, predict forward, compare to realized anchors/stocks/edges against a **pre-registered threshold. A threshold miss is itself a publishable result.** The rest of the study is not hostage to prediction succeeding.

Core technical approach (each layer valued on its own):

- Polities / demographic groups as **nodes with movement vectors**; **volatility and velocity profiles** (inter-anchor Δshare/Δt, never fabricated annual vol).
- **Place-hash catalogs + cosine retrieval** for analogical analysis (CPU numpy until N demands more; GPU is optional scaling, not a pillar).
- **Bayesian settlement / trust** over sources and claims (Beta posteriors; settlement-only updates).
- **Co-occurrence / co-variance** of movement events (exploratory at current N).
- **Event-delta accounting** so migrations rewrite node state — the step that makes any of the above testable.

The system remains **objective and source-cited**, designed for sparse heterogeneous historical data without overclaiming.

**The hook (new emphasis).** Demographics are discussed across many sources and *nobody keeps score*. The distinctive contribution is a **source-weighted, settlement-gated evidence loop** applied to that gap: every future census round or realized migration settles prior claims and bumps `source_trust:*` posteriors. Over enough cycles the system holds not just estimates but a **calibrated ledger of who to believe about demography** — potentially the more publishable artifact. Lead with this framing, not the map.

---

## 2. Publication Strategy — Two Separable Papers

**Paper A (defensible near-term):** *Confidence-aware representation and comparison of sparse historical demographic movements.*  
Contribution: uncertainty-propagation methodology; anchor/event/edge model (archive = sparse cited snapshots, yearly state = a view); movement vectors / place-hashes over polity-years; descriptive movement structure (burst co-occurrence, volatility by era); the source-trust ledger design. **Does not depend on prediction working.** Venue: computational social science / digital history.

**Paper B (optional, higher risk):** *Can source-weighted Bayesian settlement forecast MENA demographic movement 1975→present?*  
Contribution: the 1975-cut backtest with calibrated intervals and honest baselines (share-reversion, AR-on-shares, unweighted vectors). Pre-register the threshold; **a calibrated failure is a legitimate result**.

Hard rule: **Paper A's fate never rides on Paper B.** Design the 1975-cut protocol early (even before the model is smart), but report it in its own section/paper.

Licensing note (unchanged): Pew/CBS/Cambridge/microdata may block full data release — plan for "code + non-redistributable processing recipes" from the start.

---

## 3. Current State (14 July 2026, evening)

### Running product

- Pygame year scrubber (`./run.sh`) over **1900–2025**; hold-shares + OWID overlay + edge fade.
- Hand seeds: 12 polities × 1900/1950/2000; Pew 2010/2020; 10 migration edges; **`events.jsonl` seeded** (Lausanne 1923, 1948 war, Iran 1979).

### The honest gap

| Fact | Consequence |
| --- | --- |
| Engine consumes ~3 of ~20 processed files (anchors, edges, OWID totals) | The strong data desk does not yet reach any result |
| Edges fade visually but never mutate node populations | The "simulation" animates held anchors; it does not simulate |
| Events seeded but not applied at runtime | Trigger IDs are still decoration |
| No tests beyond `--smoke`; no CI | Ingest regressions are silent; reproducibility is manual |
| `networkx` in requirements, unused | Use it (lineage/succession) or drop it |
| Pew-7 buckets force Christian Palestinians / Arab→muslim proxies | Silent misattribution in exactly the contested cases — needs a `group_note`/flag surfaced in limitations |

### Data desk (summary; see v0.1 §2 for the full table)

Ingested: Pew, OWID, UN WPP, World Bank, UNHCR (COA), UN DESA (destination **and** origin×destination), ARDA 2005, WJP, CBS Israel groups, Arab Barometer, PCBS, Ottoman wiki, **Karpat Table 4.3 summary, Basihos 1520–1927, McCarthy Six Vilayets (contested; conf capped)**. Cataloged: CBS localities, MEVS (panel `.sav` truncated via Wayback — full microdata blocked).

**Verdict: stop widening the desk.** The next marginal hour goes to engine wiring, not another downloader.

---

## 4. New Research Track — The Sparsity→Simulation Bridge

The most interesting technical bet, promoted from implicit to explicit:

**Question:** can dense 1920+ data constrain a simulation that back-fills sparse pre-1920 estimates with *calibrated* uncertainty?

**Method sketch:**

1. Fit movement dynamics on the dense modern window (share-transition kernels, migration response to event deltas, volatility by regime/era).
2. Run those dynamics into sparse eras as a **generative prior** — distributions, not point estimates, whose spread widens with anchor distance.
3. **Settle** simulated estimates wherever a real anchor exists (Ottoman census rows, Karpat/Basihos tables, WJP Jewish series 1880+). Hits/misses bump trust on the *dynamics*, not the data.
4. Report calibration: does the stated band contain the realized anchor at the stated rate?

**Cross-domain provenance (cite in the paper):** this is the demographic analogue of the sparse/dense problem in the sibling medical work — MIMIC's episodic ICU records vs. a dense-registry EHR stream, and patient journaling filling inter-encounter gaps in 2OPMD. Same abstraction: *dense-regime dynamics as a prior over sparse-regime state, gated by settlement against real anchors.* Solving it in either domain is a method the other can cite.

**Caution:** a backward-run generative simulation over contested history is politically loaded. Frame outputs strictly as *"what modern-fit dynamics imply, with widening confidence bands,"* always dominated by cited anchors where they exist; contested tables (McCarthy) stay confidence-capped inputs, never validation targets.

---

## 5. Phased Plan (re-prioritized)

### Phase 0 — Make the scrubber a model (now – 2 weeks)

1. **Event-delta accounting behind a flag:** edge volume subtracts origin / adds destination with a confidence band; events apply documented deltas + confidence resets. *Top of the queue — everything downstream needs a state that moves.* → **Done** (`ConfluxModel(apply_event_deltas=…)`, demo default on, `[D]` toggle).
2. **Wire 2–3 idle overlays** into `ConfluxModel` (UN WPP totals; WJP Jewish series; DESA OD for modern edge realism). → **Done** (WPP preferred over OWID; WJP CJP share overlay; DESA OD annotates edges).
3. **Volatility / inter-anchor velocity report** — Δshare/Δt with gap length flagged; never annualized vol between 1900→1950. → **Done** (`docs/INTER_ANCHOR_VELOCITY.md`, `make phase0-reports`).
4. **"Shape of the data" report** under `docs/` (per-polity anchor counts, gap lengths, confidence distribution, missingness). This is Paper A's Figure 1. → **Done** (`docs/SHAPE_OF_THE_DATA.md` + gaps in `make verify-all`).
5. **Minimal `pytest`:** schema validation, `view(year)` invariants (shares ≈ 1, confidence ∈ [0,1]), one golden smoke snapshot. **URL drift:** keep `data/sources/CANONICAL_URLS.json` in sync with download/scrape scripts (offline contract tests). Do **not** make live scrapes part of the Phase 0 gate — use `pytest -m network` only as an opt-in heads-up. Gate for any Phase 1 claim: `make test`. → **Done** (incl. true golden Egypt@1950 + event-delta movement test).

**Milestone:** a demo where 1948 visibly moves population with a band, plus committed shape-of-data + volatility reports and a green test run. → *Reachable: run `make test && make verify-all && make phase0-reports && make smoke`.*

### Phase 1 — Movement vectors & retrieval (weeks 2–6)

- `conflux/movement.py`: year/decade-scale place-hash (retuned `delta/gap/level/vol` bins from ptv `lab_movement.py`); node/place vector = shares + velocity + volatility + confidence. → **Done**
- Cosine retrieval of similar polity-years (numpy; GPU only if the scorecard demands it). → **Done**
- Exploratory burst co-occurrence (N≈10 edges — descriptive only, say so). → *deferred* (not required by Phase 1 test contracts)
- **Ablation:** confidence-weighted vs unweighted vectors. → **Hook shipped** (`place_vector(weighted=)`); research comparison not asserted in tests
- Milestone scorecard: → **Done** — see `docs/REPORT_PHASE1_SCORECARD.md`. On the demo tape, **majority / persistence beat `hash_mode`** (honest miss; sparsity-limited).

**Milestone:** hash-catalog scorecard vs a share-reversion baseline over the demo window, with methodology note. → *Reached (result: hash does not win yet).*

### Phase 2 — Settlement & trust (weeks 6–10)

- `conflux/learning.py`: Beta `TrustStore` port (near verbatim from ptv `learning.py`), keyed `source_trust:pew`, `source_trust:hand_seed_v0`, `dynamics:*`.
- Claim → settle → bump; settlement tape = next census round, realized edge volumes, newly extracted historical tables landing on simulated priors.
- Holdouts: leave-one-decade-out / leave-one-polity-out with an honest power discussion (~4–5 snapshots per polity).
- *(Renamed from "anomaly detection" — the portable pattern is settlement-gated trust, not change-point ML.)*
- **Optional experiment, strictly after the above:** PortalGC source-graph governance (see §8.C).

**Milestone:** trust ledger evaluated on known shocks; first calibration table.

### Phase 3 — The 1975 cut (weeks 10–16)

- Forecast share deltas / edge volume bands at multi-year horizons (not "regime shifts" — political-science constructs stay out of the target variable).
- Baselines: reversion, AR-on-shares, unweighted vectors. Pre-registered threshold. **Miss = result.**
- Sparsity→simulation bridge (§4) evaluated here too: calibration of back-filled pre-1920 bands against held-out historical tables.

**Milestone:** backtest report (success optional), feeding Paper B.

### Phase 4 — Papers & dissemination (parallel from week 8)

- Paper A first; Paper B when the backtest tape exists.
- Cite sibling reuse transparently (ptv-embed-lab, nakatomi, provenance-engine).
- **Educational mp4 with narration** (pauses at major events) stays *after* the loop is worth filming — but note its methodological value: a rendering legible to non-specialists forces honesty (visible bands, visible migrations, visibly widening pre-1920 uncertainty). If the video looks wrong, the model probably is.

---

## 6. Key Constraints (hard gates, carried from v0.1 + additions)

1. **Uncertainty is never optional.**
2. **No overclaiming on prediction** — forecasts are exploratory until the tape says otherwise.
3. **Reproducibility first** — now including the pytest/golden-smoke gate.
4. **Evaluation discipline** — backtests, baselines, calibration.
5. **Scope discipline** — 1800–present first; antiquity separate.
6. **Component reuse cited.**
7. **Avoid ideological framing** — contested history stays in sourced evidence with confidence bands; bucket-collapse distortions (Pew-7) flagged, not hidden.
8. **Settlement over breadth** *(new)* — prefer closing a loop (wire, test, settle, report) over opening a source or a hypothesis.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| **Breadth outruns settlement** (new, primary) | §6.8; next-actions ordered by "does this close a loop?" |
| Data sparsity early periods | Explicit confidence; modern window first; §4 bridge produces bands, not points |
| "ML on history" skepticism | Lead with uncertainty methodology + falsifiable protocol; miss = result |
| Over-engineering ML early | numpy before GPU; hash catalog before learned embeddings |
| Sibling-pattern mismatch | Lab day-bins ≠ census decades; nakatomi price bands ≠ migrant volumes — retune yardsticks |
| Sensitive events / contested tables | Multi-source bands; McCarthy-class sources confidence-capped and never used as validation targets; generative back-fill framed as model-implied, anchor-dominated |
| Group-bucket collapse | `group_note` flags; explicit limitations section |
| Licensing blocks data release | Code + recipes plan from day one |

---

## 8. Reusable Code Exploration

### A. `2OPMD/2ndOpinionMD/ptv-embed-lab` (unchanged assessment)

| Pattern | Location | Reuse |
| --- | --- | --- |
| Place hash + bins | `ptv_embed/lab_movement.py` | **High** — retune to years/decades, share deltas |
| `stamp_node_context` / place embedding | `ptv_embed/node_context.py` | **Adapt** → `anchor_context` on polity×religion series |
| Beta trust ledger | `ptv_embed/learning.py` | **Copy** nearly as-is |
| Hypothesis predict/settle registry | `ptv_embed/hypotheses.py` | **Adapt** to share/edge outcomes |
| Frozen cohort normalizer | `ptv_embed/embed.py` | **Later** |
| GPU cosine matmul | `ptv_embed/code_filter.py` | **Optional util** |
| Patient graph, connascence, MIMIC, LOINC | various | **Do not copy** |

### B. `nakatomi` (unchanged assessment)

Settlement-only learning + source-class trust posteriors: **high reuse**. ARGYLE graded settlement: **medium-high** for volume bands. Price vol/reactor/portfolio: **do not port**. Transfer thesis stands: nakatomi settles *who to believe*, which maps to Conflux source trust + forecast calibration — not a drop-in share predictor.

### C. PortalGC / [`provenance-engine`](https://pypi.org/project/provenance-engine/) *(new)*

Lorenz-attractor graph lifecycle: nodes → (x₀,y₀,z₀) from connectivity/association/temporal vitality; RK4; **KEEP / EVICT / REVIEW** with load-bearing protection. It already speaks the FullMetalPacket connascence edge vocabulary (STRUCTURAL 1.2 … TEMPORAL 0.4).

| Aspect | Fit for Conflux |
| --- | --- |
| Demographic prediction | **None. Never wire into Paper B.** |
| Source/anchor-graph governance | **Plausible, Phase 2+:** sources/anchors as nodes (connectivity = series supported, vitality = recency/citation, association = corroboration); KEEP/EVICT/REVIEW triages which low-confidence anchors to retain, retire, or send to manual review |
| `load_bearing` | Maps naturally: "only cited anchor for a polity-era → never auto-evict" |
| Temporal-vitality decay | Memory freshness only — **must not leak into demographic confidence math** |

Status: filed as a governance-layer experiment once the source graph is big enough to need pruning. It does not pull focus from Phase 0.

---

## 9. Immediate Next Actions (next 7–10 days, ordered by loop-closure)

1. **Event-delta accounting** behind a flag (1948 moves population with a band).
2. **Wire WPP + WJP + DESA OD overlays** into `ConfluxModel`.
3. **Shape-of-the-data report** + **inter-anchor velocity report** under `docs/`.
4. **Minimal pytest + golden smoke** (`make test`). Offline URL-contract tests via `CANONICAL_URLS.json`; live host probes are `make test-network` only.
5. Port **Beta `TrustStore`** + year-scale place-hash utilities (thin; no patient graph / connascence).
6. Design the **1975-cut protocol** on paper (pre-register threshold + baselines) — cheap now, load-bearing later.
7. Deeper Karpat appendix OCR / UNHCR COO refetch: **only after 1–5** (desk is ahead).

---

## 10. Direction & Feasibility (updated opinion)

| Track | Feasibility | Notes |
| --- | --- | --- |
| Phase 0 engine wiring + reports | **High** | Glue + docs; 1–2 weeks |
| Place-hash + scorecard (Phase 1 lite) | **High** | Proven pattern; careful year-scale binning |
| Source-trust loop (Phase 2 lite) | **Medium–High** | Portable; settlement tape exists (census rounds, realized edges) |
| Sparsity→simulation bridge calibration | **Medium** | Novel; the most citable piece if it calibrates |
| 1975→now prediction *attempt* | **Medium** | Backtests + baselines achievable; success optional |
| "We can predict MENA demography" | **Low unless evidence appears** | Miss is the honest prior |
| GPU store / ancient backfill / org overlays | **Low near-term** | Separate papers |

**Bottom line (v0.2):** the epistemics are the asset — keep them. The desk is ahead of the engine; spend the next hours making state actually move and loops actually settle. Ship Paper A independent of prediction, pre-register the 1975 cut, treat the trust ledger as a headline deliverable, and keep PortalGC as a curiosity on the governance shelf until Phase 2 earns it.
