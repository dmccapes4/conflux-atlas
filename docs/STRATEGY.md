# Conflux Atlas — Strategy Document (v0.1)

> **SUPERSEDED (14 July 2026):** current strategy is [`STRATEGY_V0.2.md`](STRATEGY_V0.2.md), which incorporates the external technical review (`REVIEW_TECHNICAL_2026-07-14.md`) and reflection (`REFLECTION_CROSS_DOMAIN_LOOP.md`). This file is preserved unmodified below for provenance.

**Date:** 14 July 2026  
**Status:** Initial demo running. **North Star = prediction** (1975→now backtests; threshold miss = result). The rest of the study stands alone.  
**Companion:** Sections marked **Critique** flag overreach, missing prerequisites, or mismatches with the current codebase.

---

## 1. Vision & Scope

Conflux Atlas is a **confidence-aware computational framework** for modeling religious and demographic regime shifts and movements across the MENA region + key diaspora nodes from ~1800 to present (with planned backfill).

**North Star — prediction.** The home-run outcome is a learning/predictive loop that can forecast demographic movements with **calibrated** confidence — and that can be **falsified**. The canonical test window is roughly **1975 → present**: freeze knowledge at a cut year, predict forward, compare to realized anchors / stocks / edges. **Failing to beat a confidence threshold is itself a publishable result.** Everything else in the project either (a) improves our understanding of movement so we can judge whether prediction is possible in this system, or (b) teaches us what we learn when a component does *not* help. **The rest of the study is not hostage to prediction succeeding.**

Core technical approach (build toward the North Star; value each layer on its own):

- Represent polities / demographic groups as **nodes with movement vectors**.
- Compute **volatility and velocity profiles**.
- Use **vector embeddings + cosine similarity** (hash catalogs; GPU optional at scale) for retrieval and analogical analysis.
- Apply **Bayesian settlement / trust** methods to quantify unexpected movements and source reliability.
- Track **co-occurrence and co-variance** of major movement events in historical context.
- Build a **learning/predictive loop** that attempts forecasts with calibrated confidence — evaluated on holdouts (e.g. 1975→now).

The system must remain **objective and source-cited**. It is explicitly designed to handle sparse, heterogeneous historical data without overclaiming precision.

**Primary research questions (for publication — separable):**

1. How can we represent and compare historical demographic movements while properly propagating source uncertainty? *(core study — stands alone)*  
2. Under what conditions (if any) can this system forecast movements 1975→present above a stated confidence threshold — and what do calibrated failures teach us? *(North Star — optional success)*

### Critique — Vision

| Claim | Issue |
| --- | --- |
| Prediction as identity of the project | **Revised:** North Star, not prerequisite. Phases 0–2 remain valuable if prediction fails. |
| GPU cosine + vector hashes as core | Premature as a *defining* pillar. With ~12–50 polities × sparse years, CPU numpy cosine is enough until embeddings prove lift. GPU is optional scaling (see §7). |
| “Regime shifts” | Not yet first-class in schema (anchors + migration edges only). Governance overlays (Baath, mandate, republic) are notes, not modeled regimes. |

---

## 2. Current State (14 July 2026)

### Running product

- Pygame year scrubber (`./run.sh`) over **1900–2025**.
- Policy: **hold** religion shares from latest `Anchor` ≤ year; **overlay** OWID annual population; fade migration edges in-window.
- Hand seeds: 12 polities × 1900/1950/2000; Pew 2010/2020; 10 migration edges.

### Data infrastructure (raw → processed)

