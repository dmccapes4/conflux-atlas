"""Phase 2.5 — multi-source observation desk + level-scaled tolerance.

Unlike the phase1/phase2 contract files these test IMPLEMENTED code
(`conflux/observations.py`) and run in the default gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conflux import observations as obs_mod
from conflux.learning import TrustStore
from conflux.observations import (
    ShareObservation,
    level_tolerance,
    load_observation_desk,
    make_observation_claims,
    observations_from_share_records,
    observations_from_wjp,
)
from conflux.settlement import settle_corroboration_claims

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


# ---------------------------------------------------------------------------
# level_tolerance — the trace-share fix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "share,tol",
    [
        (0.005, 0.005),  # trace → ±0.5pp
        (0.05, 0.01),    # minority → ±1pp
        (0.20, 0.03),    # significant → ±3pp
        (0.50, 0.05),    # plural → ±5pp
        (0.95, 0.05),    # dominant → ±5pp
    ],
)
def test_level_tolerance_scales_with_share(share: float, tol: float) -> None:
    assert level_tolerance(share) == pytest.approx(tol)


def test_trace_shares_no_longer_free_successes() -> None:
    """0.2% vs 4% jewish shares 'agreed' under flat ±5pp — the exact
    inflation that made hand_seed look brilliant. Level tolerance
    (±0.5pp at trace) must fail that pair."""
    assert abs(0.002 - 0.04) <= 0.05          # old flat rule: free success
    assert abs(0.002 - 0.04) > level_tolerance(0.002)  # new rule: fails


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def test_excluded_sources_dropped() -> None:
    recs = [
        {
            "polity_id": "egypt", "year": 2000, "confidence": 0.5,
            "shares": {"muslim": 0.9, "christian": 0.1},
            "source_ids": ["hand_seed_v0"],
        },
        {
            "polity_id": "egypt", "year": 2010, "confidence": 0.9,
            "shares": {"muslim": 0.9, "christian": 0.1},
            "source_ids": ["pew_global_religious_composition_2010_2020"],
        },
    ]
    out = observations_from_share_records(recs)
    assert {o.source_id for o in out} == {"pew_global_religious_composition_2010_2020"}


def test_min_share_floor_drops_unreported_groups() -> None:
    recs = [{
        "polity_id": "egypt", "year": 2010, "confidence": 0.9,
        "shares": {"muslim": 0.999, "jewish": 0.0001},
        "source_ids": ["pew"],
    }]
    out = observations_from_share_records(recs)
    assert {o.group for o in out} == {"muslim"}, (
        "near-zero shares are 'not reported', never corroboration fodder"
    )


def test_wjp_share_computed_from_cjp_over_total() -> None:
    recs = [{
        "polity_id": "israel", "year": 1970, "confidence": 0.6,
        "core_jewish_population": 2_582_000, "total_population": 2_958_000,
        "source_ids": ["jewishdatabank_world_jewish_population"],
    }]
    out = observations_from_wjp(recs)
    assert len(out) == 1
    assert out[0].group == "jewish"
    assert out[0].share == pytest.approx(2_582_000 / 2_958_000)


# ---------------------------------------------------------------------------
# Corroboration over observations
# ---------------------------------------------------------------------------


def _obs(src: str, pid: str, year: int, share: float, conf: float = 0.6) -> ShareObservation:
    return ShareObservation(
        obs_id=f"{src}|{pid}|muslim|{year}",
        polity_id=pid, group="muslim", year=year,
        share=share, confidence=conf, source_id=src,
    )


def test_same_year_cross_source_settles() -> None:
    """Two sources measuring the same polity-year is the cleanest possible
    corroboration (zero world movement between measurements)."""
    claims = make_observation_claims(
        [_obs("src_a", "egypt", 2010, 0.90), _obs("src_b", "egypt", 2010, 0.91)]
    )
    assert len(claims) == 1
    assert claims[0].hypothesis_id == "source_trust:src_a"


def test_no_self_corroboration_and_gap_cap() -> None:
    claims = make_observation_claims(
        [
            _obs("src_a", "egypt", 1950, 0.90),
            _obs("src_a", "egypt", 1960, 0.90),   # same source — skip
            _obs("src_b", "egypt", 2020, 0.90),   # 70y gap — beyond cap
        ],
        max_gap_years=30,
    )
    assert claims == []


def test_tolerance_stored_per_level_and_settles_correctly() -> None:
    """A 2pp disagreement passes at plural level, fails at minority level."""
    store = TrustStore()
    claims = make_observation_claims(
        [
            _obs("src_a", "egypt", 2010, 0.50),   # plural: tol 5pp
            _obs("src_b", "egypt", 2011, 0.52),
            _obs("src_c", "iraq", 2010, 0.05),    # minority: tol 1pp
            _obs("src_d", "iraq", 2011, 0.07),
        ]
    )
    settle_corroboration_claims(claims, store)
    by_hyp = {c.hypothesis_id: c for c in claims}
    assert by_hyp["source_trust:src_a"].success is True
    assert by_hyp["source_trust:src_c"].success is False
    assert by_hyp["source_trust:src_a"].meta["tolerance_pp"] == pytest.approx(0.05)
    assert by_hyp["source_trust:src_c"].meta["tolerance_pp"] == pytest.approx(0.01)


def test_claim_ids_deterministic_and_unique() -> None:
    rows = [
        _obs("src_a", "egypt", 2010, 0.50),
        _obs("src_b", "egypt", 2011, 0.52),
        _obs("src_a", "iraq", 2010, 0.60),
        _obs("src_b", "iraq", 2011, 0.62),
    ]
    a = make_observation_claims(rows)
    b = make_observation_claims(rows)
    assert [c.claim_id for c in a] == [c.claim_id for c in b]
    assert len({c.claim_id for c in a}) == len(a)


# ---------------------------------------------------------------------------
# Real-desk integration
# ---------------------------------------------------------------------------


def test_real_desk_loads_multi_source_and_excludes_hand_seed() -> None:
    desk = load_observation_desk(PROCESSED)
    assert len(desk) >= 1000, "expected 1000+ observations from the ingest desk"
    sources = {o.source_id for o in desk}
    assert len(sources) >= 6
    assert "pew_global_religious_composition_2010_2020" in sources
    assert not (sources & obs_mod.EXCLUDED_SOURCES)
    # every observation is a reported share in [MIN_SHARE, 1]
    for o in desk:
        assert obs_mod.MIN_SHARE <= o.share <= 1.0 + 1e-9


def test_real_desk_pew_gets_settled() -> None:
    """The Phase 2 hole: Pew was only ever a settler. On the expanded desk
    Pew must have a posterior with trials — AB/CBS observations post-date
    Pew 2010/2020 and can settle it."""
    desk = load_observation_desk(PROCESSED)
    store = TrustStore()
    claims = make_observation_claims(desk, max_gap_years=30)
    settle_corroboration_claims(claims, store)
    pew = store.get("source_trust:pew_global_religious_composition_2010_2020")
    assert pew.trials > 0, "Pew must be settled, not just a settler"
