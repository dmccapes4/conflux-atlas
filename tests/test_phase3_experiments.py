"""Phase 3 expanded-experimentation contracts (PHASE3_EXPERIMENT_PLAN.md).

Pins the E5 tagging fix, E7 hygiene math, E3 width-model invariants, E4
candidate abstention/no-leakage, and the E6 width-shape ablation.
"""

from __future__ import annotations

import math

import pytest

pytestmark = pytest.mark.phase3

exps = pytest.importorskip("conflux.experiments")
from conflux.bridge import Dynamics, backfill_series  # noqa: E402
from conflux.connascence import tag_shock_claims, tag_shock_claims_contact  # noqa: E402
from conflux.experiments import (  # noqa: E402
    SeriesPoint,
    analog_claims,
    climatology_claims,
    compute_width,
    fit_conformal_lambda,
    make_series_claims,
    permutation_control,
    policy_block,
    settle_band_claims,
    wilson_interval,
)
from conflux.learning import Claim, TrustStore  # noqa: E402
from conflux.schema import Event, MigrationEdge  # noqa: E402


def _pt(year, share, conf=0.8, src="src_a"):
    return SeriesPoint(year=year, share=share, confidence=conf, source=src)


def _series(pid="egypt", group="muslim", pts=None):
    pts = pts or [
        _pt(1900, 0.80),
        _pt(1930, 0.82),
        _pt(1950, 0.85),
        _pt(1970, 0.86),
        _pt(2010, 0.90),
        _pt(2020, 0.91),
    ]
    return {(pid, group): pts}


def _claim(pid="iran", y_from=1975, y_to=2010, **meta):
    base = {"realized_share": 0.5, "lo": 0.4, "hi": 0.6, "policy": "persistence"}
    base.update(meta)
    return Claim(
        claim_id=f"c_{pid}_{y_to}",
        hypothesis_id="forecast:persistence",
        polity_id=pid,
        group="muslim",
        cut_year=y_from,
        predicted="in_band",
        stated_p=0.8,
        train_n=2,
        year_from=y_from,
        year_to=y_to,
        meta=base,
    )


# ---------------------------------------------------------------------------
# E5 — polity-aware shock tagging
# ---------------------------------------------------------------------------


def _iran_event():
    return Event(
        event_id="iranian_revolution_1979",
        year=1979,
        year_end=1985,
        title="Iranian Revolution",
        affected_polities=["iran"],
        source_ids=["seed"],
        confidence=0.9,
    )


def test_window_tagging_degenerates_but_contact_does_not():
    """The bug the fix exists for: window-only tags every long claim."""
    claims = [_claim("iran"), _claim("morocco"), _claim("egypt")]
    tag_shock_claims(claims, [_iran_event()])
    assert all(c.meta["shock"] for c in claims)  # degenerate: calm n=0

    n = tag_shock_claims_contact(claims, [_iran_event()])
    assert n == 1
    assert claims[0].meta["shock"] is True
    assert claims[1].meta["shock"] is False and claims[2].meta["shock"] is False


def test_contact_via_triggered_migration_edge():
    edge = MigrationEdge(
        edge_id="e1",
        year_start=1979,
        year_end=1985,
        from_polity="iran",
        to_polity="israel",
        group="jewish",
        volume_est=50_000,
        kind="expulsion_or_flight",
        trigger_event_id="iranian_revolution_1979",
        confidence=0.8,
        source_ids=["seed"],
    )
    claims = [_claim("israel"), _claim("morocco")]
    tag_shock_claims_contact(claims, [_iran_event()], [edge])
    assert claims[0].meta["shock"] is True  # destination of triggered edge
    assert claims[1].meta["shock"] is False


def test_contact_respects_window():
    claims = [_claim("iran", y_from=1990, y_to=2010)]  # window after the event
    tag_shock_claims_contact(claims, [_iran_event()])
    assert claims[0].meta["shock"] is False


