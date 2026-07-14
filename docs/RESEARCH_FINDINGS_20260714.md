# RESEARCH FINDINGS — Conflux Atlas, 14 July 2026

**Scope:** everything measured between Phase 0 (schema gates) and Bridge v2 (nugget-calibrated backfill), one build day.
**Posture:** objective; misses reported with the same precision as wins. Every number below is reproducible from a committed artifact (`data-validation-reports/`) and a runner script.
**Suite:** 235 tests green. Branches merged: PRs #1–#5.

---

## 1. System under study

A confidence-aware evidence system over religious-demography share series for MENA polities + diaspora. State is a set of *anchors* and *observations*: source `s` states share `x ∈ [0,1]` for (polity `p`, group `g`, year `t`) with confidence `c`. Around this sit five measured subsystems:

1. **Trust ledger** — Beta-Bernoulli posteriors per hypothesis, settlement-only updates.
2. **Connascence layer** — typed edges (structural / conceptual / co-variance / temporal) that change how settlements are *weighted and routed*, not what is claimed.
3. **LLM proposer** — a scored, verifier-gated enrichment agent inside the same ledger.
4. **Banded forecaster + pre-registered backtest** — share forecasts as central intervals, Winkler-scored.
5. **Sparsity bridge** — modern-fit dynamics backfilled into sparse eras with calibrated bands.

## 2. Trust arithmetic (Phases 2–2b)

### 2.1 Graded Beta-Bernoulli updates

Posterior per hypothesis `h`: \( \theta_h \sim \mathrm{Beta}(\alpha, \beta) \), prior \( \mathrm{Beta}(1,1) \). A settlement with outcome \( y \in \{0,1\} \) and weight \( w \in (0,1] \):

\[ (\alpha, \beta) \leftarrow (\alpha + w\,y,\; \beta + w\,(1-y)) \]

`w < 1` implements (a) the **independence discount** — corroborations between same-method-family sources (census/survey/synthesis/derived/scholarly registry) carry `w = 0.5`, because two surveys agreeing is weaker evidence than a survey agreeing with a census; and (b) **partial settlement** — one-hop propagation along strict-tier co-variance edges at `w = strength × coefficient`, capped ≤ 0.25.

### 2.2 Level-scaled corroboration tolerance

A flat ±5 pp tolerance is absurd at trace shares (any two near-zero values "agree"). Tolerance is binned by level: trace ±0.5 pp, minority ±1 pp, significant ±3 pp, else ±5 pp; observations < 0.5 pp are non-reports and never settle.

### 2.3 Definitional routing — measured effect

377 corroboration claims re-settled with discounts + routing (14 claims rerouted off `source_trust:*` onto `definition_gap:*` lanes):

| Hypothesis | Unweighted mean | Weighted + routed | Δ |
| --- | ---: | ---: | ---: |
| `jewishdatabank_wjp` | 0.667 | 0.500 | **−0.167** |
| `cbs_population_madaf` | 0.667 | 0.750 | **+0.083** |
| `pew_2010_2020` | 0.700 | 0.688 | −0.012 |
| `definition_gap:cjp_vs_pew_jewish` | — | 0.800 | new lane |
| `definition_gap:cbs_arab_proxy_vs_pew_muslim` | — | **0.167** | new lane |

**Finding:** WJP's trust was inflated by definition-overlap agreement with Pew (core-Jewish vs affiliation), and CBS was drained by an Arab-proxy-vs-muslim definition mismatch that is now quarantined in its own lane. The 0.167 on that lane is itself a result: the proxy systematically over-counts (folds in Arab Christians and Druze).

## 3. Co-variance discovery: the multiple-testing result (Phase 2b)

For series pair \( (A, B) \), over all overlapping *moving* transition pairs, agreement is directional co-movement. The null is **bucket-stratified**: for transitions with origin place-hashes \( a, b \),

\[ p_{\text{null}} = \overline{ p_a p_b + (1-p_a)(1-p_b) } , \qquad p_h = P(\text{up} \mid \text{moving},\ \text{hash}=h) \]

so "both series are secularly declining" cannot mint an edge. Admission: \( n \ge 3 \) overlaps, one-sided exact binomial \( P(X \ge k \mid n, p_{\text{null}}) < 0.05 \), **and** Benjamini–Hochberg survival across all scored pairs (\( p_{(i)} \le \alpha\, i/m \)).

Measured on 3,852 scored cross-polity pairs:

- raw α tier: **4 real edges** (best p = 0.012 at n = 7);
- shuffle control (outcomes permuted within series): **20 raw-α edges** — *more than the real tape*;
- BH-FDR survivors: **0**, real and shuffled.

