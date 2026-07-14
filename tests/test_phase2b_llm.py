"""Phase 2b gate — LLM enrichment protocol invariants (no live model).

Pins the §3 contract with a fake client: proposals are recorded and
settled as claims under llm_proposer:<model>; the deterministic verifier
is the only promotion path; abstentions cost nothing; malformed windows
are dropped.
"""

from __future__ import annotations

from conflux.connascence import CovarianceCluster
from conflux.learning import TrustStore
from conflux.llm_enrich import (
    EnrichmentResult,
    PairCandidate,
    enrich_conceptual_couplings,
    enrich_event_attribution,
    verify_coupling,
    verify_event_attribution,
)
from conflux.observations import ShareObservation
from conflux.schema import Event, MigrationEdge, MigrationKind


class FakeClient:
    """Scripted stand-in for OllamaClient — returns canned windows in order."""

    def __init__(self, responses):
        self.model = "fake-enricher"
        self.responses = list(responses)
        self.calls = 0

    def chat_json(self, system, user, schema):
        self.calls += 1
        return self.responses.pop(0) if self.responses else None


def _event(eid="arab_israeli_war_1948", year=1948, year_end=1949, polities=("israel", "iraq")):
    return Event(
        event_id=eid,
        year=year,
        year_end=year_end,
        title=eid,
        affected_polities=list(polities),
        source_ids=["test"],
        confidence=0.8,
    )


def _mig_edge(frm="iraq", to="israel", group="jewish", trigger=None):
    return MigrationEdge(
        edge_id=f"{frm}_{to}_{group}",
        year_start=1949,
        year_end=1951,
        from_polity=frm,
        to_polity=to,
        group=group,
        volume_est=100_000,
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        trigger_event_id=trigger,
        confidence=0.7,
        source_ids=["test"],
    )


def _cluster(series=("series|egypt|jewish", "series|iraq|jewish"), y0=1945, y1=1960):
    return CovarianceCluster(
        cluster_id="c1",
        series=list(series),
        year_min=y0,
        year_max=y1,
        dominant_direction="down",
        n_edges=1,
    )


# ---------------------------------------------------------------------------
# Deterministic verifiers
# ---------------------------------------------------------------------------


def test_verify_event_attribution_window_and_polity():
    ev = _event()
    # iraq is in cluster AND affected_polities; window overlaps → pass
    assert verify_event_attribution(_cluster(), ev, []) is True
    # window far away → fail even with polity contact
    assert verify_event_attribution(_cluster(y0=1990, y1=2000), ev, []) is False
    # no polity contact and no edge contact → fail
    far = _cluster(series=("series|morocco|christian", "series|syria|christian"))
    assert verify_event_attribution(far, ev, []) is False
    # polity contact via a triggered migration edge → pass
    edge = _mig_edge(frm="morocco", to="france", trigger="arab_israeli_war_1948")
    viaedge = _cluster(series=("series|morocco|jewish", "series|tunisia|jewish"))
    assert verify_event_attribution(viaedge, ev, [edge]) is True


def _pair(**kw):
    defaults = dict(
        pair_id="p1",
        kind_hint={},
        polity_a="iraq",
        polity_b="israel",
        group_a="jewish",
        group_b="jewish",
        source_a="*series*",
        source_b="*series*",
    )
    defaults.update(kw)
    return PairCandidate(**defaults)


def test_verify_coupling_kinds():
    edges = [_mig_edge()]
    # conservation: documented edge between the polities, same group → pass
    assert verify_coupling(_pair(), "conservation", edges, []) is True
    # conservation without a documented edge → fail
    assert (
        verify_coupling(_pair(polity_b="turkey"), "conservation", edges, []) is False
    )
    # complement: same polity/source/year, different groups → pass
    comp = _pair(
        polity_b="iraq",
        group_b="muslim",
        source_a="pew",
        source_b="pew",
        year_a=2010,
        year_b=2010,
    )
    assert verify_coupling(comp, "complement", edges, []) is True
    # complement across sources → fail
    comp2 = _pair(
        polity_b="iraq", group_b="muslim", source_a="pew", source_b="arda",
        year_a=2010, year_b=2010,
    )
    assert verify_coupling(comp2, "complement", edges, []) is False
    # definition: registry hit → pass without observations
    defp = _pair(
        polity_b="iraq",
        source_a="jewishdatabank_world_jewish_population",
        source_b="pew_global_religious_composition_2010_2020",
        polity_a="iraq",
        year_a=2010,
        year_b=2010,
    )
    assert verify_coupling(defp, "definition", edges, []) is True
    # unknown kind → fail
    assert verify_coupling(_pair(), "similarity", edges, []) is False


