"""Phase 2.5 — PortalGC evidence-graph export + governance guardrails.

Tests the graph mapping (`conflux/portal_graph.py`), not the Lorenz
classifier itself. The one classification test uses provenance-engine
directly and skips if the package is absent.
"""

from __future__ import annotations

import pytest

from conflux.learning import TrustStore
from conflux.observations import ShareObservation, make_observation_claims
from conflux.portal_graph import build_portal_nodes, sweep_portal, write_portal_jsonl
from conflux.settlement import settle_corroboration_claims


def _obs(src: str, pid: str, year: int, share: float, conf: float = 0.6) -> ShareObservation:
    return ShareObservation(
        obs_id=f"{src}|{pid}|muslim|{year}",
        polity_id=pid, group="muslim", year=year,
        share=share, confidence=conf, source_id=src,
    )


@pytest.fixture
def small_desk():
    obs = [
        _obs("src_a", "egypt", 1950, 0.90, 0.8),
        _obs("src_b", "egypt", 1960, 0.91, 0.6),
        _obs("src_a", "iraq", 1950, 0.85, 0.8),   # sole source for iraq
    ]
    store = TrustStore()
    claims = make_observation_claims(obs)
    settle_corroboration_claims(claims, store)
    return obs, claims, store


def test_nodes_well_formed(small_desk) -> None:
    obs, claims, store = small_desk
    nodes = build_portal_nodes(obs, claims, store)
    ids = [n["id"] for n in nodes]
    assert len(ids) == len(set(ids)), "node ids must be unique"
    id_set = set(ids)
    for n in nodes:
        for e in n["edges"]:
            assert e["target"] in id_set, f"dangling edge target {e['target']}"
            assert e["type"] in {
                "SOURCE", "CO_OCCURRENCE", "CO_VARIANCE", "TEMPORAL",
            }
            assert 0.0 <= e["strength"] <= 1.0
    # observation + source hub nodes both present
    types = {n["type"] for n in nodes}
    assert types == {"observation", "source"}


def test_sole_source_timeline_is_load_bearing(small_desk) -> None:
    obs, claims, store = small_desk
    nodes = {n["id"]: n for n in build_portal_nodes(obs, claims, store)}
    assert nodes["src_a|iraq|muslim|1950"]["load_bearing"] is True
    # egypt has two sources → its observations are not sole-source
    assert nodes["src_a|egypt|muslim|1950"]["load_bearing"] is False


def test_vitality_is_evidential_not_calendar(small_desk) -> None:
    """The trap the review flagged: pre-1920 must not auto-evict for age.
    updated_at derives from corroboration status, so a corroborated 1950
    observation is FRESHER than an unsettled 1960 one."""
    obs, claims, store = small_desk
    nodes = {n["id"]: n for n in build_portal_nodes(obs, claims, store)}
    corroborated_1950 = nodes["src_a|egypt|muslim|1950"]["updated_at"]
    unsettled_1960 = nodes["src_b|egypt|muslim|1960"]["updated_at"]
    assert corroborated_1950 > unsettled_1960  # ISO strings compare temporally


def test_covariance_edge_from_settled_corroboration(small_desk) -> None:
    obs, claims, store = small_desk
    nodes = {n["id"]: n for n in build_portal_nodes(obs, claims, store)}
    cov = [
        e for e in nodes["src_a|egypt|muslim|1950"]["edges"]
        if e["type"] == "CO_VARIANCE"
    ]
    assert len(cov) == 1
    assert cov[0]["target"] == "src_b|egypt|muslim|1960"
    assert cov[0]["strength"] == 1.0  # agreement within tolerance


def test_trusted_source_hub_is_load_bearing(small_desk) -> None:
    obs, claims, store = small_desk
    nodes = {n["id"]: n for n in build_portal_nodes(obs, claims, store)}
    hub = nodes["source:src_a"]
    assert hub["load_bearing"] is True  # settled trials with mean >= 0.5
    assert hub["metadata"]["trust_trials"] > 0


def test_jsonl_roundtrip(small_desk, tmp_path) -> None:
    import json

    obs, claims, store = small_desk
    nodes = build_portal_nodes(obs, claims, store)
    path = tmp_path / "portal.jsonl"
    write_portal_jsonl(nodes, path)
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == len(nodes)
    assert all("id" in rec and "edges" in rec for rec in lines)


def test_sweep_never_evicts_load_bearing(small_desk) -> None:
    """The provenance-engine invariant we rely on: load_bearing nodes are
    escalated to REVIEW, never EVICT — across the whole ρ×τ grid."""
    pytest.importorskip("provenance_engine", reason="provenance-engine not installed")
    obs, claims, store = small_desk
    nodes = build_portal_nodes(obs, claims, store)
    results = sweep_portal(nodes, rhos=(24.0, 28.0, 32.0), taus=(1.5, 2.0, 3.0))
    assert len(results) == 9
    for r in results:
        assert r["load_bearing_evictions"] == 0
        assert sum(r["counts"].values()) == len(nodes)
