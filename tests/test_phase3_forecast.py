"""Phase 3 gate — banded share forecasts (`conflux/forecast.py`).

CONTRACT (docs/PHASE3_TEST_SPEC.md §1):

  - `BandForecast` invariants: 0 <= lo <= point <= hi <= 1, target after
    cut, coverage in (0,1).
  - Temporal hygiene: post-cut points must not influence output at all.
  - Abstention by train length (persistence>=1, reversion>=2, ar1>=3).
  - Monotone band widening with horizon; determinism; [0,1] clipping.

These tests SKIP until conflux/forecast.py exists. Run: `make test-phase3`.
"""

from __future__ import annotations

import pytest

forecast = pytest.importorskip(
    "conflux.forecast", reason="Phase 3: conflux/forecast.py not implemented yet"
)

pytestmark = pytest.mark.phase3


# A dense synthetic series: linear decline 0.30 → 0.14 over 1900–1980,
# then post-cut points that MUST NOT matter.
LINEAR = [(1900 + 10 * i, 0.30 - 0.02 * i) for i in range(9)]  # …1980
FLAT = [(1900 + 10 * i, 0.25) for i in range(9)]


def _mk(points, policy, cut=1975, targets=(1980, 1990, 2000), coverage=0.80):
    return forecast.forecast_series(
        points, cut_year=cut, target_years=list(targets), policy=policy,
        coverage=coverage,
    )


# ---------------------------------------------------------------------------
# BandForecast invariants
# ---------------------------------------------------------------------------


def test_band_forecast_invariants_enforced():
    with pytest.raises(ValueError):
        forecast.BandForecast(
            polity_id="x", group="muslim", cut_year=1975, target_year=1980,
            point=0.5, lo=0.6, hi=0.7, coverage=0.8, policy="persistence",
            train_n=3,
        )  # lo > point
    with pytest.raises(ValueError):
        forecast.BandForecast(
            polity_id="x", group="muslim", cut_year=1975, target_year=1970,
            point=0.5, lo=0.4, hi=0.6, coverage=0.8, policy="persistence",
            train_n=3,
        )  # target before cut
    with pytest.raises(ValueError):
        forecast.BandForecast(
            polity_id="x", group="muslim", cut_year=1975, target_year=1980,
            point=0.5, lo=0.4, hi=0.6, coverage=1.0, policy="persistence",
            train_n=3,
        )  # coverage not in (0,1)


@pytest.mark.parametrize("policy", ["persistence", "reversion", "ar1"])
def test_forecasts_well_formed_and_deterministic(policy):
    out1 = _mk(LINEAR, policy)
    out2 = _mk(LINEAR, policy)
    assert out1, f"{policy} should forecast on a 7-point train series"
    assert len(out1) == len(out2)
    for f1, f2 in zip(out1, out2):
        assert (f1.point, f1.lo, f1.hi, f1.target_year) == (
            f2.point, f2.lo, f2.hi, f2.target_year
        )
        assert 0.0 <= f1.lo <= f1.point <= f1.hi <= 1.0
        assert f1.cut_year == 1975
        assert f1.policy == policy


# ---------------------------------------------------------------------------
# Temporal hygiene — the load-bearing rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", ["persistence", "reversion", "ar1"])
def test_post_cut_points_never_influence_output(policy):
    tampered = [(y, s) for y, s in LINEAR if y <= 1975] + [(1980, 0.99)]
    clean = [(y, s) for y, s in LINEAR if y <= 1975]
    out_t = _mk(tampered, policy)
    out_c = _mk(clean, policy)
    assert [(f.point, f.lo, f.hi) for f in out_t] == [
        (f.point, f.lo, f.hi) for f in out_c
    ]


# ---------------------------------------------------------------------------
# Point semantics per policy
# ---------------------------------------------------------------------------


def test_persistence_point_is_last_train_share():
    out = _mk(LINEAR, "persistence")
    last_train = max((y, s) for y, s in LINEAR if y <= 1975)[1]
    for f in out:
        assert f.point == pytest.approx(last_train)


def test_reversion_point_between_last_and_mean():
    out = _mk(LINEAR, "reversion")
    train = [s for y, s in LINEAR if y <= 1975]
    last, mean = train[-1], sum(train) / len(train)
    lo_b, hi_b = min(last, mean), max(last, mean)
    for f in out:
        assert lo_b - 1e-9 <= f.point <= hi_b + 1e-9


def test_ar1_continues_a_linear_trend():
    out = _mk(LINEAR, "ar1", targets=(1980,))
    assert len(out) == 1
    # train ends 1970 at 0.16 with -0.02/decade → 1980 ≈ 0.14
    assert out[0].point == pytest.approx(0.14, abs=0.005)


# ---------------------------------------------------------------------------
# Abstention thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "policy,min_points",
    [("persistence", 1), ("reversion", 2), ("ar1", 3)],
)
def test_abstention_below_min_train_points(policy, min_points):
    just_enough = LINEAR[:min_points]
    too_few = LINEAR[: min_points - 1]
    assert _mk(just_enough, policy, cut=1975, targets=(1990,)) != []
    assert _mk(too_few, policy, cut=1975, targets=(1990,)) == []


# ---------------------------------------------------------------------------
# Bands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", ["persistence", "reversion", "ar1"])
def test_band_width_monotone_in_horizon(policy):
    out = _mk(LINEAR, policy, targets=(1980, 1990, 2000, 2010))
    widths = [f.hi - f.lo for f in sorted(out, key=lambda f: f.target_year)]
    assert all(w2 >= w1 - 1e-12 for w1, w2 in zip(widths, widths[1:]))


@pytest.mark.parametrize("policy", ["persistence", "reversion", "ar1"])
def test_band_positive_width_when_train_varies(policy):
    out = _mk(LINEAR, policy)
    assert all(f.hi - f.lo > 0 for f in out)


def test_bands_clipped_to_unit_interval():
    near_zero = [(1900 + 10 * i, 0.01) for i in range(9)]
    near_one = [(1900 + 10 * i, 0.99) for i in range(9)]
    for pts in (near_zero, near_one):
        for policy in ("persistence", "reversion", "ar1"):
            for f in _mk(pts, policy, targets=(2000,)):
                assert 0.0 <= f.lo and f.hi <= 1.0


def test_flat_series_stays_well_formed():
    for policy in ("persistence", "reversion", "ar1"):
        for f in _mk(FLAT, policy):
            assert 0.0 <= f.lo <= f.point <= f.hi <= 1.0