def test_verify_definition_by_systematic_offset():
    """Non-registry pair passes only with ≥3 one-sided beyond-tolerance gaps."""
    obs = []
    for year in (2000, 2005, 2010, 2015):
        obs.append(
            ShareObservation(
                obs_id=f"a|x|muslim|{year}", polity_id="x", group="muslim",
                year=year, share=0.60, confidence=0.8, source_id="src_a",
            )
        )
        obs.append(
            ShareObservation(
                obs_id=f"b|x|muslim|{year}", polity_id="x", group="muslim",
                year=year, share=0.50, confidence=0.8, source_id="src_b",
            )
        )
    p = _pair(
        polity_a="x", polity_b="x", group_a="muslim", group_b="muslim",
        source_a="src_a", source_b="src_b", year_a=2000, year_b=2000,
    )
    assert verify_coupling(p, "definition", [], obs) is True
    # same shares → no systematic offset → fail
    flat = [o for o in obs if o.source_id == "src_a"] + [
        ShareObservation(
            obs_id=f"b|x|muslim|{o.year}", polity_id="x", group="muslim",
            year=o.year, share=0.60, confidence=0.8, source_id="src_b",
        )
        for o in obs
        if o.source_id == "src_a"
    ]
    assert verify_coupling(p, "definition", [], flat) is False


# ---------------------------------------------------------------------------
# Windowed runner protocol
# ---------------------------------------------------------------------------


def test_event_attribution_records_settles_and_gates_edges():
    cluster = _cluster()
    ev = _event()
    store = TrustStore()
    result = EnrichmentResult(model="fake-enricher")
    client = FakeClient(
        [
            {
                "attributions": [
                    {"cluster_id": "c1", "event_id": "arab_israeli_war_1948", "rationale": "1948 war"},
                ]
            }
        ]
    )
    enrich_event_attribution(client, [cluster], [ev], [], store, result)
    assert result.proposals == 1 and result.verified == 1 and result.rejected == 0
    post = store.get("llm_proposer:fake-enricher")
    assert post.trials == 1 and post.alpha == 2.0
    assert len(result.verified_event_edges) == 1
    assert store.ledger[0].settled is True


def test_bad_proposal_is_rejected_and_never_becomes_an_edge():
    cluster = _cluster(y0=1990, y1=2000)  # window misses the 1948 event
    ev = _event()
    store = TrustStore()
    result = EnrichmentResult(model="fake-enricher")
    client = FakeClient(
        [
            {
                "attributions": [
                    {"cluster_id": "c1", "event_id": "arab_israeli_war_1948", "rationale": "x"},
                    {"cluster_id": "c1", "event_id": "invented_event_9999", "rationale": "y"},
                ]
            }
        ]
    )
    enrich_event_attribution(client, [cluster], [ev], [], store, result)
    assert result.proposals == 2 and result.verified == 0 and result.rejected == 2
    assert result.verified_event_edges == []
    post = store.get("llm_proposer:fake-enricher")
    assert post.beta == 3.0  # two failures on the proposer's own ledger


def test_null_attribution_is_free_abstention():
    store = TrustStore()
    result = EnrichmentResult(model="fake-enricher")
    client = FakeClient(
        [{"attributions": [{"cluster_id": "c1", "event_id": None, "rationale": "none fits"}]}]
    )
    enrich_event_attribution(client, [_cluster()], [_event()], [], store, result)
    assert result.proposals == 0
    assert result.abstained == 1
    assert store.get("llm_proposer:fake-enricher").trials == 0
    assert store.ledger == []


def test_malformed_window_dropped_without_ledger_damage():
    store = TrustStore()
    result = EnrichmentResult(model="fake-enricher")
    client = FakeClient([None])  # chat_json returning None = double parse failure
    enrich_event_attribution(client, [_cluster()], [_event()], [], store, result)
    assert result.windows_failed == 1
    assert store.ledger == []


def test_coupling_runner_promotes_only_verified():
    edges = [_mig_edge()]
    good = _pair(pair_id="good")  # conservation with a documented edge
    bad = _pair(pair_id="bad", polity_b="turkey")  # no documented edge
    store = TrustStore()
    result = EnrichmentResult(model="fake-enricher")
    client = FakeClient(
        [
            {
                "proposals": [
                    {"pair_id": "good", "kind": "conservation", "rationale": "edge exists"},
                    {"pair_id": "bad", "kind": "conservation", "rationale": "guess"},
                    {"pair_id": "good", "kind": None, "rationale": "abstain dup"},
                ]
            }
        ]
    )
    enrich_conceptual_couplings(client, [good, bad], edges, [], store, result)
    assert result.proposals == 2  # null is not a proposal
    assert result.verified == 1 and result.rejected == 1
    assert len(result.verified_coupling_edges) == 1
    edge = result.verified_coupling_edges[0]
    assert edge.kind == "concept:conservation"
    assert edge.meta["proposer"] == "fake-enricher"
    post = store.get("llm_proposer:fake-enricher")
    assert post.trials == 2 and post.alpha == 2.0 and post.beta == 2.0
