"""Phase 3 gate — sparsity→simulation bridge (`conflux/bridge.py`).

CONTRACT (docs/PHASE3_TEST_SPEC.md §3, STRATEGY_V0.2 §4):

  - Dynamics fit ONLY on transitions with year_from >= fit_start (1920);
    pre-1920 data must not influence the fit.
  - Backfill: anchors dominate (exact at anchor years, narrowest bands);
    bands widen with distance from the nearest anchor; all in [0,1].
  - Settlement: holdout hits/misses bump `dynamics:*` — and contested
    sources (McCarthy) are never settled as validation targets.

SKIPS until conflux/bridge.py exists. Run: `make test-phase3`.
"""

from __future__ import annotations

import pytest

bridge = pytest.importorskip(
    "conflux.bridge", reason="Phase 3: conflux/bridge.py not implemented yet"
)

from conflux.learning import TrustStore  # noqa: E402

pytestmark = pytest.mark.phase3


def _dense_anchors(mk_anchor, pid="egypt", n=12):
    """Dense modern window 1920–2030: enough transitions to fit on."""
    rows = []
    for i in range(n):
        rows.append(
            mk_anchor(pid, 1920 + 10 * i, {"muslim": 0.90 - 0.005 * i}, confidence=0.8)
        )
    return rows


# ---------------------------------------------------------------------------
# fit_dynamics — window discipline
# ---------------------------------------------------------------------------


def test_fit_uses_only_modern_window(mk_anchor):
    modern = _dense_anchors(mk_anchor)
    with_old = modern + [
        mk_anchor("egypt", 1850, {"muslim": 0.10}, confidence=0.4),
        mk_anchor("egypt", 1880, {"muslim": 0.95}, confidence=0.4),
    ]
    d1 = bridge.fit_dynamics(modern, groups=["muslim"])
    d2 = bridge.fit_dynamics(with_old, groups=["muslim"])
    assert d1.fit_start == d2.fit_start == 1920
    assert d1.n_transitions == d2.n_transitions, (
        "pre-1920 anchors must not add transitions to the fit"
    )


def test_fit_raises_on_unusable_input(mk_anchor):
    sparse = [mk_anchor("egypt", 1950, {"muslim": 0.9}), mk_anchor("egypt", 2000, {"muslim": 0.9})]
    with pytest.raises(ValueError):
        bridge.fit_dynamics(sparse, groups=["muslim"])


# ---------------------------------------------------------------------------
# backfill_series — anchors dominate, bands widen
# ---------------------------------------------------------------------------


@pytest.fixture
def fitted(mk_anchor):
    return bridge.fit_dynamics(_dense_anchors(mk_anchor), groups=["muslim"])


ANCHOR_POINTS = [(1850, 0.80), (1920, 0.90)]


def test_backfill_well_formed_and_deterministic(fitted):
    years = [1850, 1860, 1880, 1900, 1920]
    out1 = bridge.backfill_series(ANCHOR_POINTS, fitted, years=years)
    out2 = bridge.backfill_series(ANCHOR_POINTS, fitted, years=years)
    assert [e.year for e in out1] == years
    for e1, e2 in zip(out1, out2):
        assert (e1.point, e1.lo, e1.hi) == (e2.point, e2.lo, e2.hi)
        assert 0.0 <= e1.lo <= e1.point <= e1.hi <= 1.0
        assert e1.coverage == pytest.approx(0.80)


def test_anchors_dominate(fitted):
    out = bridge.backfill_series(
        ANCHOR_POINTS, fitted, years=[1850, 1880, 1920]
    )
    by_year = {e.year: e for e in out}
    assert by_year[1850].point == pytest.approx(0.80)
    assert by_year[1920].point == pytest.approx(0.90)
    anchor_width = by_year[1850].hi - by_year[1850].lo
    mid_width = by_year[1880].hi - by_year[1880].lo
    assert anchor_width <= mid_width, "anchor-year band must be the narrowest"


def test_bands_widen_with_anchor_distance(fitted):
    out = bridge.backfill_series(
        ANCHOR_POINTS, fitted, years=[1860, 1870, 1880]
    )
    out = sorted(out, key=lambda e: e.nearest_anchor_gap)
    widths = [e.hi - e.lo for e in out]
    gaps = [e.nearest_anchor_gap for e in out]
    assert gaps == sorted(gaps)
    assert all(w2 >= w1 - 1e-12 for w1, w2 in zip(widths, widths[1:]))


# ---------------------------------------------------------------------------
# settle_backfill — holdouts, contested exclusion
# ---------------------------------------------------------------------------


def test_settlement_bumps_dynamics_posterior(fitted, mk_anchor):
    estimates = bridge.backfill_series(ANCHOR_POINTS, fitted, years=[1880, 1900])
    holdout = [
        mk_anchor("egypt", 1880, {"muslim": 0.85}, confidence=0.6,
                  source="ottoman_demographics_wiki"),
        mk_anchor("egypt", 1900, {"muslim": 0.87}, confidence=0.6,
                  source="karpat_ottoman_population_1830_1914"),
    ]
    store = TrustStore()
    result = bridge.settle_backfill(estimates, holdout, store)
    assert result["n_settled"] == 2
    assert 0 <= result["n_hits"] <= 2
    post = store.get("dynamics:modern_fit")
    assert post.trials == 2


def test_contested_sources_never_settle(fitted, mk_anchor):
    estimates = bridge.backfill_series(ANCHOR_POINTS, fitted, years=[1880])
    contested = [
        mk_anchor("egypt", 1880, {"muslim": 0.85}, confidence=0.3,
                  source="mccarthy_armenian_pop_ottoman"),
    ]
    store = TrustStore()
    result = bridge.settle_backfill(estimates, contested, store)
    assert result["n_settled"] == 0
    assert result["n_excluded_contested"] == 1
    assert store.get("dynamics:modern_fit").trials == 0
    assert store.ledger == []


def test_calibration_reuses_settlement_table(fitted, mk_anchor):
    """Bridge claims flow through the shared calibration machinery."""
    from conflux.settlement import calibration_table

    estimates = bridge.backfill_series(ANCHOR_POINTS, fitted, years=[1880, 1900])
    holdout = [
        mk_anchor("egypt", 1880, {"muslim": 0.85}, confidence=0.6,
                  source="ottoman_demographics_wiki"),
        mk_anchor("egypt", 1900, {"muslim": 0.87}, confidence=0.6,
                  source="karpat_ottoman_population_1830_1914"),
    ]
    store = TrustStore()
    bridge.settle_backfill(estimates, holdout, store)
    rows = calibration_table(store.ledger, bins=(0.0, 0.5, 0.9, 1.0))
    assert rows, "settled bridge claims must be bin-able"
