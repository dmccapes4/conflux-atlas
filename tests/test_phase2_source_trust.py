"""Phase 2 gate — source-trust corroboration + calibration math.

CONTRACT (rationale in docs/PHASE2_TEST_SPEC.md):

  - "Nobody keeps score on demography" — this is the scorekeeper. A
    source earns trust when a LATER, INDEPENDENT source lands within
    tolerance of its claim for the same polity×group. Keys are
    `source_trust:<source_id>`; posteriors live in the same TrustStore
    as policy trust (one ledger, many hypothesis families).
  - Corroboration is strictly forward-in-time and cross-source: a source
    can never corroborate itself, and a claim settles against the NEXT
    qualifying anchor, not a cherry-picked agreeing one.
  - Calibration: settled claims carry stated_p; `calibration_table` bins
    them and reports observed frequency per bin; `brier_score` ∈ [0, 1].
    Tests pin the math on constructed claims — whether any policy is
    *well-calibrated* on real data is the research result.

SKIPS until conflux/settlement.py exists. Run: `make test-phase2`.
"""

from __future__ import annotations

import pytest

learning = pytest.importorskip(
    "conflux.learning", reason="Phase 2: conflux/learning.py not implemented yet"
)
settlement = pytest.importorskip(
    "conflux.settlement", reason="Phase 2: conflux/settlement.py not implemented yet"
)

pytestmark = pytest.mark.phase2


# ---------------------------------------------------------------------------
# Corroboration claims — source_trust:*
# ---------------------------------------------------------------------------


def _anchor(mk_anchor, pid, year, share, conf, source):
    return mk_anchor(pid, year, {"muslim": share}, confidence=conf, source=source)


def test_corroborated_source_gains_trust(mk_anchor) -> None:
    """Source A says 0.70 in 1950; source B says 0.72 in 1960 (within
    5pp tolerance) → A's claim settles TRUE → source_trust:src_a rises."""
    anchors = [
        _anchor(mk_anchor, "testland", 1950, 0.70, 0.6, "src_a"),
        _anchor(mk_anchor, "testland", 1960, 0.72, 0.8, "src_b"),
    ]
    store = learning.TrustStore()
    claims = settlement.make_corroboration_claims(
        anchors, group="muslim", tolerance_pp=0.05, max_gap_years=25
    )
    n = settlement.settle_corroboration_claims(claims, store)
    assert n == 1
    post = store.get("source_trust:src_a")
    assert post.trials == 1
    assert post.mean > 0.5


def test_contradicted_source_loses_trust(mk_anchor) -> None:
    anchors = [
        _anchor(mk_anchor, "testland", 1950, 0.70, 0.6, "src_a"),
        _anchor(mk_anchor, "testland", 1960, 0.50, 0.8, "src_b"),  # 20pp off
    ]
    store = learning.TrustStore()
    claims = settlement.make_corroboration_claims(
        anchors, group="muslim", tolerance_pp=0.05, max_gap_years=25
    )
    settlement.settle_corroboration_claims(claims, store)
    post = store.get("source_trust:src_a")
    assert post.trials == 1
    assert post.mean < 0.5


def test_no_self_corroboration(mk_anchor) -> None:
    """Two anchors from the same source never settle each other — a source
    agreeing with itself is provenance, not evidence."""
    anchors = [
        _anchor(mk_anchor, "testland", 1950, 0.70, 0.6, "src_a"),
        _anchor(mk_anchor, "testland", 1960, 0.70, 0.6, "src_a"),
    ]
    claims = settlement.make_corroboration_claims(
        anchors, group="muslim", tolerance_pp=0.05, max_gap_years=25
    )
    assert claims == []


def test_corroboration_uses_next_qualifying_anchor_not_best(mk_anchor) -> None:
    """src_a 1950 (0.70) is followed by src_b 1960 (0.50, contradicts) and
    src_c 1970 (0.70, agrees). The claim settles against the NEXT
    qualifying anchor (src_b) → failure. Skipping ahead to the agreeing
    anchor would be settlement shopping."""
    anchors = [
        _anchor(mk_anchor, "testland", 1950, 0.70, 0.6, "src_a"),
        _anchor(mk_anchor, "testland", 1960, 0.50, 0.8, "src_b"),
        _anchor(mk_anchor, "testland", 1970, 0.70, 0.8, "src_c"),
    ]
    store = learning.TrustStore()
    claims = settlement.make_corroboration_claims(
        anchors, group="muslim", tolerance_pp=0.05, max_gap_years=25
    )
    settlement.settle_corroboration_claims(claims, store)
    a_claims = [c for c in claims if c.hypothesis_id == "source_trust:src_a"]
    assert len(a_claims) == 1
    assert a_claims[0].success is False