# ---------------------------------------------------------------------------
# E7 — hygiene math
# ---------------------------------------------------------------------------


def test_wilson_interval_bounds_and_known_value():
    lo, hi = exps.wilson_interval(64, 108)  # the Phase 3 persistence tape
    assert 0.0 <= lo < 64 / 108 < hi <= 1.0
    assert 0.80 > hi  # the 0.80 miss is significant, not noise
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo1, hi1 = wilson_interval(5, 5)
    assert hi1 == 1.0 and lo1 > 0.4


def test_permutation_control_worsens_score_for_informative_bands():
    # Bands centered on each realized value: actual score must beat shuffled.
    claims = []
    for i, y in enumerate([0.1, 0.3, 0.5, 0.7, 0.9]):
        for pid in ("a", "b", "c"):
            c = _claim(pid, y_to=2000 + i, realized_share=y, lo=y - 0.05, hi=y + 0.05)
            c.settled = True
            c.success = True
            claims.append(c)
    res = permutation_control(claims, n_perm=50, seed=1)
    assert res["actual_mean_is"] < res["perm_mean_is"]
    assert res["perm_over_actual_ratio"] > 1.0


def test_climatology_width_uses_train_dispersion_only():
    series = _series()
    # Second series so the group-level train pool clears the min-5 floor.
    series[("syria", "muslim")] = [_pt(1900, 0.81), _pt(1950, 0.84), _pt(2010, 0.92)]
    claims = climatology_claims(series, cut_year=1975, tape="t")
    assert claims  # 2010/2020 targets exist
    for c in claims:
        # Train pool is 0.80..0.86 → band must not reach the 0.90+ targets.
        assert c.meta["hi"] <= 0.87


# ---------------------------------------------------------------------------
# E3 — width models
# ---------------------------------------------------------------------------


TRAIN = [(1900, 0.80), (1930, 0.82), (1950, 0.85), (1970, 0.86)]


@pytest.mark.parametrize("model", ["w0", "w1", "w3"])
def test_width_monotone_in_horizon(model):
    w_short, _ = compute_width(TRAIN, target_year=1990, policy="persistence", model=model)
    w_long, _ = compute_width(TRAIN, target_year=2020, policy="persistence", model=model)
    assert w_long >= w_short >= 0.0


def test_w2_uses_level_conditional_sigma():
    dyn = Dynamics(
        fit_start=1920,
        n_transitions=20,
        rate_mean=0.0,
        rate_std=0.02,
        by_level={"dominant": (0.0, 0.005), "trace": (0.0, 0.04)},
    )
    w_dom, _ = compute_width(
        [(1950, 0.95), (1970, 0.96)], target_year=2000, policy="persistence",
        model="w2", dynamics=dyn,
    )
    w_tr, _ = compute_width(
        [(1950, 0.005), (1970, 0.006)], target_year=2000, policy="persistence",
        model="w2", dynamics=dyn,
    )
    assert w_tr > w_dom  # trace shares are the volatile stratum here


def test_w3_inflates_w0_by_lambda():
    w0, _ = compute_width(TRAIN, target_year=2000, policy="persistence", model="w0")
    w3, meta = compute_width(
        TRAIN, target_year=2000, policy="persistence", model="w3", conformal_lambda=2.5
    )
    assert math.isclose(w3, 2.5 * w0, rel_tol=1e-9)
    assert meta["conformal_lambda"] == 2.5


def test_conformal_lambda_fit_is_precut_only():
    # A series whose only volatility is post-cut must not affect the fit:
    # lambda from the calm pre-cut folds stays at the bottom of the grid.
    series = {
        ("x", "muslim"): [
            _pt(1900, 0.50), _pt(1920, 0.50), _pt(1940, 0.50), _pt(1960, 0.50),
            _pt(2000, 0.99),  # post-cut jump
        ]
    }
    lam = fit_conformal_lambda(series, cut_year=1975, policy="persistence")
    assert lam == 1.0


