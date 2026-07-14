"""Phase 0 — ConfluxModel view invariants + golden smoke (offline)."""

from __future__ import annotations

from conflux.model import ConfluxModel, DEMO_POLITIES


def test_view_invariants_1948() -> None:
    model = ConfluxModel()
    view = model.view(1948)
    assert view.year == 1948
    assert len(view.nodes) >= 8
    for nid, node in view.nodes.items():
        assert 0.0 <= node.confidence <= 1.0
        if node.ghost:
            continue
        s = sum(node.shares.values())
        assert abs(s - 1.0) < 0.03, f"{nid} shares sum={s}"
        assert node.total_population >= 0


def test_golden_smoke_demo_polities_present() -> None:
    """Stable snapshot: core demo polities resolve across the scrubber window."""
    model = ConfluxModel()
    core = [p for p in DEMO_POLITIES if p != "greece"]
    for year in (1900, 1950, 2000, 2020):
        view = model.view(year)
        for pid in core:
            assert pid in view.nodes, f"missing {pid} @ {year}"
            assert not view.nodes[pid].ghost

    # greece is an edge endpoint (1923 exchange), not a hand-seeded share series
    view_1923 = model.view(1923)
    assert "greece" in view_1923.nodes


def test_golden_snapshot_egypt_1950() -> None:
    """True golden values (updated 2026-07-14 for WPP-prefer overlay).

    If seeds/overlays change on purpose, update these numbers deliberately
    in the same commit.
    """
    model = ConfluxModel(apply_event_deltas=False, prefer_wpp=True)
    node = model.view(1950).nodes["egypt"]
    assert node.total_population == 20_928_820  # UN WPP overlay (preferred)
    assert node.pop_source == "un_wpp"
    assert node.confidence == 0.55  # hand_seed_v0 @ 1950
    assert abs(node.shares["muslim"] - 0.915) < 1e-9
    assert abs(node.shares["christian"] - 0.08) < 1e-9


def test_smoke_edge_fade_window_includes_1948() -> None:
    model = ConfluxModel()
    view = model.view(1948)
    active = [e for e in view.edges if e.alpha > 0]
    assert active, "expected at least one migration edge visible in 1948"
    ids = {e.edge.edge_id for e in active}
    assert any("nakba" in i or "jewish" in i or "1948" in i or "1949" in i for i in ids)


def test_event_deltas_move_1948_populations() -> None:
    """Phase 0 milestone: with deltas on, 1948-window edges mutate node totals."""
    off = ConfluxModel(apply_event_deltas=False).view(1951)
    on = ConfluxModel(apply_event_deltas=True).view(1951)
    assert on.applied_deltas, "expected applied migration deltas by 1951"
    # Iraq→Israel Jewish exodus is fully in window by 1951
    iraq_off = off.nodes["iraq"].total_population
    iraq_on = on.nodes["iraq"].total_population
    israel_off = off.nodes["israel"].total_population
    israel_on = on.nodes["israel"].total_population
    assert iraq_on < iraq_off
    assert israel_on > israel_off
    assert on.nodes["iraq"].net_migration < 0
    assert on.nodes["israel"].net_migration > 0


def test_wpp_preferred_over_owid() -> None:
    wpp = ConfluxModel(prefer_wpp=True).view(1950).nodes["egypt"]
    owid = ConfluxModel(prefer_wpp=False).view(1950).nodes["egypt"]
    assert wpp.pop_source == "un_wpp"
    assert owid.pop_source == "owid_population"
    assert wpp.total_population != owid.total_population