def test_max_gap_years_prevents_stale_settlement(mk_anchor) -> None:
    """A 1900 claim cannot be settled by a 2020 anchor: over the gap cap
    the world itself moved — disagreement is not evidence of a bad source."""
    anchors = [
        _anchor(mk_anchor, "testland", 1900, 0.70, 0.6, "src_a"),
        _anchor(mk_anchor, "testland", 2020, 0.40, 0.9, "src_b"),
    ]
    claims = settlement.make_corroboration_claims(
        anchors, group="muslim", tolerance_pp=0.05, max_gap_years=25
    )
    assert claims == []


def test_polities_do_not_cross_corroborate(mk_anchor) -> None:
    anchors = [
        _anchor(mk_anchor, "a_land", 1950, 0.70, 0.6, "src_a"),
        _anchor(mk_anchor, "b_land", 1960, 0.70, 0.8, "src_b"),
    ]
    claims = settlement.make_corroboration_claims(
        anchors, group="muslim", tolerance_pp=0.05, max_gap_years=25
    )
    assert claims == []


# ---------------------------------------------------------------------------
# Calibration math
# ---------------------------------------------------------------------------


def _settled_claim(claim_id: str, stated_p: float, success: bool) -> "learning.Claim":
    c = learning.Claim(
        claim_id=claim_id,
        hypothesis_id="policy:test",
        polity_id="testland",
        group="muslim",
        cut_year=1975,
        predicted="up",
        stated_p=stated_p,
        train_n=10,
    )
    c.settled = True
    c.success = success
    return c


def test_calibration_table_well_formed() -> None:
    claims = (
        [_settled_claim(f"hi{i}", 0.9, i < 9) for i in range(10)]     # 90% stated, 90% observed
        + [_settled_claim(f"lo{i}", 0.55, i < 3) for i in range(10)]  # 55% stated, 30% observed
    )
    table = settlement.calibration_table(claims, bins=(0.0, 0.5, 0.6, 0.8, 1.0))
    assert table, "expected non-empty calibration table"
    total = 0
    for row in table:
        assert row.p_lo < row.p_hi
        assert 0.0 <= row.observed <= 1.0
        assert row.p_lo <= row.stated_mean <= row.p_hi
        assert row.n > 0
        total += row.n
    assert total == 20, "every settled claim lands in exactly one bin"

    hi = next(r for r in table if r.p_lo >= 0.8)
    lo = next(r for r in table if r.p_lo == 0.5)
    assert hi.observed == pytest.approx(0.9)
    assert lo.observed == pytest.approx(0.3)


def test_calibration_table_ignores_unsettled() -> None:
    settled = [_settled_claim("s1", 0.7, True)]
    pending = learning.Claim(
        claim_id="p1", hypothesis_id="policy:test", polity_id="x", group="muslim",
        cut_year=1975, predicted="up", stated_p=0.7, train_n=1,
    )
    table = settlement.calibration_table(settled + [pending], bins=(0.0, 1.0))
    assert sum(r.n for r in table) == 1


def test_brier_score_bounds_and_extremes() -> None:
    perfect = [_settled_claim("a", 1.0, True), _settled_claim("b", 1.0, True)]
    worst = [_settled_claim("c", 1.0, False), _settled_claim("d", 1.0, False)]
    coin = [_settled_claim("e", 0.5, True), _settled_claim("f", 0.5, False)]
    assert settlement.brier_score(perfect) == pytest.approx(0.0)
    assert settlement.brier_score(worst) == pytest.approx(1.0)
    assert settlement.brier_score(coin) == pytest.approx(0.25)


def test_trust_report_serializable(tmp_path) -> None:
    """Milestone artifact: JSON with posteriors by family + calibration.
    docs/REPORT_PHASE2_TRUST.md cites this file."""
    import json

    store = learning.TrustStore()
    claims = [_settled_claim(f"c{i}", 0.7, i % 2 == 0) for i in range(6)]
    for c in claims:
        store.record(c)
        store.bump(c.hypothesis_id, bool(c.success))

    out = tmp_path / "trust_report.json"
    settlement.write_trust_report(store, claims, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "posteriors" in data and "calibration" in data and "brier" in data
    assert "policy:test" in data["posteriors"]
    post = data["posteriors"]["policy:test"]
    assert {"alpha", "beta", "trials", "mean"} <= set(post)
    assert 0.0 <= data["brier"] <= 1.0