| Layer | Status |
| --- | --- |
| Pew religious composition | **Ingested** → `anchors.jsonl` |
| Hand historical anchors / edges | **Seeded** |
| OWID population | **Ingested** → `population_totals.jsonl` (model overlay) |
| Ottoman wiki empire + 1914 provinces | **Ingested** (low confidence) |
| Karpat Table 4.3 religious summary | **Ingested** → `karpat_religious_structure_summary.jsonl` (full appendices still OCR-hard) |
| Basihos Turkey-border totals | **Ingested** → `basihos_turkey_borders_population.jsonl` (1520–1927) |
| McCarthy Six Vilayets Table One | **Ingested** → `mccarthy_six_vilayets_religion.jsonl` (contested; conf capped) |
| UNHCR refugee stock by COA | **Ingested** → `unhcr_refugee_stock_by_coa.jsonl` (no origin in dump) |
| UN DESA migrant stock (destination) | **Ingested** → `un_desa_migrant_stock_destination.jsonl` |
| UN DESA migrant stock (dest×origin) | **Ingested** → `un_desa_migrant_stock_od.jsonl` (222 pairs × years) |
| ARDA National Profiles 2005 | **Ingested** → `arda_national_profiles_2005.jsonl` (cross-check; conf capped) |
| World Bank SP.POP.TOTL | **Ingested** → `population_totals_worldbank.jsonl` |
| PCBS projected population | **Ingested** → `pcbs_projected_population.jsonl` (2017–2026) |
| UN WPP 2024 Estimates | **Ingested** → `population_totals_wpp.jsonl` (18 polities × 1950–2023) |
| CBS Israel pop groups | **Ingested** → `cbs_israel_population_groups.jsonl` (2019–2024; Arab→muslim proxy) |
| WJP (DellaPergola / Shapiro) | **Ingested** → `wjp_world_core_jewish_population.jsonl` + `wjp_country_core_jewish_population.jsonl` (2023 appendix + 1970) |
| Arab Barometer Q1012 | **Ingested** → `arab_barometer_religion_shares.jsonl` (waves II–VIII; survey ≠ census) |
| Events (`events.jsonl`) | **Seeded** → 3 triggers (Lausanne 1923, 1948 war, Iran 1979) |
| CBS locality / MEVS microdata | **Cataloged**; MEVS panel `.sav` truncated at 1MB (Wayback) — full microdata extract blocked |

### Schema / docs

- Pydantic: `Anchor`, `MigrationEdge`, religion + migration-kind enums (`conflux/schema.py`).
- Bibliography discipline started (`data/sources/BIBLIOGRAPHY.md`).

### Critique — Current state draft claims

| Claim in source draft | Reality |
| --- | --- |
| “Strong data infrastructure already in place” | **Partially true.** Download coverage is strong; **ingest → model wiring** is still thin (UNHCR/DESA just landed; CBS/WJP unused in engine). |
| “event/edge support” | Edges yes; **Event model + `events.jsonl` seeded** (3 triggers). Engine still does not apply events at runtime. |

---

## 3. Realistic Phased Plan (Publishable Path)

### Phase 0 – Foundation (Now – 2 weeks)

**Goal:** Stabilize the demo and establish the data shape.

- Finish basic **volatility + velocity** on current anchors + a small set of hand-coded events (e.g. 1948–51 Jewish exoduses; optionally 1976 Lebanon violence as *event* records — see critique).
- Exploratory viz: volatility profiles, simple movement vectors.
- Lock core schema (polity, anchor, event, edge); add **minimal** vector/place-hash fields only after series exist.
- Produce “shape of the data” report (descriptive stats, missingness, confidence distribution) under `docs/`.
- **Publishability:** Fully reproducible scripts + docs.

**Milestone:** Reproducible demo + volatility report committed.

#### Critique — Phase 0

| Item | Disclaimer |
| --- | --- |
| “1976 Damour/Karantina massacres” as early canonical events | High political sensitivity; casualty/displacement figures are contested. If included, treat as **sourced Event records with explicit confidence bands**, not model outputs. Prefer starting with already-seeded 1923 / 1948–51 / 1979 edges. |
| Volatility on *sparse* anchors (3–5 years/polity) | Year-to-year velocity is ill-defined between 1900→1950. Report **inter-anchor Δshare / Δt** and flag gap length — do not pretend annual vol like lab time series. |

---

### Phase 1 – Vector Representation & Retrieval (Weeks 2–6)

**Goal:** Move from scalar demographics to movement vectors.

- Design node/place vector (shares, velocity, volatility profile, confidence).
- Cosine similarity search (adapt ptv-embed-lab patterns; CPU first).
- Store hash catalogs / embeddings for retrieval of similar polity-years.
- Basic co-occurrence / co-variance of migration edges in time windows.
- **Publishability:** Ablation of confidence-weighted vs unweighted vectors.

