"""Phase 3 gate — pre-registered 1975 backtest (`conflux/backtest.py`).

CONTRACT (docs/PHASE3_TEST_SPEC.md §2):

  - PREREGISTRATION values are PINNED here. Changing the protocol means
    changing these tests in the same commit — that visibility IS the
    pre-registration mechanism.
  - Winkler interval score exact arithmetic; lower is better.
  - Targets are realized post-cut anchor years only; contested sources
    (McCarthy) never become validation targets.
  - Claims settle once through TrustStore; report is JSON-serializable
    and never hides a miss.

SKIPS until conflux/backtest.py exists. Run: `make test-phase3`.
"""

from __future__ import annotations

import json

import pytest

backtest = pytest.importorskip(
    "conflux.backtest", reason="Phase 3: conflux/backtest.py not implemented yet"
)

from conflux.learning import TrustStore  # noqa: E402

pytestmark = pytest.mark.phase3


# ---------------------------------------------------------------------------
# Pre-registration — pinned exactly
# ---------------------------------------------------------------------------


def test_preregistration_pinned():
    p = backtest.PREREGISTRATION
    assert p["cut_year"] == 1975
    assert p["coverage"] == 0.80
    assert p["alpha"] == pytest.approx(0.20)
    assert tuple(p["policies"]) == ("persistence", "reversion", "ar1")
    assert p["primary_metric"] == "mean_interval_score"
    assert "mccarthy_armenian_pop_ottoman" in p["contested_validation_excluded"]


def test_preregistration_is_read_only():
    with pytest.raises((TypeError, AttributeError)):
        backtest.PREREGISTRATION["cut_year"] = 1980  # type: ignore[index]


# ---------------------------------------------------------------------------
# Interval score — exact values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "y,lo,hi,expected",
    [
        (0.5, 0.4, 0.6, 0.2),          # inside: width only
        (0.4, 0.4, 0.6, 0.2),          # boundary counts as inside
        (0.6, 0.4, 0.6, 0.2),
        (0.3, 0.4, 0.6, 1.2),          # below: 0.2 + 10*0.1
        (0.7, 0.4, 0.6, 1.2),          # above: 0.2 + 10*0.1
        (0.0, 0.4, 0.6, 0.2 + 10 * 0.4),
    ],
)
def test_interval_score_exact(y, lo, hi, expected):
    assert backtest.interval_score(y, lo, hi, alpha=0.20) == pytest.approx(expected)


def test_interval_score_rewards_honest_narrow_bands():
    # Same hit: narrower band scores better. Same width: hit beats miss.
    assert backtest.interval_score(0.5, 0.45, 0.55) < backtest.interval_score(
        0.5, 0.3, 0.7
    )
    assert backtest.interval_score(0.5, 0.4, 0.6) < backtest.interval_score(
        0.65, 0.4, 0.6
    )


# ---------------------------------------------------------------------------
# Claims — targets, hygiene, contested exclusion
# ---------------------------------------------------------------------------


def _anchors(mk_anchor):
    """Two polities with pre- and post-cut anchors; one contested target."""
    rows = []
    for pid, base in (("egypt", 0.90), ("iraq", 0.95)):
        for year in (1900, 1950, 1970):  # pre-cut train
            rows.append(mk_anchor(pid, year, {"muslim": base}, confidence=0.8))
        for year in (2000, 2010):  # realized post-cut targets
            rows.append(mk_anchor(pid, year, {"muslim": base - 0.01}, confidence=0.8))
    # contested-source anchor lands post-cut: must never become a target
    rows.append(
        mk_anchor(
            "egypt", 1990, {"muslim": 0.5},
            confidence=0.3, source="mccarthy_armenian_pop_ottoman",
        )
    )
    return rows


def test_claims_target_realized_postcut_anchor_years_only(mk_anchor):
    claims = backtest.make_forecast_claims(_anchors(mk_anchor), groups=["muslim"])
    assert claims
    for c in claims:
        assert c.hypothesis_id in {
            "forecast:persistence", "forecast:reversion", "forecast:ar1"
        }
        assert c.cut_year == 1975
        assert c.year_to in {2000, 2010}, "targets must be realized anchor years"
        assert c.year_to != 1990, "contested source must never be a target"
        assert c.stated_p == pytest.approx(0.80)
        m = c.meta
        assert 0.0 <= m["lo"] <= m["point"] <= m["hi"] <= 1.0


def test_settlement_bumps_forecast_posteriors_once(mk_anchor):
    anchors = _anchors(mk_anchor)
    claims = backtest.make_forecast_claims(anchors, groups=["muslim"])
    store = TrustStore()
    n = backtest.settle_forecast_claims(claims, anchors, store)
    assert n == len(claims)
    total_trials = sum(
        store.get(f"forecast:{p}").trials
        for p in ("persistence", "reversion", "ar1")
    )
    assert total_trials == n
    with pytest.raises(ValueError):
        backtest.settle_forecast_claims(claims[:1], anchors, store)  # double settle


def test_success_is_band_membership(mk_anchor):
    anchors = _anchors(mk_anchor)
    claims = backtest.make_forecast_claims(anchors, groups=["muslim"])
    store = TrustStore()
    backtest.settle_forecast_claims(claims, anchors, store)
    for c in claims:
        realized = float(c.meta["realized_share"])
        inside = c.meta["lo"] <= realized <= c.meta["hi"]
        assert c.success is inside


def test_claims_are_shock_taggable(mk_anchor):
    from conflux.connascence import tag_shock_claims
    from conflux.schema import Event

    claims = backtest.make_forecast_claims(_anchors(mk_anchor), groups=["muslim"])
    ev = Event(
        event_id="test_shock", year=2005, title="t",
        source_ids=["test"], confidence=0.8,
    )
    tag_shock_claims(claims, [ev])
    assert all("shock" in c.meta for c in claims)
    assert any(c.meta["shock"] for c in claims if c.year_to == 2010)


# ---------------------------------------------------------------------------
# Report — serializable, honest about misses
# ---------------------------------------------------------------------------


def test_backtest_report_shape_and_serializability(mk_anchor):
    anchors = _anchors(mk_anchor)
    claims = backtest.make_forecast_claims(anchors, groups=["muslim"])
    store = TrustStore()
    backtest.settle_forecast_claims(claims, anchors, store)
    report = backtest.backtest_report(claims)
    json.dumps(report)  # must not raise
    assert report["preregistration"]["cut_year"] == 1975
    for policy in ("persistence", "reversion", "ar1"):
        row = report["policies"][policy]
        assert row["n"] >= 0
        if row["n"]:
            assert 0.0 <= row["coverage_observed"] <= 1.0
            assert row["mean_interval_score"] >= 0.0
            assert row["mean_width"] >= 0.0
    assert "verdict" in report
    assert report["verdict"]["candidate"] is None  # baselines only, no winner claim


def test_report_never_hides_a_miss(mk_anchor):
    """A tape where every band misses must still produce a valid report."""
    anchors = _anchors(mk_anchor)
    claims = backtest.make_forecast_claims(anchors, groups=["muslim"])
    for c in claims:  # force universal miss
        c.meta["lo"], c.meta["hi"] = 0.0, 0.001
        c.meta["point"] = 0.0005
    store = TrustStore()
    backtest.settle_forecast_claims(claims, anchors, store)
    report = backtest.backtest_report(claims)
    for policy in ("persistence", "reversion", "ar1"):
        row = report["policies"][policy]
        if row["n"]:
            assert row["coverage_observed"] == 0.0
