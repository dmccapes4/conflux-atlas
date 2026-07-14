# Phase 3 Test Spec — The 1975 Cut (banded forecasts, pre-registered backtest, sparsity bridge)

**For:** Grok (implementer)  
**Contracts:** `tests/test_phase3_forecast.py`, `tests/test_phase3_backtest.py`, `tests/test_phase3_bridge.py` (marker `phase3`; they `importorskip` and stay green until the modules exist — run `make test-phase3`)  
**Strategy:** `STRATEGY_V0.2.md` §5 Phase 3 + §4 (sparsity→simulation bridge). North Star: *calibrated* forecasts, falsifiable protocol, **a threshold miss is itself a publishable result**.

Three new modules. Reuse, don't reinvent: `Claim`/`TrustStore` (`conflux/learning.py` — graded `settle(weight=)` already exists), `tag_shock_claims` (`conflux/connascence.py`), `calibration_table`/`brier_score` (`conflux/settlement.py`).

---

## 1. `conflux/forecast.py` — banded share forecasts

The Phase 2 policy tape predicted *direction*. Phase 3 predicts a **share value with a central interval** — the calibration target is "does the realized share land inside the band at the stated rate".

### 1.1 `BandForecast` (frozen dataclass)

Fields: `polity_id, group, cut_year, target_year, point, lo, hi, coverage, policy, train_n, meta` (dict, default empty).

Invariants (validated at construction — raise `ValueError`):
- `0.0 <= lo <= point <= hi <= 1.0` (shares clipped into [0,1] *before* construction);
- `target_year > cut_year`;
- `0.0 < coverage < 1.0`.

### 1.2 Policies

`FORECAST_POLICIES = ("persistence", "reversion", "ar1")` — these are also Paper B's baselines. An optional `"analog"` (place-vector retrieval) may be added later; tests only cover the three.

`forecast_series(points, *, cut_year, target_years, policy, coverage=0.80) -> list[BandForecast]`

`points` = sorted `[(year, share), …]` for one (polity, group) series.