**Milestone:** Similarity search over 1800–2025 (practically: demo window) with methodology note.

#### Critique — Phase 1

| Item | Disclaimer |
| --- | --- |
| “GPU-accelerated” as Phase 1 deliverable | **Over-scoped.** Port the matmul helper; default to numpy until N is large. |
| “1800–2025 window” | Anchors are densest 1900–2020. Claiming 1800 requires Ottoman/Karpat ingest quality we do not yet have. |
| Co-occurrence with N≈10 edges | Descriptive only; not statistically powered. Frame as **exploratory**. |

---

### Phase 2 – Bayesian Components & Anomaly Detection (Weeks 6–10)

**Goal:** Quantify unexpected movement with proper uncertainty.

- Adapt Bayesian **settlement** loop from ptv-embed-lab / nakatomi (Beta trust over claims/sources).
- Detect “unexpected” movements relative to volatility / hash-mode baselines.
- Propagate source confidence; prefer posteriors over point estimates.
- **Publishability:** Calibration checks on held-out periods.

**Milestone:** Bayesian anomaly / trust module evaluated on known shocks.

#### Critique — Phase 2

| Item | Disclaimer |
| --- | --- |
| “Bayesian anomaly detection” | Neither sibling repo is a classical anomaly detector. Portable piece is **claim → settle → Beta bump** (trust / transition prediction), not change-point ML. Rename milestone to match. |
| Held-out historical periods | With ~4 share snapshots/polity, holdouts are fragile. Prefer leave-one-decade-out or leave-one-polity-out with honest power discussion. |

---

### Phase 3 – Predictive Learning Loop & Evaluation (Weeks 10–16)

**Goal:** Attempt the North Star — forward prediction with quantified confidence — without making the rest of the study depend on success.

- Forecast share moves / migration bursts using vector + Bayesian foundation.
- **Canonical backtest:** cut knowledge ~**1975**, predict through present, compare to realized series; report hit/miss vs a pre-registered confidence threshold.
- Baselines (reversion, AR-on-shares, unweighted vectors). **Threshold miss is a result.**
- Calibrated intervals; limitations of sparsity and contingency.

**Milestone:** Predictive *attempt* + backtest report (success optional).

#### Critique — Phase 3

| Item | Disclaimer |
| --- | --- |
| Forecasting “next major regime shift” | Prefer forecasting **share deltas / edge volume bands** at multi-year horizons. Regime labels are political-science constructs. |
| 16-week path | Aggressive if Phase 0–1 data gaps slip; the **1975 cut protocol** can still be designed early. |

---

### Phase 4 – Paper & Dissemination (Parallel from Week 8)

**Goal:** Publishable artifact.

- Methods paper: confidence-aware vector + Bayesian settlement for historical demography.
- Venues: computational social science / digital history.
- Release code + processing pipelines; datasets where licensing allows.
- Transparent reuse of sibling patterns (cite ptv-embed-lab / nakatomi).

#### Critique — Phase 4

Licensing of Pew, CBS, Cambridge PDFs, and some survey microdata may **block** full data release. Plan for “code + processed non-redistributable recipes” early.

---

## 4. Key Constraints for Publishability

1. **Uncertainty is never optional** — quantitative claims carry source-derived confidence.
2. **No overclaiming on prediction** — strongest claims = pattern detection and analogy; forecasts are exploratory.
3. **Reproducibility first** — scripts, processing, model defs version-controlled and documented.
4. **Evaluation discipline** — learning/prediction needs backtests, baselines, calibration.
5. **Scope discipline** — first papers: 1800–present with high-quality anchors; deeper antiquity separate.
6. **Component reuse cited** — adapt sibling repos transparently; do not present ports as wholly novel.
7. **Avoid ideological framing** — neutral analytical tool; contested history stays in sourced evidence.

*(These constraints are sound; keep them as hard gates.)*

---

