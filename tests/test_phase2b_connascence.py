"""Phase 2b gate — connascence layer (STRATEGY_CONNASCENCE.md §5 pins).

Covers: registry totality, discount arithmetic, definitional routing,
complement exclusion in co-variance, null-model floor, one-hop partial
settlement, shock tagging, conservation claims, and repr_version stamps.
"""

from __future__ import annotations

import pytest

from conflux.connascence import (
    METHOD_REGISTRY,
    REPR_VERSION,
    SAME_FAMILY_WEIGHT,
    apply_partial_settlement,
    complement_edges,
    covariance_edges,
    independence_weight,
    make_conservation_claims,
    method_family,
    route_definitional_claims,
    settle_conservation_claims,
    settle_corroboration_claims_weighted,
    shock_events_for_window,
    tag_shock_claims,
)
from conflux.learning import Claim, Posterior, TrustStore
from conflux.movement import MovementEvent, place_hash
from conflux.observations import ShareObservation, make_observation_claims
from conflux.schema import Event, MigrationEdge, MigrationKind


# ---------------------------------------------------------------------------
# §2.1 STRUCTURAL — registry + discount arithmetic
# ---------------------------------------------------------------------------


def test_registry_totality_over_live_desk():
    """Every source the desk can emit has exactly one registered family."""
    desk_sources = {
        "cbs_population_madaf",
        "ottoman_demographics_wiki",
        "arab_barometer",
        "pew_global_religious_composition_2010_2020",
        "jewishdatabank_world_jewish_population",
        "arda_national_profiles_2005",
        "mccarthy_armenian_pop_ottoman",
    }
    assert desk_sources <= set(METHOD_REGISTRY)


def test_unregistered_sources_are_never_same_family():
    assert method_family("mystery_source") == "unregistered:mystery_source"
    assert independence_weight("mystery_source", "other_mystery") == 1.0
    # …not even with a registered source
    assert independence_weight("mystery_source", "arab_barometer") == 1.0


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # same family: both demographic syntheses
        (
            "pew_global_religious_composition_2010_2020",
            "jewishdatabank_world_jewish_population",
            SAME_FAMILY_WEIGHT,
        ),
        # same family: both census/registry
        ("cbs_population_madaf", "ottoman_demographics_wiki", SAME_FAMILY_WEIGHT),
        # cross family: survey vs synthesis
        ("arab_barometer", "pew_global_religious_composition_2010_2020", 1.0),
        # cross family: WCD-derived vs census
        ("arda_national_profiles_2005", "cbs_population_madaf", 1.0),
    ],
)
def test_independence_weights(a, b, expected):
    assert independence_weight(a, b) == expected
    assert independence_weight(b, a) == expected  # symmetric


def test_posterior_weighted_bump_arithmetic():
    p = Posterior()
    p2 = p.bumped(True, weight=0.5)
    assert p2.alpha == 1.5 and p2.beta == 1.0 and p2.trials == 1
    p3 = p2.bumped(False, weight=0.5)
    assert p3.alpha == 1.5 and p3.beta == 1.5
    with pytest.raises(ValueError):
        p.bumped(True, weight=0.0)
    with pytest.raises(ValueError):
        p.bumped(True, weight=1.5)


def _obs(src, pid, group, year, share, conf=0.8):
    return ShareObservation(
        obs_id=f"{src}|{pid}|{group}|{year}",
        polity_id=pid,
        group=group,
        year=year,
        share=share,
        confidence=conf,
        source_id=src,
    )


def test_weighted_settlement_discounts_same_family():
    """Agreeing same-family pair bumps α by 0.5; cross-family by 1.0."""
    same = [
        _obs("pew_global_religious_composition_2010_2020", "egypt", "jewish", 2010, 0.10),
        _obs("jewishdatabank_world_jewish_population", "egypt", "jewish", 2012, 0.10),
    ]
    cross = [
        _obs("arab_barometer", "egypt", "muslim", 2010, 0.90),
        _obs("pew_global_religious_composition_2010_2020", "egypt", "muslim", 2012, 0.90),
    ]
    store = TrustStore()
    claims = make_observation_claims(same + cross, max_gap_years=30)
    n = settle_corroboration_claims_weighted(claims, store)
    assert n >= 2
    pew_jewish = store.get("source_trust:pew_global_religious_composition_2010_2020")
    ab = store.get("source_trust:arab_barometer")
    # jewish claim: same-family agree → α = 1 + 0.5 (pew also claims in the
    # cross pair? no — pew claims muslim only as settler there). Check meta:
    same_claim = [c for c in claims if c.group == "jewish"][0]
    assert same_claim.meta["independence_weight"] == SAME_FAMILY_WEIGHT
    assert same_claim.meta["settle_weight"] == SAME_FAMILY_WEIGHT
    cross_claim = [c for c in claims if c.group == "muslim"][0]
    assert cross_claim.meta["independence_weight"] == 1.0
    assert ab.alpha == 2.0  # full bump
    assert pew_jewish.alpha == 1.5  # discounted bump