Hard rules:
1. **Temporal hygiene:** only points with `year <= cut_year` may influence the output in ANY way (point, band, abstention). The test mutates post-cut points and asserts identical output.
2. **Abstention by train length:** persistence needs ≥ 1 train point, reversion ≥ 2, ar1 ≥ 3. Below that: return `[]` for that policy (abstention is first-class; no zero-width guesses).
3. **Point semantics:**
   - `persistence`: point = last train share.
   - `reversion`: point lies **between the last train share and the train mean, inclusive** (a pull-back toward the mean; exact fraction is implementer's choice, pinned only by the betweenness contract).
   - `ar1`: fit on train **deltas**; on a synthetic constant-delta (linear) series the point must continue the trend within ±0.005 per step.
4. **Bands:**
   - `lo <= point <= hi` always; width > 0 whenever the train series has any variance;
   - **monotone widening:** for the same series+policy, band width is non-decreasing in `target_year` (uncertainty grows with horizon);
   - a train series with zero variance (all same share) may produce a degenerate band for persistence but must still produce `width >= 0` and satisfy all other invariants.
5. **Determinism:** identical inputs → identical outputs (no RNG without a fixed seed).
6. Clipping: bands never leave [0,1].

---

## 2. `conflux/backtest.py` — the pre-registered 1975 protocol

### 2.1 `PREREGISTRATION` (module-level, read-only mapping)

The tests **pin these exact values** — changing any of them means changing the tests in the same commit, which is the point (the pre-registration is enforced by diff visibility):

```python
PREREGISTRATION = MappingProxyType({
    "cut_year": 1975,
    "coverage": 0.80,          # nominal central-interval coverage
    "alpha": 0.20,             # 1 - coverage; interval-score parameter
    "policies": ("persistence", "reversion", "ar1"),
    "primary_metric": "mean_interval_score",
    "success_rule": "candidate_beats_all_baselines_on_primary_metric",
    "contested_validation_excluded": ("mccarthy_armenian_pop_ottoman",),
})
```

`contested_validation_excluded` implements STRATEGY §6.7: McCarthy-class sources are confidence-capped *inputs*, **never validation targets**.

### 2.2 `interval_score(y, lo, hi, *, alpha=0.20) -> float`

Winkler interval score — the proper scoring rule for central intervals (lower is better):

```
S = (hi - lo)
  + (2/alpha) * (lo - y)   if y < lo
  + (2/alpha) * (y - hi)   if y > hi
```

Pinned exact values (alpha=0.2 → penalty factor 10):
- inside: `interval_score(0.5, 0.4, 0.6) == 0.2` (just the width);
- below: `interval_score(0.3, 0.4, 0.6) == 0.2 + 10*0.1 == 1.2`;
- above: `interval_score(0.7, 0.4, 0.6) == 0.2 + 10*0.1 == 1.2`.

### 2.3 `make_forecast_claims(anchors, *, groups, policies=None, prereg=PREREGISTRATION) -> list[Claim]`

- Build per-(polity, group) share series from anchors (highest-confidence per year — same dedupe rule as `movement.py`).
- **Targets are realized post-cut anchor years only** — never interpolated years (no invented ground truth).
- Anchors whose primary source is in `contested_validation_excluded` are dropped from **targets** (they may still appear in pre-cut training).
- One claim per (series, target_year, policy): `hypothesis_id = f"forecast:{policy}"`, `predicted = "in_band"`, `stated_p = coverage`, `year_from = cut_year`, `year_to = target_year`, and `meta` carrying `point/lo/hi/coverage/policy/realized_share` (realized filled at settle time or carried for settlement — implementer's choice, but settlement must not re-read anchors it wasn't given).
- Claims must be **shock-taggable**: after `tag_shock_claims(claims, events)`, every claim has `meta["shock"]` — the report splits calm/shock.

### 2.4 `settle_forecast_claims(claims, anchors, store) -> int`

- `success = lo <= realized_share <= hi`; record + settle exactly once (double settle raises — inherited from `TrustStore.settle`).
- Settlement bumps `forecast:<policy>` posteriors.

### 2.5 `backtest_report(claims, *, prereg=PREREGISTRATION) -> dict`

JSON-serializable. Per policy: `n`, `coverage_observed`, `mean_interval_score`, `mean_width`, calm/shock split of the same. Top level: `preregistration` echo (as a plain dict), `verdict` — for each non-baseline policy (when one exists), whether it beat **all** baselines on the primary metric; with only the three baselines present, `verdict` compares them and names the best but sets `"candidate": None`. **A miss is reported, never hidden:** report generation must not raise when coverage is far from nominal.

---

## 3. `conflux/bridge.py` — sparsity→simulation bridge (§4)

Dense-window dynamics as a generative prior over sparse eras, settled against held-out real anchors. Bands, not points; anchors dominate.

### 3.1 `fit_dynamics(anchors, *, groups, fit_start=1920) -> dynamics`

- Fit on transitions with `year_from >= fit_start` **only**. The test mutates pre-1920 data and asserts the fit is unchanged.
- Representation is the implementer's choice (suggested: per level-bin rate/decade mean+std, reusing `movement.level_bin`), but it must expose `dynamics.fit_start` and `dynamics.n_transitions` for the report.
- Raise `ValueError` if fewer than 10 qualifying transitions (an unusable fit must be loud, not silent).

### 3.2 `backfill_series(anchor_points, dynamics, *, years, coverage=0.80) -> list[BandEstimate]`

`anchor_points` = sorted `[(year, share)]` real anchors for one series; `years` = years to estimate.

`BandEstimate` (frozen): `year, point, lo, hi, coverage, nearest_anchor_gap`.

Contracts:
1. **Anchors dominate:** at a year that IS an anchor year, `point == anchor share` and the band width at that year is ≤ the width at every non-anchor year in the same call.
2. **Widening with distance:** band width is non-decreasing in `nearest_anchor_gap` (compare any two estimates from one call).
3. Bounds: everything in [0,1]; `lo <= point <= hi`.
4. Determinism.

### 3.3 `settle_backfill(estimates, holdout_anchors, store, *, hypothesis="dynamics:modern_fit") -> dict`

- `success = lo <= holdout share <= hi` for holdout anchors at estimated years; claims under `hypothesis`; settle-once discipline.
- **Contested exclusion:** holdout anchors whose primary source is in `PREREGISTRATION["contested_validation_excluded"]` are **skipped, never settled**, and counted in the returned dict as `n_excluded_contested`. (Import the tuple from `conflux.backtest` — one pre-registration, one truth.)
- Returns `{"n_settled": int, "n_hits": int, "n_excluded_contested": int}`.

### 3.4 Calibration

Reuse `settlement.calibration_table` on the backfill claims — stated coverage vs realized hit rate is the §4 deliverable ("does the stated band contain the realized anchor at the stated rate?").

---

## 4. Wiring expectations (not covered by contracts, but part of Phase 3 done-ness)

- `scripts/run_phase3_backtest.py`: full-population 1975 run → `data-validation-reports/PHASE3_BACKTEST.json` + calm/shock calibration; `scripts/run_phase3_bridge.py`: fit 1920+, backfill pre-1920, settle on Ottoman/Karpat/Basihos anchors (McCarthy excluded) → `PHASE3_BRIDGE.json`.
- `make test-phase3` exists and behaves like the other phase targets (exit 5 → "not implemented yet", green).
- Report doc `docs/REPORT_PHASE3_BACKTEST.md` once the tape exists — **write the miss if it misses.**

## 5. Design notes / rationale

- **Interval score over hit-rate as primary metric:** hit rate alone rewards absurdly wide bands; the Winkler score charges for width *and* for misses at rate 2/α, so honest narrow bands win. Coverage is still reported for calibration.
- **Targets = realized anchor years only:** interpolating a "truth" to forecast against would manufacture ground truth — the same rule as Phase 1's no-interpolation contract.
- **Baselines first, candidate later:** the three baselines make the protocol runnable *today*; any future "smart" policy (analog retrieval, trust-weighted ensemble) enters as a candidate against the frozen rule. Pre-registration is enforced socially by the pinned tests: you cannot move the goalposts without a visible diff.
- **Bridge exclusion imports from backtest:** one `contested_validation_excluded` tuple, used by both consumers, so the exclusion can never drift apart between Paper B and the bridge.