## 5. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Data sparsity early periods | Explicit confidence; publish modern window first |
| “ML on history” skepticism | Lead with uncertainty methodology + event modeling |
| Over-engineering ML early | Baselines before GPU/embeddings; hash catalog before learned embeds |
| Scope creep (PLO/MB/ancient) | Explicitly later |
| **Sibling-pattern mismatch** (new) | Lab day-scale bins ≠ census decades; nakatomi price bands ≠ migrant volumes — retune settlement yardsticks |
| **Sensitive event selection** (new) | Prefer well-documented demographic edges; massacre events only with multi-source bands |

---

## 6. Immediate Next Actions (Next 7–10 days)

Aligned with Fable’s leverage reorder (`docs/REVIEW_TECHNICAL_2026-07-14.md` §7): engine wiring over more downloads.

1. **Wire edge → node-delta** (flagged) so migration edges mutate populations — scrubber → model.
2. Wire **2–3 overlays** (WPP totals, WJP Jewish series; then DESA OD / Karpat–Basihos) into `ConfluxModel`.
3. Stabilize demo: **volatility / inter-anchor velocity** report (not annual fake vol).
4. **Shape / validity:** `make verify-all` → `data-validation-reports/VERIFY_*.md` (presence, schema, edge→event, bib coverage, shape stats). Keep regenerating as ingest changes.
5. Port thin **Beta `TrustStore`** + year-scale place-hash utilities; do **not** port patient graph / connascence.
6. Minimal `pytest` (schema + `view(year)` invariants + golden smoke).
7. Optional: deeper Karpat appendix OCR via `ocr_forge --resume`; optional UNHCR COO refetch.

---

## 7. Reusable Code Exploration

### A. `2OPMD/2ndOpinionMD/ptv-embed-lab`

| Pattern | Location (approx.) | Reuse |
| --- | --- | --- |
| Place hash + bins (`delta/gap/level/vol`) | `ptv_embed/lab_movement.py` | **High** — retune bins to years/decades and share deltas |
| `stamp_node_context` / place embedding | `ptv_embed/node_context.py` | **Adapt** → `anchor_context` on polity×religion series |
| Beta trust ledger | `ptv_embed/learning.py` | **Copy** nearly as-is |
| Hypothesis predict/settle registry | `ptv_embed/hypotheses.py` | **Adapt** claims to share/edge outcomes |
| Frozen cohort normalizer | `ptv_embed/embed.py` | **Later** — after hash catalog shows lift |
| GPU cosine matmul | `ptv_embed/code_filter.py` | **Optional util** |
| Patient graph, connascence, MIMIC, LOINC | various | **Do not copy** |

Docs worth reading: `docs/PLAN_LAB_MOVEMENT_CONTEXT_SPACE.md`, `docs/REPORT_PHASE0_LEARNINGS_AND_RISE_PATH.md`, `docs/MEMO_HYPOTHESIS_LEARNING_LOOP.md`, `docs/STRATEGY_V0.1_EMBEDDING_SPACE.md`.

**Effort (honest):** ~1–1.5 weeks MVP hash+catalog on demo polities; +1 week trust loop; +1.5–2 weeks demography embeddings. **~4–6 weeks** to a useful v1 inference layer.

### B. `nakatomi` (crypto-crawler learning loop)

| Pattern | Location (approx.) | Reuse |
| --- | --- | --- |
| Settlement-only learning (`bump` only on settled outcomes) | `crypto_crawler/learning.py` | **High** — same discipline as ptv |
| Source-class trust posteriors | evidence settle paths | **High** — `source_trust:pew`, `hand_seed_v0`, … |
| Graded settlement / calibration (ARGYLE) | `crypto_crawler/argyle/` | **Medium–High** for volume bands; still shadow/research code |
| Price vol bands, reactor, portfolio | `vol.py`, `reactor.py`, … | **Do not port** |

**Transfer thesis:** Nakatomi settles distributions over **who to believe** (Beta on trust keys), not over a full demographic state vector. That maps to Conflux **source trust + forecast calibration**, not a drop-in predictor of population shares.

---

## 8. Direction & Feasibility (Author Opinion)

**Direction:** Prediction is the **North Star** (1975→present backtests with a confidence threshold; miss = result). Day-to-day work still centers on **confidence-aware representation of sparse series**, place-hashes, and settlement-gated trust — because those are what make the North Star *testable*, and they remain valuable if forecasts fail. GPU embeddings stay optional scaling.