# ---------------------------------------------------------------------------
# §2.2 CONCEPTUAL — complement edges + definitional routing
# ---------------------------------------------------------------------------


def test_complement_edges_within_one_measurement_only():
    obs = [
        _obs("pew_global_religious_composition_2010_2020", "egypt", "muslim", 2010, 0.9),
        _obs("pew_global_religious_composition_2010_2020", "egypt", "christian", 2010, 0.08),
        # different source, same polity-year → NOT a complement edge
        _obs("arda_national_profiles_2005", "egypt", "jewish", 2010, 0.01),
        # different year → NOT a complement edge
        _obs("pew_global_religious_composition_2010_2020", "egypt", "jewish", 2020, 0.01),
    ]
    edges = complement_edges(obs)
    assert len(edges) == 1
    e = edges[0]
    assert e.kind == "concept:complement"
    assert {e.src, e.dst} == {
        "pew_global_religious_composition_2010_2020|egypt|muslim|2010",
        "pew_global_religious_composition_2010_2020|egypt|christian|2010",
    }
    assert e.repr_version == REPR_VERSION


def test_definitional_routing_quarantines_known_overlaps():
    obs = [
        _obs("jewishdatabank_world_jewish_population", "israel", "jewish", 2010, 0.74),
        _obs("pew_global_religious_composition_2010_2020", "israel", "jewish", 2012, 0.76),
    ]
    claims = make_observation_claims(obs, max_gap_years=30)
    assert claims and all(c.hypothesis_id.startswith("source_trust:") for c in claims)
    n = route_definitional_claims(claims)
    assert n == len(claims)
    for c in claims:
        assert c.hypothesis_id == "definition_gap:cjp_vs_pew_jewish"
        assert c.meta["routed_from"].startswith("source_trust:")
    # settling rerouted claims must not touch source_trust:*
    store = TrustStore()
    settle_corroboration_claims_weighted(claims, store)
    assert not any(h.startswith("source_trust:") for h in store.posteriors)
    assert store.get("definition_gap:cjp_vs_pew_jewish").trials == len(claims)


# ---------------------------------------------------------------------------
# §2.3 CO_VARIANCE — exclusion, null floor, positive control
# ---------------------------------------------------------------------------


def _ev(pid, group, y0, y1, rate, level=0.10):
    return MovementEvent(
        polity_id=pid,
        group=group,
        year_from=y0,
        year_to=y1,
        gap_years=y1 - y0,
        share_from=level,
        share_to=level + rate * (y1 - y0) / 10.0,
        delta=rate * (y1 - y0) / 10.0,
        rate_per_decade=rate,
        confidence=0.8,
        origin_hash=place_hash(level="minority", delta="na", gap="decade", vol="na"),
    )


def _co_moving_pair(pid_a="egypt", pid_b="iraq", group="jewish"):
    """Two series across polities, alternating direction in lockstep."""
    events = []
    for pid in (pid_a, pid_b):
        for i, rate in enumerate([-0.04, +0.03, -0.05, +0.02, -0.03]):
            events.append(_ev(pid, group, 1940 + 10 * i, 1950 + 10 * i, rate))
    return events


def test_covariance_positive_control_and_edge_shape():
    events = _co_moving_pair()
    edges = covariance_edges(events, min_overlap_pairs=3, alpha=0.05)
    assert len(edges) == 1
    e = edges[0]
    assert e.kind == "co_variance"
    assert {e.src, e.dst} == {"series|egypt|jewish", "series|iraq|jewish"}
    assert e.strength == 1.0
    assert e.meta["n_pairs"] >= 3
    assert e.meta["p_value"] < 0.05
    assert e.repr_version == REPR_VERSION


def test_covariance_complement_exclusion_same_polity():
    """Perfectly anti-covarying groups in ONE polity must yield no edge."""
    events = []
    for i, rate in enumerate([-0.04, +0.03, -0.05, +0.02, -0.03]):
        events.append(_ev("egypt", "muslim", 1940 + 10 * i, 1950 + 10 * i, rate))
        events.append(_ev("egypt", "christian", 1940 + 10 * i, 1950 + 10 * i, -rate))
    assert covariance_edges(events, min_overlap_pairs=3, alpha=0.05) == []


