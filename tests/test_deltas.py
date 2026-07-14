"""Unit tests for event-delta helpers (offline)."""

from __future__ import annotations

from conflux.deltas import apply_volume_to_nodes, edge_progress_frac
from conflux.schema import MigrationEdge, MigrationKind, Religion


def test_edge_progress_frac_ramp() -> None:
    e = MigrationEdge(
        edge_id="t",
        year_start=1948,
        year_end=1951,
        from_polity="iraq",
        to_polity="israel",
        group=Religion.JEWISH,
        volume_est=120000,
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        confidence=0.5,
        source_ids=["hand_seed_edges_v0"],
    )
    assert edge_progress_frac(e, 1947) == 0.0
    assert 0.0 < edge_progress_frac(e, 1949) < 1.0
    assert edge_progress_frac(e, 1951) == 1.0
    assert edge_progress_frac(e, 1960) == 1.0


def test_apply_volume_moves_group_mass() -> None:
    from_pop, fs, to_pop, ts = apply_volume_to_nodes(
        from_pop=1_000_000,
        from_shares={"muslim": 0.9, "jewish": 0.1},
        to_pop=500_000,
        to_shares={"jewish": 0.8, "muslim": 0.2},
        group="jewish",
        volume=50_000,
    )
    assert from_pop == 950_000
    assert to_pop == 550_000
    assert fs["jewish"] < 0.1
    assert ts["jewish"] > 0.8
