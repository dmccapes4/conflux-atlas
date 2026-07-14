"""Phase 1 gate — movement primitives (`conflux/movement.py`).

CONTRACT (see docs/PHASE1_TEST_SPEC.md for rationale and thresholds):

  - Bin functions are *total* (every float maps to exactly one bin) and
    operate on RATE PER DECADE, never raw inter-anchor deltas, so a
    1900→1950 gap and a 2010→2020 gap are comparable.
  - `movement_events()` emits inter-anchor transitions only. It must NOT
    interpolate annual values (Phase 0 critique: sparse anchors must not
    pretend to be annual series). Every event carries its gap.
  - Derived confidence uses the weakest-link rule: min(conf_from, conf_to).
  - `place_hash` is deterministic and formatted "level|delta|gap|vol".

These tests SKIP until conflux/movement.py exists; then they become part
of the default gate automatically. Run just this phase: `make test-phase1`.
"""

from __future__ import annotations

import pytest

movement = pytest.importorskip(
    "conflux.movement", reason="Phase 1: conflux/movement.py not implemented yet"
)

pytestmark = pytest.mark.phase1


# ---------------------------------------------------------------------------
# Bins — exact thresholds from the spec. If you change a threshold, change
# the spec and these tests in the same commit (they are the contract).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rate,expected",
    [
        (-0.20, "big_down"),
        (-0.05, "big_down"),   # boundary: |r| >= 0.05 is "big"
        (-0.02, "down"),
        (-0.005, "down"),      # boundary: |r| >= 0.005 leaves "flat"
        (-0.004, "flat"),
        (0.0, "flat"),
        (0.004, "flat"),
        (0.005, "up"),
        (0.02, "up"),
        (0.05, "big_up"),
        (0.20, "big_up"),
    ],
)
def test_delta_bin_thresholds(rate: float, expected: str) -> None:
    """rate = Δshare per decade (share points / 10y)."""
    assert movement.delta_bin(rate) == expected


@pytest.mark.parametrize(
    "years,expected",
    [
        (1, "close"),
        (5, "close"),
        (6, "decade"),
        (15, "decade"),
        (16, "generation"),
        (35, "generation"),
        (36, "era"),
        (100, "era"),
    ],
)
def test_gap_bin_thresholds(years: float, expected: str) -> None:
    """gap_bin describes anchor spacing (data density), not dynamics."""
    assert movement.gap_bin(years) == expected


@pytest.mark.parametrize(
    "share,expected",
    [
        (0.0, "trace"),
        (0.009, "trace"),
        (0.01, "minority"),
        (0.09, "minority"),
        (0.10, "significant"),
        (0.34, "significant"),
        (0.35, "plural"),
        (0.64, "plural"),
        (0.65, "majority"),
        (0.89, "majority"),
        (0.90, "dominant"),
        (1.0, "dominant"),
    ],
)
def test_level_bin_thresholds(share: float, expected: str) -> None:
    assert movement.level_bin(share) == expected


@pytest.mark.parametrize(
    "vol,expected",
    [
        (None, "na"),        # < 2 prior transitions → volatility undefined
        (0.0, "calm"),
        (0.004, "calm"),
        (0.005, "drift"),
        (0.029, "drift"),
        (0.03, "turbulent"),
        (0.5, "turbulent"),
    ],
)
def test_vol_bin_thresholds(vol: float | None, expected: str) -> None:
    """vol = mean |rate per decade| over PRIOR transitions only (causal)."""
    assert movement.vol_bin(vol) == expected


def test_bins_are_total_functions() -> None:
    """No float may fall through to an exception or None."""
    for x in (-1e9, -1.0, -1e-12, 0.0, 1e-12, 1.0, 1e9):
        assert isinstance(movement.delta_bin(x), str)
        assert isinstance(movement.vol_bin(abs(x)), str)
    for x in (0.0, 1e-12, 0.5, 1.0):
        assert isinstance(movement.level_bin(x), str)
    for x in (0.0, 0.5, 1.0, 500.0):
        assert isinstance(movement.gap_bin(x), str)


# ---------------------------------------------------------------------------
# place_hash
# ---------------------------------------------------------------------------


def test_place_hash_format_and_determinism() -> None:
    h1 = movement.place_hash(level="majority", delta="down", gap="era", vol="na")
    h2 = movement.place_hash(level="majority", delta="down", gap="era", vol="na")
    assert h1 == h2 == "majority|down|era|na"


def test_place_hash_excludes_identity() -> None:
    """The hash describes a PLACE, not a polity/group — identity lives in
    catalog metadata so retrieval can find cross-polity analogies."""
    import inspect

    params = inspect.signature(movement.place_hash).parameters
    assert "polity_id" not in params
    assert "group" not in params


# ---------------------------------------------------------------------------
# movement_events — inter-anchor transitions
# ---------------------------------------------------------------------------


