# Phase 3 — Expanded Experimentation Plan

**Date:** 14 July 2026  
**Follows:** `REPORT_PHASE3_BACKTEST.md` (first 1975 run: coverage 0.59 vs stated 0.80; bridge 0.297; ar1 silent; shock split degenerate)  
**Binding constraint:** the 1975 tape has been *seen*. It is now the confirmatory set. All selection (band models, policies, hyper-anything) happens on pre-cut folds or alternate cuts; re-runs against 1975 are labeled exploratory until a frozen candidate takes one confirmatory shot. `PREREGISTRATION` does not move.

Each experiment names its question, method, deliverable, and what would count as a result. Ordered by leverage.

---

## E1 — Cut sweep: is 1975 special, or is the protocol miscalibrated everywhere?

**Question:** does under-coverage persist across cut years, or is it an artifact of the 1900/1950-only pre-cut desk?

**Method:** run the identical protocol at cuts **1950, 1990, 2000, 2010** (grid; no tuning between runs). Later cuts have denser trains (Pew 2010 enters at cut 2010; desk sources at 1990+) and shorter horizons — if coverage recovers as train density rises and horizon shrinks, the diagnosis "density problem, not method problem" is confirmed quantitatively.

**Deliverable:** `PHASE3_CUT_SWEEP.json` + a coverage-vs-cut / IS-vs-cut table in the report. Wilson 95% intervals on every observed coverage (see E7).

**Result criteria:** monotone (or clearly non-) relationship between train density / horizon and coverage. Either way it's a Paper B figure.

## E2 — Desk-augmented series: unlock ar1 and multiply targets

**Question:** what does the backtest look like on the *full evidence desk* instead of anchors-only?

**Method:** build series from the merged anchor+observation timeline (the `desk_movement_events` merge from Phase 2b, highest-confidence per year). Pre-cut this adds WJP 1970, Ottoman-era points; post-cut it adds ARDA 2005, AB waves, CBS annual, WJP yearly as *targets* (with the definition-overlap lanes from connascence §2.2 respected — a CJP target must not settle a Pew-trained band without the definitional discount, or jewish series will manufacture misses).

**Why it matters:** ar1 needs ≥3 pre-cut points — the desk provides them for several series; target count grows well past 216; and the 25-year stale-state problem shrinks wherever the desk has 1960s–70s points.

**Deliverable:** `PHASE3_BACKTEST_DESK.json`, same report shape; ar1 row populated (or its continued silence now *means* something).

## E3 — Band-width ablation: fix calibration without touching the tape

**Question:** which uncertainty model yields honest coverage — selected *without* looking at post-cut outcomes?

**Candidates (all fit on pre-cut data only):**

- **W0** current: `z · share_std · sqrt(horizon/10)` (control);
- **W1** walk-forward residuals: within the train window, forecast each train point from its predecessors, collect |residual| per decade of gap, take the empirical 80% quantile → width scales from *measured* one-step error, not raw share_std;
- **W2** dynamics-conditional: per level-bin rate_std from `bridge.fit_dynamics` (fit ≤ cut), width = z · σ_level · sqrt(decades);
- **W3** conformal-style: W0 shape × a single inflation factor chosen so pre-cut folds hit 80% empirically.

**Selection rule (pre-registered here):** pick the winner on **cut-1950 and cut-1990 tapes only** (E1 machinery). The frozen winner then takes **one** confirmatory shot at 1975. No second shots without a new plan doc.

**Deliverable:** `PHASE3_WIDTH_ABLATION.json`; the confirmatory 1975 number goes in the report with the label "single pre-registered attempt."

## E4 — A real candidate policy: the success rule finally gets used

**Question:** can anything beat persistence on mean interval score under the frozen rule?

**Candidates (max two, to keep the multiple-comparisons budget honest):**

1. **Analog retrieval:** place-vector cosine neighbors (Phase 1 catalog, train-window only) vote on the outcome distribution; band = neighbor-outcome quantiles. This is the Phase 1 machinery finally entering the pre-registered arena.
2. **Shrinkage ensemble:** convex combination of persistence/reversion/ar1 points with weights fit on pre-cut walk-forward IS; band from E3's winner.

**Method:** develop on cuts 1950/1990; one confirmatory run each at 1975 via `success_rule: candidate_beats_all_baselines_on_primary_metric`. A loss is reported as a loss.

**Deliverable:** verdict block with `candidate` non-null for the first time; win or lose, this is Paper B's central table.

## E5 — Polity-aware shock gating: repair the degenerate split

**Question (measurement fix, not tuning):** with shock defined as *an event whose affected polities or triggered edges touch the claim's polity*, does forecast skill differ calm vs shock?

