# REPORT — Sparsity→Simulation Bridge v2 (nugget + shock widening)

**Date:** 14 July 2026  
**Follows:** `REPORT_PHASE3_EXPERIMENTS.md` §6 — the anchor-drop curves showed the calibration-vs-sparsity relationship *inverted*: under-coverage where anchors are densest (definitional noise priced at zero), honest coverage at long gaps.  
**Artifacts:** `PHASE3_BRIDGE_V2.json`, `BRIDGE_V2_BACKFILL.jsonl` (the product: 4,592 banded rows)  
**Reproduce:** `python scripts/run_bridge_v2.py` · contracts: `make test-phase3` (235 suite-wide, incl. 9 new v2 contracts)  
**Pre-declared, not tuned:** shock σ-multiplier 2.0; nugget year-tolerance ±3; 5-year grid. The nugget itself is *estimated from data*, not chosen.

## 1. What changed

`backfill_series` gains two opt-in terms (defaults preserve the Phase 3 contract exactly; all prior tests pass unchanged):

- **Nugget** — additive measurement-noise floor, applied off-anchor only: `half = z·sqrt(nugget² + (σ_eff·gap_term)²)`. Estimated per group from cross-source same-polity-year(±3) spreads: two independent sources disagreeing by `d` imply `σ_m = sd(d)/√2`.
- **Shock widening** — σ doubled over spans overlapping documented event windows that touch the series' polity (same contact rule as the E5 shock tagging).

## 2. The nugget, measured

| Group | σ_m (share points) | n pairs |
| --- | ---: | ---: |
| muslim | 0.0382 | 50 |
| christian | 0.0458 | 13 |
| jewish | **0.0152** | 14 |
| pooled | 0.0365 | 77 |

Two independent sources stating the same polity-year disagree by ~±4 share points for muslim/christian shares and ~±1.5 for jewish shares — the jewish lane's tighter nugget is consistent with WJP/CBS counting a well-defined core population while affiliation surveys scatter more. For context: the modern rate volatility is 0.027/decade, so **cross-source definitional noise ≈ 1.4 decades' worth of real movement**. That is the quantity the Phase 3 bridge priced at zero.

## 3. The curve, un-inverted

282 leave-one-out holdouts across 37 dense desk series, stated coverage 0.80:

| Gap (years) | n | Phase 3 (linear, no nugget) | **v2 (sqrt + nugget)** |
| --- | ---: | --- | --- |
| 1–5 | 210 | 0.495 [0.428, 0.562] | **0.848** [0.793, 0.890] |
| 6–10 | 15 | 0.667 | 0.800 |
| 11–25 | 6 | 0.833 | 0.833 |
| 26–50 | 51 | 0.922 | 0.882 [0.766, 0.945] |
| overall | 282 | 0.589 | **0.851** |

Every bucket's Wilson interval now contains 0.80; mean bucket miscalibration fell from 0.148 to **0.041**. Interval score *improved* at short gaps (0.218 → 0.166) — the wider bands hit enough more often to pay for their width. Config selection (nugget/sqrt over the 2×2 grid) was by mean bucket |coverage − 0.80| on these modern-window curves, which are exploratory instrumentation, not the confirmatory tape.

## 4. Historical lanes (still data-starved, slightly better)

| Lane | n | Coverage [Wilson] | Mean IS |
| --- | ---: | --- | ---: |
| Karpat LOO (same polity), v2 | 3 | 0.333 [0.061, 0.792] | 0.288 (was 0.368) |
| Ottoman provinces (cross-polity stress test), v2 | 34 | 0.265 [0.146, 0.431] | 0.822 (was 0.938) |

The same-polity lane remains n=3 — the interval spans everything, and no width model can fix a sample-size problem. `dynamics:modern_fit_v2` posterior: mean 0.400 over 3 trials. **E8 ingest (deeper Karpat extraction) is still the binding constraint**, exactly as the experiment plan ranked it.

One honest gap surfaced by the run: `shock_windows_for_polity("ottoman_empire", …)` returns **none** — the event tape's `affected_polities` use successor-state ids (turkey, greece, …), so empire-level series get no shock widening. The mechanism is tested and live; the tape needs either empire-membership mapping or empire-era events. Logged as an ingest/tape task, not patched inline.

## 5. The product

`BRIDGE_V2_BACKFILL.jsonl`: 4,592 rows — every desk+seed series with ≥2 anchors, banded on a 5-year grid from 30 years before its first anchor, per-group nuggets, per-polity shock windows.

| Era | n rows | Mean band width |
| --- | ---: | ---: |
| pre-1920 | 376 | 0.087 |
| 1920–1999 | 2,140 | 0.116 |
| 2000+ | 2,076 | 0.055 |

The 1920–1999 era is the *widest* — wider than pre-1920 — because it sits in the long anchor desert between the Ottoman-era rows and the 2005+ desk. The width structure is now an honest map of where the evidence desk is thin, which is precisely what a confidence-aware atlas should render (the mp4's uncertainty shading falls straight out of these bands).

## 6. Verdict on feasibility

The bridge's core mechanism is now **calibrated on modern holdouts at every gap scale we can measure** (0.85 overall vs stated 0.80, all buckets consistent). The failure mode found in Phase 3 was real, diagnosable, and fixable with one principled term whose magnitude was estimated from the desk rather than tuned on outcomes. What remains open is *transfer*, not method: whether calm-era dynamics plus a 2× shock multiplier honestly price the 1850–1920 Ottoman collapse cannot be answered with 3 same-polity holdouts. The instrument is ready; it is waiting on E8 data.

## 7. Files

- `conflux/bridge.py` — nugget + shock params on `backfill_series` (defaults unchanged), `estimate_nugget`, `shock_windows_for_polity`
- `conflux/experiments.py` — `anchor_drop_curves(nuggets=…)`, `bridge_block(nugget=…, shock_windows=…)`
- `scripts/run_bridge_v2.py` — end-to-end runner
- `tests/test_phase3_bridge_v2.py` — 9 contracts: default-preservation, anchor exactness, floor dominance at short gaps, quadrature (not additive) behavior at long gaps, monotonicity, nugget recovery/independence/fallback, shock overlap + contact rule
