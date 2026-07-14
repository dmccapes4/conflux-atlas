# REPORT — Phase 3 Backtest & Bridge (1975 cut)

**Date:** 14 July 2026  
**Protocol:** Pre-registered banded share forecasts (`PREREGISTRATION` in `conflux/backtest.py`) + sparsity→simulation bridge (`conflux/bridge.py`)  
**Artifacts:** `data-validation-reports/PHASE3_BACKTEST.json`, `PHASE3_BRIDGE.json`  
**Reproduce:** `make phase3-backtest` / `make phase3-bridge`  
**Contracts:** `make test-phase3` (44 passed)

## 1. What ran

| Tape | Settled | Notes |
| --- | ---: | --- |
| Banded forecast backtest | **216** | Full `anchors.jsonl`, groups muslim/christian/jewish, cut 1975, coverage 0.80 |
| Bridge holdout settle | **37** | Fit on 675 modern transitions (`year_from ≥ 1920`); McCarthy **excluded** (2) |
| Basihos | — | 16 population rows, **no religion shares** → not settleable |

Pre-registration (pinned by tests): cut **1975**, nominal coverage **0.80**, primary metric **mean interval score** (Winkler), success rule = candidate beats all baselines. This run is **baselines only** (`candidate: null`).

## 2. Backtest — baselines on the primary metric

| Policy | n | Coverage observed | Mean interval score ↓ | Mean width |
| --- | ---: | ---: | ---: | ---: |
| **persistence** | 108 | 0.593 | **0.321** | 0.182 |
| reversion | 108 | 0.565 | 0.327 | 0.182 |
| ar1 | **0** | — | — | — |

**Verdict:** best baseline = **persistence**. No candidate policy was entered.

### Misses (reported, not hidden)

1. **Coverage miss.** Stated central coverage is 0.80; observed ≈ **0.59** (persistence) / **0.57** (reversion). Bands are too narrow (or points too far) for the realized post-cut tape. Interval score still ranks policies because it charges for both width and misses.
2. **`ar1` silent.** Abstention floor is ≥3 train points with `year ≤ 1975`. Most polity series on the desk have only two pre-cut religion-share anchors (typically 1900 + 1950), so AR1 correctly returns no claims. Silence is an honest result, not a bug — same sparsity story as Phase 1/2 `hash_mode`.
3. **Shock split.** With the current event tape, every settled claim window overlaps a tagged event (notably 1979), so calm n=0 / shock n=108 per active policy. The calm/shock machinery works; the event catalog is thin relative to 1975→2010 forecast windows.

Brier on forecast claims: **0.293**.

## 3. Bridge — modern-fit dynamics into sparse eras

| Quantity | Value |
| --- | ---: |
| Fit window | `year_from ≥ 1920` |
| Transitions fitted | 675 |
| Mean rate / decade (muslim+christian+jewish) | −0.0049 |
| Rate std / decade | 0.027 |
| Settled holdouts | 37 |
| Hits | 11 |
| Coverage observed | **0.297** (stated 0.80) |
| Contested excluded (McCarthy) | **2** |
| `dynamics:modern_fit` posterior mean | 0.308 (α=12, β=27) |

**Protocol notes:**

- **Karpat LOO** (3 empire muslim-share rows): each year estimated from the other Karpat anchors; bands widen with gap.
- **Ottoman 1914 provinces** (34): settled against a Karpat-era empire prior (cross-polity — a weak generative prior, not a like-for-like series).
- **McCarthy Six Vilayets:** structurally unable to settle; counted in `n_excluded_contested` via the single `PREREGISTRATION` exclusion tuple.
- **Basihos:** totals only; cannot score share bands.

### Miss (the §4 deliverable)

Stated 80% bands contained the realized holdout share **29.7%** of the time. That is a clear **calibration miss**: modern-fit rate uncertainty, applied as a prior over sparse/cross-polity years, does not yet produce honest coverage on this holdout mix. The miss is the result — not something to tune away after looking at the tape. Next iterations can tighten the holdout design (same-polity series only; denser Karpat extraction) without moving the pre-registered scoring rule.

## 4. Design choices left alone

- **Interval score over hit rate** as primary: hit rate alone rewards absurdly wide bands; Winkler charges for width and misses at 2/α.
- **Baselines-first:** the protocol runs today; any smart candidate later enters against the frozen rule.
- **Targets = realized post-cut anchor years only** — no interpolated “truth.”

## 5. Definition of done

- [x] `conflux/forecast.py`, `conflux/backtest.py`, `conflux/bridge.py`
- [x] `make test-phase3` green (44 contracts, 0 skipped)
- [x] `make test` green
- [x] `PHASE3_BACKTEST.json` + `PHASE3_BRIDGE.json`
- [x] This report — coverage miss, AR1 silence, and bridge undercoverage written plainly