def test_covariance_flat_series_never_pair():
    """Flat transitions are excluded — flat-dominant series can't co-vary."""
    events = []
    for pid in ("egypt", "iraq"):
        for i in range(5):
            events.append(_ev(pid, "muslim", 1940 + 10 * i, 1950 + 10 * i, 0.0))
    assert covariance_edges(events, min_overlap_pairs=1, alpha=0.5) == []


def test_covariance_stratified_null_blocks_regime_comembership():
    """All-down regimes agreeing is the null itself — no edge minted.

    Every moving transition in the population goes down, so the
    bucket-stratified null probability of agreement is ~1 and observed
    perfect agreement carries zero evidence.
    """
    events = []
    for pid in ("egypt", "iraq", "syria", "yemen"):
        for i in range(5):
            events.append(_ev(pid, "jewish", 1940 + 10 * i, 1950 + 10 * i, -0.04))
    assert covariance_edges(events, min_overlap_pairs=3, alpha=0.05) == []


def test_covariance_min_overlap_pairs_respected():
    events = _co_moving_pair()
    assert covariance_edges(events, min_overlap_pairs=99, alpha=0.05) == []


def test_covariance_fdr_tiers():
    """Strict tier ⊆ hypothesis tier; strict edges are all fdr_pass=True."""
    events = _co_moving_pair() + _co_moving_pair("syria", "morocco", "christian")
    strict = covariance_edges(events, min_overlap_pairs=3, alpha=0.05)
    hypo = covariance_edges(events, min_overlap_pairs=3, alpha=0.05, require_fdr=False)
    strict_keys = {(e.src, e.dst) for e in strict}
    hypo_keys = {(e.src, e.dst) for e in hypo}
    assert strict_keys <= hypo_keys
    assert all(e.meta["fdr_pass"] for e in strict)
    # every edge carries the audit fields either way
    for e in hypo:
        assert "p_value" in e.meta and "fdr_pass" in e.meta


def test_covariance_shortlist_is_propose_only():
    """Shortlisting can only shrink the edge set, never add to it."""
    events = _co_moving_pair() + _co_moving_pair("syria", "morocco", "christian")
    full = covariance_edges(events, min_overlap_pairs=3, alpha=0.05)
    short = covariance_edges(events, min_overlap_pairs=3, alpha=0.05, shortlist_k=2)
    full_keys = {(e.src, e.dst) for e in full}
    short_keys = {(e.src, e.dst) for e in short}
    assert short_keys <= full_keys


# ---------------------------------------------------------------------------
# §2.3 partial settlement — one hop, capped
# ---------------------------------------------------------------------------


def _policy_claim(pid, group, y0, y1, predicted, policy="persistence", settled=False, success=None):
    c = Claim(
        claim_id=f"{pid}|{group}|{y0}|{y1}|{policy}",
        hypothesis_id=f"policy:{policy}",
        polity_id=pid,
        group=group,
        cut_year=y0,
        predicted=predicted,
        stated_p=0.6,
        train_n=5,
        year_from=y0,
        year_to=y1,
        meta={"policy": policy},
    )
    if settled:
        c.settled = True
        c.success = success
    return c


def test_partial_settlement_one_hop_and_cap():
    events = _co_moving_pair()  # egypt↔iraq jewish, strength 1.0
    edges = covariance_edges(events, min_overlap_pairs=3, alpha=0.05)
    settled = [_policy_claim("iraq", "jewish", 1950, 1960, "down", settled=True, success=True)]
    pending = [_policy_claim("egypt", "jewish", 1955, 1965, "down")]
    store = TrustStore()
    n = apply_partial_settlement(pending, settled, edges, store)
    assert n == 1
    post = store.get("policy:persistence")
    assert post.alpha == 1.0 + 0.25  # strength 1.0 × coefficient 0.25
    assert post.beta == 1.0
    # pending claim annotated but NOT settled — one-hop, no cascade
    assert pending[0].settled is False
    assert pending[0].meta["partial_bumps"][0]["weight"] == 0.25

    # a partially-bumped pending claim contributes nothing onward
    third = [_policy_claim("morocco", "jewish", 1955, 1965, "down")]
    n2 = apply_partial_settlement(third, pending, edges, store)
    assert n2 == 0

    with pytest.raises(ValueError):
        apply_partial_settlement(pending, settled, edges, store, coefficient=0.5)


