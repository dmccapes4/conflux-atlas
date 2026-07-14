# REPORT — Beacon tranche-1 ingest (Syria / Lebanon / Iran deepen)

**Date:** 14 July 2026  
**Branch:** `feature/event-beacons`  
**Reproduce:** `make beacon-tranche1 && make phase2b && make phase3-backtest`

## What landed

| Artifact | Change |
| --- | --- |
| Events | **5** (was 3): +`syrian_civil_war_2011`, +`lebanese_civil_war_1975`; Iran gains Israel-bound effect |
| Edges | **20** (was 10): 6 UNHCR Syria→host stock edges @2015, 3 Labaki Lebanon 1975–77, 1 Iran→Israel |
| OD series | `unhcr_syria_refugee_stock_od.jsonl` (140 rows, coo=SYR × hosts 2011–2024) |
| BIBLIOGRAPHY | `beacon_tranche1_v0`, `labaki_abu_rjaili_2005`, Shaw/SCPR/IDMC PDF notes |
| Phase 2b tagging | Switched to **`tag_shock_claims_contact`** so Syria does not paint every 2010–2020 polity as shock |

## Phase 2b delta (full re-run)

| Metric | Before tranche-1 | After |
| --- | ---: | ---: |
| Policy claims in shock windows | **0** | **63** |
| Conservation edges considered | 10 | 20 |
| Conservation settled | 0 | **6** (4 OK, 2 VIOLATED: Lebanon/Turkey gains vs Syria loss accounting) |
| Complement edges | 451 | 451 |

Shock vs calm hit rates (majority): calm **0.672** vs shock **0.481** — first real calm/shock split on the policy tape.

## Phase 3

Banded backtest and bridge numbers unchanged (still baselines-only; ar1 silent; bridge cov 0.30). Forecast shock tagging remains window-based per Phase 3 contracts; denser events will matter more once contact tagging is wired there or targets widen.

## Honest limits

- UNHCR volumes are **stocks**, not flows — edged as order-of-magnitude bursts with confidence 0.65.
- Labaki edges use a single religion group (schema limit) for a mixed confessional outflow.
- Conservation “VIOLATED” on Syria→Lebanon/Turkey is expected when dest population gains dwarf attributed refugee stocks — signal, not a silent pass.
- Karpat/Shaw/SCPR PDFs are on disk but **not** yet table-extracted into share anchors.

## Next

1. Extract Karpat/Shaw tables into anchors (OCR forge if needed).  
2. Optional: wire Phase 3 forecast claims through contact shock tagging.  
3. LLM enrichment only after the deterministic desk is accepted.