def test_movement_events_basic_transition(mk_anchor) -> None:
    anchors = [
        mk_anchor("testland", 1900, {"muslim": 0.80, "christian": 0.20}, confidence=0.4),
        mk_anchor("testland", 1950, {"muslim": 0.90, "christian": 0.10}, confidence=0.6),
    ]
    events = movement.movement_events(anchors, group="muslim")
    assert len(events) == 1
    ev = events[0]
    assert ev.polity_id == "testland"
    assert ev.group == "muslim"
    assert ev.year_from == 1900 and ev.year_to == 1950
    assert ev.gap_years == 50
    assert ev.share_from == pytest.approx(0.80)
    assert ev.share_to == pytest.approx(0.90)
    assert ev.delta == pytest.approx(0.10)
    # rate is normalized per decade: 0.10 over 50y = 0.02/decade
    assert ev.rate_per_decade == pytest.approx(0.02)
    # weakest-link confidence
    assert ev.confidence == pytest.approx(0.4)


def test_movement_events_no_interpolation(mk_anchor) -> None:
    """Two anchors yield exactly ONE event — never 49 fabricated annual steps."""
    anchors = [
        mk_anchor("testland", 1900, {"muslim": 0.80}),
        mk_anchor("testland", 1950, {"muslim": 0.90}),
        mk_anchor("testland", 2000, {"muslim": 0.95}),
    ]
    events = movement.movement_events(anchors, group="muslim")
    assert len(events) == 2
    assert [(e.year_from, e.year_to) for e in events] == [(1900, 1950), (1950, 2000)]


def test_movement_events_sorted_and_multi_polity(mk_anchor) -> None:
    """Input order must not matter; polities must not cross-contaminate."""
    anchors = [
        mk_anchor("b_land", 2000, {"muslim": 0.5}),
        mk_anchor("a_land", 1950, {"muslim": 0.7}),
        mk_anchor("b_land", 1950, {"muslim": 0.6}),
        mk_anchor("a_land", 2000, {"muslim": 0.6}),
    ]
    events = movement.movement_events(anchors, group="muslim")
    assert len(events) == 2
    by_polity = {e.polity_id: e for e in events}
    assert by_polity["a_land"].delta == pytest.approx(-0.1)
    assert by_polity["b_land"].delta == pytest.approx(-0.1)
    # no transition may span two polities
    for e in events:
        assert e.year_from < e.year_to


def test_movement_events_missing_group_is_zero_share(mk_anchor) -> None:
    """A religion absent from `shares` means share 0.0, not a crash —
    minorities appearing/vanishing IS movement we care about."""
    anchors = [
        mk_anchor("testland", 1950, {"muslim": 0.98, "jewish": 0.02}),
        mk_anchor("testland", 2000, {"muslim": 1.0}),
    ]
    events = movement.movement_events(anchors, group="jewish")
    assert len(events) == 1
    assert events[0].share_from == pytest.approx(0.02)
    assert events[0].share_to == pytest.approx(0.0)
    assert events[0].delta == pytest.approx(-0.02)


def test_movement_events_same_year_dedupe(mk_anchor) -> None:
    """Two anchors in the same polity-year: keep the higher-confidence one
    (spec §2.3) — never emit a zero-gap transition (division by zero)."""
    anchors = [
        mk_anchor("testland", 2010, {"muslim": 0.90}, confidence=0.5),
        mk_anchor("testland", 2010, {"muslim": 0.85}, confidence=0.9),
        mk_anchor("testland", 2020, {"muslim": 0.80}, confidence=0.9),
    ]
    events = movement.movement_events(anchors, group="muslim")
    assert len(events) == 1
    assert events[0].share_from == pytest.approx(0.85)  # higher-conf 2010 row won
    assert events[0].gap_years == 10


def test_movement_event_carries_origin_place_hash(mk_anchor) -> None:
    """Each event is stamped with the hash of its ORIGIN place — the place
    you were in when the move began. This is what the Phase 1 scorecard
    conditions on (predict transition direction from origin place)."""
    anchors = [
        mk_anchor("testland", 1900, {"muslim": 0.80}),
        mk_anchor("testland", 1950, {"muslim": 0.90}),
    ]
    ev = movement.movement_events(anchors, group="muslim")[0]
    # level of origin share (0.80 → majority); first transition has no prior
    # delta/vol history → prev-delta "na" is not part of the hash; vol is "na".
    assert ev.origin_hash == movement.place_hash(
        level="majority",
        delta=movement.delta_bin(ev.rate_per_decade),
        gap=movement.gap_bin(ev.gap_years),
        vol="na",
    )


def test_direction_labels(mk_anchor) -> None:
    """Outcome direction uses the same flat threshold as delta_bin."""
    assert movement.direction(0.004) == "flat"
    assert movement.direction(0.005) == "up"
    assert movement.direction(-0.005) == "down"