**Feasibility:**

| Track | Feasibility | Notes |
| --- | --- | --- |
| Demo + data desk + volatility report (Phase 0) | **High** | Mostly glue + docs; 1–2 weeks |
| Place-hash + holdout scorecard (Phase 1 lite) | **High** | Proven pattern in ptv; sparse years need careful binning |
| Source-trust Bayesian loop (Phase 2 lite) | **Medium–High** | Portable; needs a real settlement tape (next census / edge realization) |
| Calibrated 1975→now prediction *attempt* (Phase 3) | **Medium** | Achievable as backtests + baselines; **success not required** for the study to land |
| “We can predict MENA demography” as a strong claim | **Low unless evidence appears** | Threshold miss is the honest default prior |
| Full vision (GPU store, ancient backfill, org overlays) | **Low near-term** | Scope creep; separate papers |

**Recommended sequencing (opinionated):**

1. Events JSONL (**done** — 3 triggers) + keep `make verify-all` green as the living shape-of-data report.  
2. Edge→node deltas + overlay wiring (WJP / WPP first).  
3. `conflux/movement.py` + `conflux/learning.py` ports.  
4. Hash catalog scorecard vs share-reversion baseline.  
5. Design the **1975 cut / forward settle** protocol early (even before the model is smart).  
6. Embeddings / GPU only if they help the scorecard.  
7. Paper can lead with uncertainty + movement structure; North Star results (hit or miss) in a dedicated section.

**Bottom line:** Aim at prediction without tying the project’s worth to beating the threshold. Sibling code is reusable for the path that makes that test real.

---

## Appendix — Processed artifacts (as of this revision)

```
data/processed/anchors.jsonl
data/processed/anchors_historical_seed.jsonl
data/processed/edges.jsonl
data/processed/population_totals.jsonl
data/processed/ottoman_empire_population.jsonl
data/processed/ottoman_1914_provinces.jsonl
data/processed/unhcr_refugee_stock_by_coa.jsonl
data/processed/un_desa_migrant_stock_destination.jsonl
data/processed/arda_national_profiles_2005.jsonl   # after ingest_arda.py
data/processed/population_totals_worldbank.jsonl   # after ingest_worldbank_population.py
data/processed/pcbs_projected_population.jsonl     # after ingest_pcbs.py
data/processed/cbs_file_catalog.jsonl              # after catalog_cbs.py
data/processed/jewishdatabank_wjp_catalog.jsonl    # after catalog_jewishdatabank.py
data/processed/wjp_world_core_jewish_population.jsonl
data/processed/wjp_country_core_jewish_population.jsonl
data/processed/arab_barometer_religion_shares.jsonl
data/processed/basihos_turkey_borders_population.jsonl
data/processed/karpat_religious_structure_summary.jsonl
data/processed/mccarthy_six_vilayets_religion.jsonl
data/processed/un_desa_migrant_stock_od.jsonl
data/processed/events.jsonl
```

Regenerate key series:

```bash
.venv/bin/python scripts/ingest_owid_population.py
.venv/bin/python scripts/ingest_ottoman_wiki.py
.venv/bin/python scripts/ingest_unhcr.py
.venv/bin/python scripts/ingest_un_desa_ims.py
.venv/bin/python scripts/ingest_un_desa_ims_od.py
.venv/bin/python scripts/ingest_arda.py
.venv/bin/python scripts/ingest_worldbank_population.py
.venv/bin/python scripts/ingest_pcbs.py
.venv/bin/python scripts/ingest_wjp.py
.venv/bin/python scripts/ingest_arab_barometer_religion.py
.venv/bin/python scripts/ingest_basihos_turkey_borders.py
.venv/bin/python scripts/ingest_karpat_religious_summary.py
.venv/bin/python scripts/ingest_mccarthy_six_vilayets.py
.venv/bin/python scripts/seed_events.py
.venv/bin/python scripts/catalog_cbs.py
.venv/bin/python scripts/catalog_jewishdatabank.py
```