**Method:** extend `tag_shock_claims` with a polity-contact rule (same contact logic as `verify_event_attribution`); optionally sub-window tagging (shock only if event falls within ±k years of the *target*, not anywhere in cut→target). Re-report all E1/E2 runs' calm/shock splits. Expectation from Phase 2: persistence degrades under shocks; if it doesn't, that's interesting.

**Deliverable:** calm/shock rows that are no longer 0/108; a `shock_gated` abstention experiment (policies abstain on shock-tagged targets — does aggregate IS improve?).

## E6 — Bridge, disaggregated: separate the legitimate experiment from the stress test

**Question:** what is the calibration of modern-fit backfill on *like-for-like* series, and what is the calibration-vs-gap curve?

**Method:**

- **E6a same-polity holdouts only:** Karpat empire LOO (expand extraction if possible), WJP series where pre-1920 points exist, Ottoman *province* anchors settled against province-level priors only when a province series exists. Report separately from cross-polity.
- **E6b anchor-drop curves:** on dense modern series (Pew+desk 1990–2020), progressively hide anchors, backfill the hidden years, measure coverage as a function of `nearest_anchor_gap`. This produces the *calibration-vs-sparsity curve* — the §4 deliverable and a natural Paper A figure, obtainable at scale without any pre-1920 extraction.
- **E6c width-shape variant:** current width is linear in gap; test sqrt(gap) (random-walk scaling) on E6b curves. Selection on modern-window curves only; pre-1920 stays confirmatory.
- **E6d interval score for the bridge** (not just hit rate), same α.

**Deliverable:** `PHASE3_BRIDGE_CURVES.json` + report section replacing the single pooled 0.297 with: same-polity coverage, cross-polity coverage (labeled a stress test), and the coverage-vs-gap curve.

## E7 — Statistical hygiene layer (applies to all of the above)

- **Wilson 95% intervals** on every observed coverage (0.593 on n=108 → ≈ [0.50, 0.68]; the 0.80 miss is significant, not noise — say so with the interval, every time).
- **Climatology baseline** for IS: group-level train-mean point with the width that would have covered 80% of *train* dispersion — the "no-skill but honest-width" floor every policy must beat.
- **Permutation control** (Phase 2b shuffle lesson): permute realized shares across same-group/level series; all policies' IS should collapse toward climatology. Guards against bands wide enough to "win" on anything.
- **Sample accounting:** per-policy n stratified by train_n and horizon decade in every artifact.

## E8 — Priority ingest supporting all of it (one target, three consumers — carried from Phase 2b)

Mid-century (1930–1990) share anchors remain the highest-leverage single ingest: they densify pre-1975 trains (E1/E2/ar1), populate the calm side of shock splits (E5), and extend same-polity bridge holdouts (E6a). Candidates already cataloged on the desk: deeper Karpat appendix OCR, CBS historical yearbooks, WJP pre-1970 volumes.

---

## Execution order & budget

| Step | Experiments | Cost | Gate |
| --- | --- | --- | --- |
| 1 | E7 hygiene + E5 tagging fix (measurement layer first) | small | tests for polity-aware tagging + Wilson math |
| 2 | E1 cut sweep + E2 desk series | medium | re-run report; no selection decisions yet |
| 3 | E6b/E6c anchor-drop curves (modern window) | medium | curve artifact |
| 4 | E3 width ablation on cuts 1950/1990 | medium | frozen winner declared in this doc's changelog |
| 5 | E4 candidates on 1950/1990 → one confirmatory 1975 shot each | medium | verdict block |
| 6 | E6a same-polity bridge + E8 ingest as it lands | ongoing | report v2 |

**Standing rules:** `PREREGISTRATION` untouched; the 1975 tape gets exactly one confirmatory run per frozen candidate; every number ships with n and an interval; a miss is a result.

---

## Changelog

**14 July 2026 — executed (results: `REPORT_PHASE3_EXPERIMENTS.md`).**

- *Amendment (declared before any confirmatory run):* selection on cut-1950/1990 tapes would leak — their targets are the same realized 2005–2020 rows as the 1975 tape's. Replaced with a deterministic series split: sha1(polity|group) even → selection, odd → confirmatory. Outcome rows disjoint by construction.
- *E3 frozen winner:* **w3** (conformal inflation of the w0 shape; λ = 2.5/3.0/1.0 for persistence/reversion/ar1, fit on selection-half pre-cut folds). Selection rule as pre-registered: min mean |coverage−0.80| across cuts {1975, 1990}, tie-break mean IS. One confirmatory shot taken; result 0.681 [0.564, 0.779] — improved, still a (smaller) miss.
- *E4 verdict:* analog beats all baselines on the primary metric (nominal win under the frozen rule); paired bootstrap CI spans zero — not resolved at n=64. Ensemble entered and lost.
- E8 (mid-century ingest) remains open.