# ---------------------------------------------------------------------------
# claims over series — hygiene invariants
# ---------------------------------------------------------------------------


def test_series_claims_respect_target_exclusions_and_cut():
    pts = [
        _pt(1900, 0.80),
        _pt(1950, 0.85),
        _pt(2005, 0.88, src="arda"),
        _pt(2010, 0.90, src="hand_seed_v0"),  # excluded target source
        _pt(2014, 0.91, src="mccarthy_armenian_pop_ottoman"),  # contested
    ]
    claims = make_series_claims({("egypt", "muslim"): pts}, cut_year=1975, tape="t")
    target_years = {c.year_to for c in claims}
    assert 2005 in target_years
    assert 2010 not in target_years and 2014 not in target_years
    assert all(c.year_to > 1975 for c in claims)


def test_series_claims_abstention_by_train_length():
    pts = [_pt(1950, 0.85), _pt(2010, 0.90)]  # one pre-cut point
    claims = make_series_claims({("x", "muslim"): pts}, cut_year=1975, tape="t")
    pols = {c.meta["policy"] for c in claims}
    assert pols == {"persistence"}  # reversion/ar1 abstain


def test_settlement_and_policy_block_shapes():
    claims = make_series_claims(_series(), cut_year=1975, tape="t")
    store = TrustStore()
    n = settle_band_claims(claims, store)
    assert n == len(claims) > 0
    block = policy_block([c for c in claims if c.meta["policy"] == "persistence"])
    assert set(block) >= {"n", "coverage_observed", "coverage_wilson95", "mean_interval_score"}
    lo, hi = block["coverage_wilson95"]
    assert 0.0 <= lo <= block["coverage_observed"] <= hi <= 1.0


# ---------------------------------------------------------------------------
# E4 — analog candidate
# ---------------------------------------------------------------------------


def test_analog_excludes_own_series_from_neighbors_and_abstains_when_thin():
    # Only one series → no cross-series neighbors → must abstain entirely.
    claims = analog_claims(_series(), cut_year=1975, tape="t")
    assert claims == []


def test_analog_band_is_wellformed_when_neighbors_exist():
    series = {}
    for i in range(12):
        series[(f"p{i}", "muslim")] = [
            _pt(1900, 0.5 + i * 0.01),
            _pt(1930, 0.51 + i * 0.01),
            _pt(1960, 0.52 + i * 0.01),
            _pt(2010, 0.55 + i * 0.01),
        ]
    claims = analog_claims(series, cut_year=1975, min_neighbors=5, tape="t")
    assert claims
    for c in claims:
        assert 0.0 <= c.meta["lo"] <= c.meta["point"] <= c.meta["hi"] <= 1.0
        assert c.meta["n_neighbors"] >= 5
        assert c.year_to > 1975


# ---------------------------------------------------------------------------
# E6 — width shape ablation
# ---------------------------------------------------------------------------


def test_backfill_sqrt_narrower_beyond_a_decade_wider_within():
    dyn = Dynamics(fit_start=1920, n_transitions=50, rate_mean=0.0, rate_std=0.02)
    support = [(1900, 0.7)]
    lin = backfill_series(support, dyn, years=[1905, 1950], width_shape="linear")
    sq = backfill_series(support, dyn, years=[1905, 1950], width_shape="sqrt")
    # gap 5 (< 1 decade): sqrt(0.5) > 0.5 → sqrt wider; gap 50: sqrt(5) < 5 → narrower.
    assert (sq[0].hi - sq[0].lo) > (lin[0].hi - lin[0].lo)
    assert (sq[1].hi - sq[1].lo) < (lin[1].hi - lin[1].lo)


def test_backfill_rejects_unknown_shape():
    dyn = Dynamics(fit_start=1920, n_transitions=50, rate_mean=0.0, rate_std=0.02)
    with pytest.raises(ValueError):
        backfill_series([(1900, 0.7)], dyn, years=[1950], width_shape="cubic")