def test_partial_settlement_requires_window_overlap_and_policy_match():
    events = _co_moving_pair()
    edges = covariance_edges(events, min_overlap_pairs=3, alpha=0.05)
    store = TrustStore()
    # no window overlap
    settled = [_policy_claim("iraq", "jewish", 1950, 1960, "down", settled=True, success=True)]
    pending = [_policy_claim("egypt", "jewish", 1970, 1980, "down")]
    assert apply_partial_settlement(pending, settled, edges, store) == 0
    # different policy
    pending2 = [_policy_claim("egypt", "jewish", 1955, 1965, "down", policy="hash_mode")]
    assert apply_partial_settlement(pending2, settled, edges, store) == 0


# ---------------------------------------------------------------------------
# §2.4 TEMPORAL — shock tagging
# ---------------------------------------------------------------------------


def _event(eid, year, year_end=None):
    return Event(
        event_id=eid,
        year=year,
        year_end=year_end,
        title=eid,
        source_ids=["test"],
        confidence=0.8,
    )


def test_shock_window_overlap():
    events = [_event("war_1948", 1948, 1949)]
    assert shock_events_for_window(1945, 1950, events) == ["war_1948"]
    assert shock_events_for_window(1949, 1960, events) == ["war_1948"]
    assert shock_events_for_window(1950, 1960, events) == []
    assert shock_events_for_window(1930, 1947, events) == []


def test_tag_shock_claims_stamps_meta():
    events = [_event("war_1948", 1948, 1949)]
    shock = _policy_claim("egypt", "jewish", 1945, 1950, "down")
    calm = _policy_claim("egypt", "jewish", 1990, 2000, "flat")
    n = tag_shock_claims([shock, calm], events)
    assert n == 1
    assert shock.meta["shock"] is True and shock.meta["shock_events"] == ["war_1948"]
    assert calm.meta["shock"] is False and calm.meta["shock_events"] == []


# ---------------------------------------------------------------------------
# §2.2 conservation claims
# ---------------------------------------------------------------------------


def _mig_edge(eid="iraq_to_israel", frm="iraq", to="israel", vol=120_000):
    return MigrationEdge(
        edge_id=eid,
        year_start=1949,
        year_end=1951,
        from_polity=frm,
        to_polity=to,
        group="jewish",
        volume_est=vol,
        volume_low=int(vol * 0.9),
        volume_high=int(vol * 1.1),
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        confidence=0.7,
        source_ids=["test"],
    )


def test_conservation_claim_settles_on_matching_books(mk_anchor):
    edge = _mig_edge()
    anchors = [
        mk_anchor("iraq", 1947, {"jewish": 0.026, "muslim": 0.95}, pop=5_000_000),
        mk_anchor("iraq", 1955, {"jewish": 0.001, "muslim": 0.975}, pop=5_500_000),
        mk_anchor("israel", 1948, {"jewish": 0.82, "muslim": 0.15}, pop=800_000),
        mk_anchor("israel", 1955, {"jewish": 0.89, "muslim": 0.09}, pop=1_800_000),
    ]
    claims = make_conservation_claims(anchors, [edge])
    assert len(claims) == 1
    store = TrustStore()
    settle_conservation_claims(claims, store)
    c = claims[0]
    # iraq jewish: 130k → 5.5k  (loss ≈ 124.5k, inside [0.5·108k, 4·132k])
    assert c.success is True
    assert c.meta["origin_loss"] > 0
    assert c.meta["dest_gain"] > 0
    assert store.get(f"conservation:{edge.edge_id}").trials == 1


def test_conservation_claim_fails_when_origin_never_lost(mk_anchor):
    edge = _mig_edge()
    anchors = [
        mk_anchor("iraq", 1947, {"jewish": 0.026, "muslim": 0.95}, pop=5_000_000),
        mk_anchor("iraq", 1955, {"jewish": 0.026, "muslim": 0.95}, pop=5_500_000),
        mk_anchor("israel", 1948, {"jewish": 0.82, "muslim": 0.15}, pop=800_000),
        mk_anchor("israel", 1955, {"jewish": 0.89, "muslim": 0.09}, pop=1_800_000),
    ]
    claims = make_conservation_claims(anchors, [edge])
    store = TrustStore()
    settle_conservation_claims(claims, store)
    assert claims[0].success is False


def test_conservation_abstains_without_bracketing_anchors(mk_anchor):
    edge = _mig_edge()
    anchors = [  # destination side missing entirely
        mk_anchor("iraq", 1947, {"jewish": 0.026, "muslim": 0.95}, pop=5_000_000),
        mk_anchor("iraq", 1955, {"jewish": 0.001, "muslim": 0.975}, pop=5_500_000),
    ]
    assert make_conservation_claims(anchors, [edge]) == []
