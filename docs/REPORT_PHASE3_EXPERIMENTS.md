# REPORT — Phase 3 Expanded Experimentation (E1–E7)

**Date:** 14 July 2026  
**Plan:** `PHASE3_EXPERIMENT_PLAN.md` (executed in full; E8 ingest remains open)  
**Artifacts:** `PHASE3_CUT_SWEEP.json`, `PHASE3_WIDTH_ABLATION.json`, `PHASE3_CANDIDATES.json`, `PHASE3_BRIDGE_CURVES.json`  
**Reproduce:** `python scripts/run_phase3_experiments.py` · contracts: `make test-phase3` (63 green, incl. 19 new)  
**Standing rules honored:** `PREREGISTRATION` untouched; every number ships with n and a Wilson 95% interval; misses reported as results.

**One protocol amendment (recorded before any confirmatory run):** the plan proposed selecting width models on cut-1950/1990 tapes, but those tapes' targets are the *same realized rows* (2005–2020) as the 1975 tape's — cross-cut selection would leak outcomes into the confirmatory set. Selection therefore uses a deterministic **series split**: sha1(polity|group) even → selection half, odd → confirmatory half. Outcome rows are disjoint by construction. All tapes exclude `hand_seed_v0` and contested sources from **targets** (hand seeds remain train material only — the Phase 2.5 circularity lesson applied to forecasting).

---

## 1. E1 + E2 — cut sweep on anchor-only and desk-augmented tapes

Persistence, w0 widths, stated coverage 0.80:

| Tape | n | Coverage [Wilson 95%] | Mean IS | ar1 n |
| --- | ---: | --- | ---: | ---: |
| anchors@1950 | 72 | 0.542 [0.427, 0.652] | 0.354 | 0 |
| anchors@1975 | 72 | 0.542 [0.427, 0.652] | 0.354 | 0 |
| anchors@1990 | 72 | 0.542 [0.427, 0.652] | 0.354 | 0 |
| **anchors@2000** | 72 | **0.861** [0.762, 0.923] | 0.153 | 72 |
| desk@1950 | 123 | 0.553 [0.464, 0.639] | 0.489 | 0 |
| desk@1975 | 130 | 0.523 [0.438, 0.607] | 0.457 | 12 |
| desk@1990 | 130 | 0.523 [0.438, 0.607] | 0.457 | 12 |
| **desk@2000** | 130 | **0.838** [0.766, 0.892] | 0.247 | 121 |
| desk@2010 | 426 | 0.638 [0.591, 0.682] | 0.222 | 75 |

**Findings.**

