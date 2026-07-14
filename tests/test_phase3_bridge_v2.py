"""Bridge v2 contracts — nugget floor + shock-aware widening.

The Phase 3 anchor-drop curves inverted the expected calibration-vs-sparsity
relationship: under-coverage at short gaps (definitional noise priced at
zero), honest coverage at long gaps. v2 adds an additive measurement-noise
nugget and shock-window sigma widening; defaults must preserve the Phase 3
contract behavior exactly.
"""

from __future__ import annotations

import pytest

bridge = pytest.importorskip("conflux.bridge")

from conflux.bridge import (  # noqa: E402
    Dynamics,
    backfill_series,
    estimate_nugget,
    shock_windows_for_polity,
)
from conflux.observations import ShareObservation  # noqa: E402
from conflux.schema import Event, MigrationEdge  # noqa: E402

pytestmark = pytest.mark.phase3

DYN = Dynamics(fit_start=1920, n_transitions=50, rate_mean=0.0, rate_std=0.02)
SUPPORT = [(1900, 0.70), (1960, 0.75)]


def _obs(src, pid, year, share, group="muslim"):
    return ShareObservation(
        obs_id=f"{src}|{pid}|{group}|{year}",
        polity_id=pid,
        group=group,
        year=year,
        share=share,
        confidence=0.7,
        source_id=src,
    )


# ---------------------------------------------------------------------------
# nugget — defaults preserved, floor applied off-anchor only
# ---------------------------------------------------------------------------


def test_nugget_zero_is_identical_to_phase3_behavior():
    a = backfill_series(SUPPORT, DYN, years=[1900, 1905, 1930])
    b = backfill_series(SUPPORT, DYN, years=[1900, 1905, 1930], nugget=0.0)
    for ea, eb in zip(a, b):
        assert (ea.point, ea.lo, ea.hi) == (eb.point, eb.lo, eb.hi)


def test_nugget_floors_short_gap_width_but_leaves_anchor_exact():
    out = backfill_series(SUPPORT, DYN, years=[1900, 1902], nugget=0.03)
    by_year = {e.year: e for e in out}
    # Anchor year stays exact (anchors dominate — Phase 3 contract).
    assert by_year[1900].hi - by_year[1900].lo == 0.0
    # 2y gap: gap term alone would be z*0.02*0.2 ≈ 0.005 half-width;
    # the nugget floor must dominate (z*0.03 ≈ 0.038 half-width).
    w = by_year[1902].hi - by_year[1902].lo
    assert w > 2 * 1.28 * 0.03 * 0.99


def test_nugget_widths_still_monotone_in_gap():
    out = backfill_series(SUPPORT, DYN, years=[1902, 1910, 1930], nugget=0.03)
    out = sorted(out, key=lambda e: e.nearest_anchor_gap)
    widths = [e.hi - e.lo for e in out]
    assert all(b >= a - 1e-12 for a, b in zip(widths, widths[1:]))


def test_nugget_negligible_at_long_gaps():
    """At 50y the gap term dominates; the nugget must not blow up the band."""
    plain = backfill_series([(1900, 0.7)], DYN, years=[1950])[0]
    floored = backfill_series([(1900, 0.7)], DYN, years=[1950], nugget=0.03)[0]
    w0, w1 = plain.hi - plain.lo, floored.hi - floored.lo
    assert w1 >= w0
    assert w1 <= w0 * 1.25  # quadrature, not addition


# ---------------------------------------------------------------------------
# estimate_nugget — recovery, independence, fallback
# ---------------------------------------------------------------------------


def test_estimate_nugget_recovers_known_spread():
    # Two sources disagreeing by exactly ±0.02 around truth → d = ±0.04-ish;
    # build symmetric pairs with sd(d) = 0.04 → nugget ≈ 0.04/√2 ≈ 0.028.
    obs = []
    for i, pid in enumerate([f"p{k}" for k in range(30)]):
        d = 0.04 if i % 2 == 0 else -0.04
        obs.append(_obs("src_a", pid, 2010, 0.50 + d / 2))
        obs.append(_obs("src_b", pid, 2010, 0.50 - d / 2))
    res = estimate_nugget(obs, groups=("muslim",))
    assert res["n_pairs"]["muslim"] == 30
    assert res["per_group"]["muslim"] == pytest.approx(0.04 / 2**0.5, rel=0.05)


def test_estimate_nugget_ignores_same_source_and_far_years():
    obs = [
        _obs("src_a", "x", 2010, 0.50),
        _obs("src_a", "x", 2011, 0.90),  # same source — not a pair
        _obs("src_b", "x", 2020, 0.10),  # 10y away — outside tolerance
    ]
    res = estimate_nugget(obs, groups=("muslim",))
    assert res["n_pairs"]["muslim"] == 0


def test_estimate_nugget_group_fallback_to_pooled():
    obs = []
    for i, pid in enumerate([f"p{k}" for k in range(20)]):
        d = 0.02 if i % 2 == 0 else -0.02
        obs.append(_obs("src_a", pid, 2010, 0.5 + d, group="muslim"))
        obs.append(_obs("src_b", pid, 2010, 0.5 - d, group="muslim"))
    # jewish has 1 pair — below min_pairs → pooled fallback
    obs.append(_obs("src_a", "il", 2010, 0.75, group="jewish"))
    obs.append(_obs("src_b", "il", 2010, 0.74, group="jewish"))
    res = estimate_nugget(obs, groups=("muslim", "jewish"), min_pairs=10)
    assert res["per_group"]["jewish"] == res["pooled"]
    assert res["per_group"]["muslim"] > 0


# ---------------------------------------------------------------------------
# shock widening
# ---------------------------------------------------------------------------


def test_shock_window_widens_overlapping_span_only():
    plain = backfill_series([(1900, 0.7)], DYN, years=[1915, 1950])
    shocked = backfill_series(
        [(1900, 0.7)], DYN, years=[1915, 1950],
        shock_windows=[(1912, 1923)], shock_sigma_multiplier=2.0,
    )
    # 1900→1915 span overlaps 1912–1923 → wider; 1900→1950 also overlaps.
    assert (shocked[0].hi - shocked[0].lo) > (plain[0].hi - plain[0].lo)
    # Non-overlapping window leaves widths untouched.
    calm = backfill_series(
        [(1900, 0.7)], DYN, years=[1905], shock_windows=[(1950, 1960)]
    )[0]
    ref = backfill_series([(1900, 0.7)], DYN, years=[1905])[0]
    assert calm.hi - calm.lo == pytest.approx(ref.hi - ref.lo)


def test_shock_windows_for_polity_contact_rule():
    ev = Event(
        event_id="lausanne_population_exchange_1923",
        year=1923,
        year_end=1924,
        title="Lausanne exchange",
        affected_polities=["turkey", "greece"],
        source_ids=["seed"],
        confidence=0.9,
    )
    edge = MigrationEdge(
        edge_id="e1",
        year_start=1923,
        year_end=1924,
        from_polity="turkey",
        to_polity="greece",
        group="christian",
        volume_est=1_200_000,
        kind="expulsion_or_flight",
        trigger_event_id="lausanne_population_exchange_1923",
        confidence=0.9,
        source_ids=["seed"],
    )
    assert shock_windows_for_polity("turkey", [ev]) == [(1923, 1924)]
    assert shock_windows_for_polity("egypt", [ev]) == []
    # Contact via triggered edge even without affected_polities membership.
    ev2 = ev.model_copy(update={"affected_polities": []})
    assert shock_windows_for_polity("greece", [ev2], [edge]) == [(1923, 1924)]
