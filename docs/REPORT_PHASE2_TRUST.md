# REPORT — Phase 2 Trust Ledger (Settlement Gate)

**Date:** 14 July 2026  
**Protocol:** 1975-cut policy claims + forward source corroboration  
**Artifact:** `data-validation-reports/PHASE2_TRUST.json`  
**Reproduce:** `make phase2-trust` / `.venv/bin/python scripts/run_phase2_trust.py`

## 1. What ran

| Family | Settled claims | Notes |
| --- | ---: | --- |
| Policy (`policy:*`) | 219 | Demo catalog, muslim/christian/jewish, `cut_year=1975`, `min_bucket_n=2` |
| Source corroboration (`source_trust:*`) | 36 | Full `anchors.jsonl`, ±5pp, `max_gap_years=30` |
| **Total** | **255** | Brier = **0.228** |

## 2. Policy posteriors (who to trust as a *predictor*)

| Hypothesis | Mean | Trials | α / β |
| --- | ---: | ---: | --- |
| `policy:persistence` | **0.662** | 72 | 49 / 25 |
| `policy:majority` | 0.610 | 75 | 47 / 30 |
| `policy:reversion` | 0.608 | 72 | 45 / 29 |
| `policy:hash_mode` | — | **0** | *silent* |

**Result:** On the 1975-cut tape, **persistence earns the most trust**; majority and reversion are close behind. **`hash_mode` made zero claims** at `min_bucket_n=2` — place buckets trained only on `year_to ≤ 1975` are too thin to speak after the cut. That is the same sparsity story as Phase 1 (hash lost to majority on LOPO), now visible as *abstention* rather than a low score. A silent policy is an honest result, not a bug.

This also matches Phase 1's LOPO ranking flavor (persistence / majority strong; hash weak under hand-seed density).

## 3. Source posteriors (who to believe as a *citation*)

| Hypothesis | Mean | Trials | Note |
| --- | ---: | ---: | --- |
| `source_trust:hand_seed_v0` | **0.947** | 36 | 2000 hand seeds corroborated by Pew 2010 within 5pp / 30y |

**Pew / wiki / survey:** no `source_trust:*` rows yet. Corroboration needs a *later independent* anchor within the gap cap. On the current desk, Pew 2010/2020 are usually the *last* religion-share anchors for a polity — nothing after them settles Pew. Ottoman wiki / ARDA / Arab Barometer live in overlay files, not as multi-source share series on the same polity timeline in `anchors.jsonl`.

So the first real "who to believe" ledger entry is: **hand seeds at 2000 are tightly corroborated by the next Pew snapshot** (35/36 within tolerance). That is encouraging for the seed→Pew join, and it says almost nothing yet about Pew's own trust — Pew has not been *settled*, only used as a settler.

## 4. Calibration

| Bin (stated_p) | n | stated mean | observed |
| --- | ---: | ---: | ---: |
| [0.5, 0.6) | 147 | 0.50 | 0.65 |
| [0.6, 0.8) | 102 | 0.65 | 0.71 |
| [0.8, 1.0] | 6 | 0.80 | 1.00 |

Observed frequencies track stated confidence directionally but sit **above** the diagonal in the lower bins (underconfident on this tape). Brier **0.228** is better than a constant-0.5 forecaster (0.25) and worse than a sharp well-calibrated one — fine for a sparse first cut.

## 5. Caveats (do not overclaim)

- Demo transitions are sparse; `hash_mode` silence is expected until denser modern windows or more groups enter the catalog.
- Source trust is currently a **one-edge** story (hand_seed → Pew). Expand by wiring overlay share series into the corroboration timeline, or lengthening gaps carefully with explicit era tags.
- PortalGC / `provenance-engine` stays off this path (STRATEGY v0.2 §8.C).

## 6. Definition of done (Phase 2)

- [x] `make test-phase2` green (29 contracts)
- [x] `make test` green (Phases 0+1+2)
- [x] `PHASE2_TRUST.json` written
- [x] This report cites the artifact honestly — silent hash and high hand-seed corroboration included as results