1. **The density diagnosis is confirmed.** Cuts 1950/1975/1990 produce *identical* anchor tapes — there is no train data between 1950 and 2000, so moving the cut moves nothing. The moment the 2000 anchors enter the train (cut 2000), coverage jumps from 0.542 to 0.861 and IS halves. The Phase 3 coverage miss was staleness, not method: with a fresh state (5–20y horizon instead of 25–45y), w0 widths are essentially calibrated (0.838–0.861 vs stated 0.80, inside the Wilson interval).
2. **ar1 speaks when the desk feeds it.** anchors-only: silent until cut 2000. Desk tape at 1975: n=12 (WJP 1970 supplies third points), coverage 0.833 [0.552, 0.953] — small but real, and it's the calibrated policy on that tape.
3. **anchors@2010 (cov 0.144) is a degeneracy, not a forecast result:** 567 of 603 persistence claims come from single-point trains (Pew-only polities) where share_std = 0 → zero-width bands that must miss. The non-degenerate subset covers 0.972. Protocol note for any future run: band claims from train_n=1 need a width floor or an abstention rule — left unfixed here because fixing it after seeing the tape would be tuning.
4. **Per-target-source lanes work** (desk@1975 persistence): ARDA IS 0.341, Arab Barometer 0.400, Pew 0.496, WJP 0.034, CBS 1.000 (CBS bands are the widest — Israel's jewish series is volatile in train). The definitional-lane worry is measurable now instead of hypothetical.

## 2. E5 — polity-aware shock split (measurement fix)

Old tagging: calm 0 / shock 108 (degenerate). New contact rule (event must touch the claim's polity via `affected_polities` or a triggered migration edge), desk@1975 persistence:

| Slice | n | Coverage [Wilson] | Mean IS | Mean width |
| --- | ---: | --- | ---: | ---: |
| calm | 97 | 0.433 [0.339, 0.532] | 0.413 | 0.137 |
| shock | 33 | 0.788 [0.622, 0.893] | 0.589 | 0.551 |

**Finding (non-obvious):** shock-series claims *cover better* but *score worse*. Shock-affected polities (Israel, Iran, Turkey lanes) have volatile trains → w0 emits wide bands (0.551 vs 0.137) that catch the outcome but pay the width penalty. Forecast *skill* (IS) degrades under shocks as expected; coverage alone would have said the opposite. This is exactly why the interval score is the primary metric.

## 3. E7 — hygiene layer

- **Wilson intervals everywhere:** stated 0.80 lies outside every pre-2000 persistence interval — the miss is statistically significant, not noise.
- **Climatology floor:** desk@1975 climatology IS = 1.586 vs persistence 0.457. Every active policy clears the no-skill floor by ~3×; the tapes are informative.
- **Permutation control:** shuffling realized shares within (group, level-bin) strata worsens persistence IS by ×1.18 (desk@1975) and ×1.37 (desk@2000) — bands are series-specific, not "wide enough to cover anything." The weakest ratio is anchors@1975 (×1.07): the anchor tape carries little identity information beyond level, a caution against over-reading its rankings.

## 4. E3 — width-model ablation (selection on even half, one confirmatory shot)

Selection (even-hash series, cuts 1975+1990, persistence): **w0** mean |cov−0.80| = 0.161 · **w1** 0.161 · **w2** 0.200 (IS 0.832 — level-conditioned sigma over-widens) · **w3** 0.003. Frozen winner: **w3** (conformal inflation of the w0 shape; λ fit on pre-cut walk-forward folds = 2.5 persistence / 3.0 reversion / 1.0 ar1).

Confirmatory shot — odd-hash series, cut 1975, single pre-registered attempt:

| Policy (w3) | n | Coverage [Wilson] | Mean IS |
| --- | ---: | --- | ---: |
| persistence | 69 | 0.681 [0.564, 0.779] | 0.426 |
| reversion | 64 | 0.812 [0.700, 0.889] | 0.482 |
| ar1 | 8 | 1.000 [0.676, 1.000] | 1.000 |
| *w0 reference (same half)* | 69 | 0.420 | 0.494 |

**Verdict:** w3 moves persistence coverage from 0.420 to 0.681 and improves IS (0.494 → 0.426) — a real repair, selected without touching the confirmatory outcomes. But 0.80 sits just outside the Wilson interval: **still a (now much smaller) calibration miss.** The λ fit on the selection half's pre-cut folds under-inflates for the confirmatory half's mix. Reversion under w3 is calibrated (0.812). No second shot taken.

## 5. E4 — candidates vs the frozen success rule

Ensemble weights fit on the selection half degenerated to pure ar1 (its n=12 selection tape was easy) — on the confirmatory half it could claim only n=8 and scored IS 1.000. **Ensemble: entered and lost.** Reported as such.

Analog retrieval (place-context cosine neighbors, fixed k=25, min 8 neighbors, no tuning), confirmatory half @1975:

| Policy | n | Coverage [Wilson] | Mean IS | Beats all baselines? |
| --- | ---: | --- | ---: | --- |
| **analog** | 64 | 0.719 [0.599, 0.814] | **0.415** | **yes** (0.415 < 0.426/0.482/1.000) |

Under the pre-registered rule, **analog is the first candidate to beat all baselines on the primary metric.** The honest caveat comes from the paired comparison on the 64 shared targets: mean IS difference (persistence − analog) = **+0.041 in analog's favor, bootstrap 95% CI [−0.113, +0.184]** — the interval spans zero, and analog abstained on 5 easy targets persistence aced (IS 0.031). So: *nominal win under the frozen rule, not statistically resolved at this sample size.* Both statements go in Paper B; neither is softened into the other.

## 6. E6 — bridge disaggregated + the calibration-vs-sparsity curve

**E6a — pooled 0.297 was two experiments wearing one number:**

| Lane | n | Coverage [Wilson] | Mean IS |
| --- | ---: | --- | ---: |
| Karpat LOO (same polity), linear | 3 | 0.667 [0.208, 0.939] | 0.283 |
| Ottoman provinces (cross-polity stress test), linear | 34 | 0.265 [0.146, 0.431] | 0.839 |

The legitimate same-polity experiment is n=3 — too small to say anything (the Wilson interval spans 0.21–0.94). The cross-polity stress test fails exactly as province heterogeneity predicts. **E8 ingest (deeper Karpat extraction) is the only way to grow the lane that matters.**

**E6b/E6c — anchor-drop curves (282 LOO holdouts across 37 dense desk series):**

| Gap (years) | n | Coverage, linear width | Coverage, sqrt width |
| --- | ---: | --- | --- |
| 1–5 | 210 | 0.495 [0.428, 0.562] | 0.624 [0.557, 0.687] |
| 6–10 | 15 | 0.667 | 0.667 |
| 11–25 | 6 | 0.833 | 0.833 |
| 26–50 | 51 | **0.922** [0.815, 0.969] | 0.824 [0.697, 0.904] |

**Finding — the curve is *inverted*.** The plan expected coverage to decay with gap; instead the bridge under-covers most where anchors are *densest*. At 1–5-year gaps the interpolation point is good but the gap-proportional width collapses toward zero — and what's left is **measurement noise between sources** (Pew vs ARDA vs AB definitional scatter), which the width model prices at zero. At 26–50-year gaps the rate-uncertainty term dominates and is generous. The bridge width model needs a **constant measurement-noise floor** (a nugget, in kriging terms) added to the gap term; sqrt-shape (E6c) is a partial patch (0.495→0.624 at short gaps, at the cost of the long-gap lane) but the additive floor is the structural fix. This is the single most useful thing the expanded experiments produced: the sparsity bridge's failure mode is *definitional noise at high density*, not *extrapolation at low density* — the opposite of what Phase 3 assumed, and directly actionable (estimate the nugget per group from same-polity-year cross-source spreads, which the connascence complement/definition edges already index).

## 7. What changed in code

- `conflux/experiments.py` (new): series builders (anchor / desk-augmented), width models w0–w3 + conformal-λ fit, generalized banded claims with target-source exclusions, climatology floor, Wilson/permutation hygiene, analog + ensemble candidates, paired bootstrap comparison, anchor-drop curves, disaggregated bridge blocks.
- `conflux/connascence.py`: `tag_shock_claims_contact` (polity-aware E5 fix; window-only tagger kept for transition claims).
- `conflux/bridge.py`: `width_shape=` ("linear"|"sqrt") on `backfill_series`.
- `scripts/run_phase3_experiments.py` (new): one runner for all suites.
- `tests/test_phase3_experiments.py` (new, 19 contracts): degenerate-vs-contact tagging, Wilson/permutation math, width monotonicity + λ pre-cut-only fit, target-exclusion and abstention hygiene, analog no-self-neighbors, width-shape crossover.

## 8. Follow-ups (in leverage order)

1. **Bridge nugget:** add a per-group measurement-noise floor to `backfill_series`, estimated from cross-source same-polity-year spreads (connascence definition edges already list the pairs). Then re-run E6b — the curve should flatten toward 0.80 everywhere.
2. **E8 ingest:** mid-century anchors remain the bottleneck for every pre-2000 tape; Karpat appendix depth specifically unlocks E6a's same-polity lane.
3. **Analog at larger n:** the candidate's nominal win needs the denser desk (post-ingest) to resolve the paired CI.
4. **train_n=1 width floor** for the 2010-cut degeneracy, pre-registered before the next sweep.