**Finding:** at thousands of candidates with n = 3–9 overlaps each, raw α admits noise faster than signal — the shuffle control proved it quantitatively, and the FDR gate is not optional. Consequence wired into code: a **strict tier** (FDR survivors; the only input to partial settlement — currently empty, so partial settlement correctly fired 0 times) and a **hypothesis tier** (raw-α; clusters/REVIEW/LLM input only). The bottleneck is data density (anchor grid 1900/1950/2000/2010/2020 caps overlaps at ~2 per pair), not the statistic.

## 4. LLM proposer under scorekeeping (Phase 2b → full population)

Protocol: local `qwen3:8b`, deterministic decoding (T=0, top-k 1, seed 42), closed vocabularies, JSON schema-forced, windowed (12 items/call); every proposal enters the ledger as a claim; **deterministic verifiers are the only promotion path**; abstention is free; the proposer has its own posterior.

| Run | Windows | Proposals | Verified | Rejected | Posterior mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pilot (with decoys) | 6 | 56 | 50 | 6 | 0.879 |
| Full population | 40 | 467 | 458 | 9 | **0.979** |

Timing: 16.95 s/call mean, 677.9 s total, 0 malformed windows. Error taxonomy from the pilot: all 3 planted no-edge decoys were mislabeled `complement` — and all 3 were caught by verifiers; 2 true `conservation` pairs mislabeled (fairly penalized); 1 unproven `definition` proposal rejected by the systematic-offset test. Event attribution abstained on all offered clusters (correct: the closed event list doesn't explain post-1950 growth co-movements).

**Finding:** a small local model is a reliable *classifier inside closed vocabularies* when every output is verifier-gated and its accuracy is priced in the same ledger as the data sources. Its measured failure mode is ontology confusion between coupling kinds, not hallucination.

## 5. Pre-registered banded backtest (Phase 3)

### 5.1 Protocol

Frozen before running: cut 1975; nominal central coverage 0.80 (α = 0.20); policies persistence / reversion / AR1; primary metric mean **Winkler interval score**

\[ S_\alpha(\ell, u; y) = (u-\ell) + \tfrac{2}{\alpha}(\ell-y)\,\mathbf{1}[y<\ell] + \tfrac{2}{\alpha}(y-u)\,\mathbf{1}[y>u] \]

(lower is better; charges width *and* misses); success rule "candidate beats all baselines on primary metric"; contested sources (McCarthy) excluded from validation targets; targets = realized post-cut anchor years only (no interpolated truth). Baseline width (w0): \( \text{half} = z_{0.80}\,\hat\sigma_{\text{train}}\sqrt{h/10} \), h = years past last train point.

### 5.2 First run (baselines only)

| Policy | n | Coverage (stated 0.80) | Mean IS |
| --- | ---: | ---: | ---: |
| persistence | 108 | 0.593 | 0.321 |
| reversion | 108 | 0.565 | 0.327 |
| ar1 | 0 (abstained) | — | — |

Bridge pooled holdouts: 37 settled, coverage **0.297**. Both misses were published as results before any diagnosis.

## 6. Expanded experimentation (E1–E7)

All coverage numbers now carry Wilson 95% score intervals: \( \tilde{p} \pm \frac{z}{1+z^2/n}\sqrt{\hat p(1-\hat p)/n + z^2/4n^2} \).

### 6.1 The coverage miss is train staleness (E1/E2)

Cuts 1950/1975/1990 produce byte-identical anchor tapes (no train data 1950–2000 → the cut moves nothing). When year-2000 anchors enter (cut 2000): coverage 0.542 → **0.861** [0.762, 0.923], IS 0.354 → 0.153. Desk-augmented series (multi-source timeline; hand-seed and contested sources excluded from *targets*) unlock AR1 (n = 12 at cut 1975 via WJP-1970 third points, coverage 0.833).

### 6.2 Width ablation with leakage-safe selection (E3)

Cross-cut selection would leak (cut-1950/1990 tapes share realized 2005–2020 target rows with the 1975 tape), so selection used a deterministic **series split**: sha1(polity|group) even → selection, odd → confirmatory. Four width models: w0 (above); w1 walk-forward residual quantiles; w2 level-conditional dynamics σ; w3 **conformal inflation** — w0 shape × the smallest λ (grid) achieving 0.80 empirical coverage on *pre-cut* walk-forward folds. Selection (min mean |cov − 0.80|): w3 (0.003) ≫ w0/w1 (0.161) > w2 (0.200); fitted λ = 2.5 / 3.0 / 1.0 (persistence/reversion/ar1).

Single confirmatory shot, odd half @1975: persistence coverage 0.420 → **0.681** [0.564, 0.779], IS 0.494 → 0.426. Improved and *still a miss* (0.80 outside the interval); reversion under w3 calibrated (0.812). No second shot taken.

### 6.3 First candidate to pass the frozen rule (E4)

**Analog retrieval** — origin-context place vectors (level/prior-delta/gap/vol one-hots + raw share and prior rate, L2-normalized; outcome features excluded from the query by construction), cosine top-k = 25 cross-series neighbors from the train-window transition catalog, forecast distribution = neighbor rate/decade quantiles (10/50/90) × horizon. Fixed hyperparameters, no tuning.

| Confirmatory half @1975 | n | Coverage | Mean IS |
| --- | ---: | ---: | ---: |
| analog | 64 | 0.719 [0.599, 0.814] | **0.415** |
| persistence (w3) | 69 | 0.681 | 0.426 |
| reversion (w3) | 64 | 0.812 | 0.482 |
| climatology floor | 642 | 0.838 | 0.976 |

Nominal win under the pre-registered rule. Paired on the 64 shared targets: mean IS difference (persistence − analog) = **+0.041**, bootstrap 95% CI **[−0.113, +0.184]** — spans zero. Analog also abstained on 5 easy targets (persistence IS there: 0.031). Both statements stand; neither is softened. The ensemble candidate (weights grid-fit on the selection half degenerated to pure AR1) entered and lost (IS 1.000).

### 6.4 Shock split, made meaningful (E5)

Window-only event tagging is degenerate on cut→target windows (any event tags every claim: calm 0 / shock 108). With the polity-contact rule (event's `affected_polities` or a triggered migration edge must touch the claim's polity): calm 97 / shock 33, and

| Slice | Coverage | Mean IS | Mean width |
| --- | ---: | ---: | ---: |
| calm | 0.433 | 0.413 | 0.137 |
| shock | 0.788 | 0.589 | 0.551 |

**Finding:** shock series *cover better but score worse* — volatile trains produce wide bands that catch outcomes and pay for width. Coverage alone would have inverted the conclusion; this is the concrete argument for a proper scoring rule as primary metric.

### 6.5 Controls (E7)

- **Climatology floor** (group train-mean, 10–90% train-dispersion band): IS 1.586 vs persistence 0.457 (desk@1975) — all live policies clear the no-skill floor by ~3×.
- **Permutation control** (realized shares shuffled within group × level-bin strata, 200 draws): IS worsens ×1.18 (desk@1975), ×1.37 (desk@2000), ×1.07 (anchors@1975) — bands are series-specific, weakest on the information-poor anchor tape, as expected.

## 7. Sparsity→simulation bridge: inversion and repair

### 7.1 The inverted curve (E6b)

282 leave-one-out holdouts over 37 dense desk series, coverage vs distance-to-nearest-anchor:

| Gap | n | Coverage (linear width, no nugget) |
| --- | ---: | --- |
| 1–5 y | 210 | **0.495** [0.428, 0.562] |
| 6–10 y | 15 | 0.667 |
| 11–25 y | 6 | 0.833 |
| 26–50 y | 51 | **0.922** [0.815, 0.969] |

**Finding:** the failure mode is the opposite of the design assumption. At long gaps the rate-uncertainty term \( z\sigma \cdot (g/10) \) is honest-to-generous; at short gaps it collapses to zero and the residual error is **cross-source definitional scatter**, priced at nothing.

### 7.2 The nugget (v2)

Measurement noise estimated from cross-source same-polity-year(±3) spreads: for independent noise, \( \mathrm{Var}(x_1 - x_2) = 2\sigma_m^2 \Rightarrow \hat\sigma_m = \mathrm{sd}(d)/\sqrt{2} \).

| Group | \( \hat\sigma_m \) (share points) | n pairs |
| --- | ---: | ---: |
| muslim | 0.0382 | 50 |
| christian | 0.0458 | 13 |
| jewish | 0.0152 | 14 |

Scale check: modern rate volatility is 0.027/decade, so cross-source definitional noise ≈ **1.4 decades of real movement**. Width becomes quadrature: \( \text{half} = z\sqrt{\sigma_m^2 + (\sigma_{\text{eff}}\, g_\ast)^2} \), \( g_\ast \in \{g/10, \sqrt{g/10}\} \), with \( \sigma_{\text{eff}} = 2\sigma \) over event windows touching the polity (pre-declared multiplier). Nugget applies off-anchor only (anchor exactness preserved; all prior contracts pass unchanged).

### 7.3 The curve, un-inverted

| Gap | Phase 3 | v2 (sqrt + nugget) |
| --- | ---: | ---: |
| 1–5 y | 0.495 | **0.848** [0.793, 0.890] |
| 6–10 y | 0.667 | 0.800 |
| 26–50 y | 0.922 | 0.882 |
| overall | 0.589 | **0.851** |

Every bucket's Wilson interval contains the stated 0.80; mean bucket miscalibration 0.148 → 0.041; short-gap IS *improved* (0.218 → 0.166), i.e. the wider bands pay for themselves under the proper scoring rule. Product shipped: 4,592 banded rows on a 5-year grid (`BRIDGE_V2_BACKFILL.jsonl`); era-mean widths pre-1920 0.087, 1920–1999 **0.116** (the anchor desert), 2000+ 0.055.

## 8. Negative and null results (kept on the record)

1. **PortalGC geometry ≠ evidential quality** (Phase 2.5): Lorenz-attractor KEEP/EVICT classification showed no useful correlation with independently learned source trust on this graph.
2. **BH-FDR: 0 strict co-variance edges** — the 1948–72 Jewish positive control is floored out by MIN_SHARE + grid coarseness; partial settlement therefore fired 0 times, by arithmetic.
3. **Conservation claims: 0 settleable** — bracketing 1948–51 edges needs mid-century anchors that don't exist yet (nearest: 1900/1950).
4. **AR1 silence on anchor tapes** — honest abstention (≥3 pre-cut points required), not a bug.
5. **anchors@2010 coverage 0.144 is a degeneracy**: 567/603 claims from single-point trains → zero-width bands (non-degenerate subset: 0.972). A width floor for train_n = 1 is noted for pre-registration *before* the next sweep, not patched retroactively.
6. **Same-polity historical bridge lane: n = 3** — Wilson [0.061, 0.792] is consistent with anything; no width model fixes a sample-size problem.
7. **Event tape has no empire-level polities** — `shock_windows_for_polity("ottoman_empire")` = ∅; the mechanism is live but the tape names successor states only.

## 9. The load-bearing methodological commitments

Ranked by how much they changed conclusions today:

1. **Proper scoring rule as primary metric** — coverage alone would have inverted the shock finding (§6.4) and rewarded the climatology floor.
2. **Controls travel with every discovery loop** — the shuffle control (§3) and permutation control (§6.5) each caught an over-claim before it shipped.
3. **Selection/confirmation separation with leakage checks** — the cross-cut leak (§6.2) was found *before* selection ran; the amendment is documented in the plan changelog.
4. **Settlement-only learning with graded weights** — the ledger's trust numbers moved in interpretable, defensible directions (§2.3) rather than by fiat.
5. **Estimating parameters from data rather than tuning on outcomes** — the nugget (§7.2) was measured from cross-source spreads; the confirmatory tape stayed unburned.
6. **Abstention as a free, first-class outcome** — everywhere (AR1, LLM, analog, conservation) silence carried information instead of being forced into noise.

## 10. Open items, in leverage order

1. **E8 mid-century ingest (1930–1990)** — one ingest unblocks four consumers: co-variance strict tier, conservation claims, shock-split calm side, same-polity bridge holdouts.
2. **Empire-membership mapping on the event tape** — activates shock widening for Ottoman-era series.
3. **train_n = 1 width floor** — pre-register, then re-sweep.
4. **Analog candidate at larger n** — paired CI resolution needs the denser desk.
5. **Definitional lanes in the forecaster** — per-target-source blocks exist; a CJP↔affiliation discount at claim time is the next step.

## 11. Reproducibility

| Result | Artifact | Runner |
| --- | --- | --- |
| Trust + routing | `PHASE2B_TRUST.json` | `scripts/run_phase2b_connascence.py` |
| Co-variance + controls | `PHASE2B_CONNASCENCE.json` | same |
| LLM proposer | `PHASE2B_LLM_ENRICHMENT.json` | `scripts/run_llm_enrichment.py --full` |
| Pre-registered backtest | `PHASE3_BACKTEST.json` | `scripts/run_phase3_backtest.py` |
| E1–E7 | `PHASE3_CUT_SWEEP / WIDTH_ABLATION / CANDIDATES / BRIDGE_CURVES .json` | `scripts/run_phase3_experiments.py` |
| Bridge v2 | `PHASE3_BRIDGE_V2.json`, `BRIDGE_V2_BACKFILL.jsonl` | `scripts/run_bridge_v2.py` |

Contracts: `make test` (235), phase-scoped `make test-phase{1,2,3}`.
