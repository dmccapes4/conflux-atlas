#!/usr/bin/env python3
"""Hand-seed migration edges for the first Conflux demo slice.

Volumes are rounded consensus estimates (DellaPergola / WJP, League of Nations
exchange stats, UNRWA-era refugee literature). Confidence is structural —
direction and order-of-magnitude — not precise headcounts.

Writes: data/processed/edges.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import MigrationEdge, MigrationKind, Religion  # noqa: E402

OUT = ROOT / "data" / "processed" / "edges.jsonl"
SOURCE = "hand_seed_edges_v0"


def edge(**kwargs) -> dict:
    if "source_ids" not in kwargs:
        kwargs["source_ids"] = [SOURCE]
    elif SOURCE not in kwargs["source_ids"]:
        kwargs["source_ids"] = [SOURCE, *kwargs["source_ids"]]
    return MigrationEdge(**kwargs).model_dump(mode="json")


EDGES: list[dict] = [
    edge(
        edge_id="greco_turkish_christians_1923",
        year_start=1923,
        year_end=1924,
        from_polity="turkey",
        to_polity="greece",
        group=Religion.CHRISTIAN,
        volume_est=1_200_000,
        volume_low=900_000,
        volume_high=1_500_000,
        kind=MigrationKind.SETTLEMENT_POLICY,
        trigger_event_id="lausanne_population_exchange_1923",
        confidence=0.70,
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914"],
        notes="Compulsory exchange under Lausanne; mostly Anatolian Greek Orthodox. greece not in hand-seed 12 but needed for the pair.",
    ),
    edge(
        edge_id="greco_turkish_muslims_1923",
        year_start=1923,
        year_end=1924,
        from_polity="greece",
        to_polity="turkey",
        group=Religion.MUSLIM,
        volume_est=400_000,
        volume_low=350_000,
        volume_high=500_000,
        kind=MigrationKind.SETTLEMENT_POLICY,
        trigger_event_id="lausanne_population_exchange_1923",
        confidence=0.70,
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914"],
        notes="Muslims of Greece → Turkey (same treaty). Smaller counter-flow than Christian leg.",
    ),
    edge(
        edge_id="iraq_jewish_exodus_1949_51",
        year_start=1949,
        year_end=1951,
        from_polity="iraq",
        to_polity="israel",
        group=Religion.JEWISH,
        volume_est=120_000,
        volume_low=110_000,
        volume_high=135_000,
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        trigger_event_id="arab_israeli_war_1948",
        confidence=0.70,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
        notes="Operation Ezra & Nehemiah; near-liquidation of Iraqi Jewry.",
    ),
    edge(
        edge_id="yemen_jewish_airlift_1949_50",
        year_start=1949,
        year_end=1950,
        from_polity="yemen",
        to_polity="israel",
        group=Religion.JEWISH,
        volume_est=49_000,
        volume_low=45_000,
        volume_high=55_000,
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        trigger_event_id="arab_israeli_war_1948",
        confidence=0.75,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
        notes="Operation Magic Carpet (On Eagles' Wings).",
    ),
    edge(
        edge_id="egypt_jewish_exodus_1948_67",
        year_start=1948,
        year_end=1967,
        from_polity="egypt",
        to_polity="israel",
        group=Religion.JEWISH,
        volume_est=70_000,
        volume_low=50_000,
        volume_high=90_000,
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        trigger_event_id="arab_israeli_war_1948",
        confidence=0.55,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
        notes="Multi-wave; additional tens of thousands went to France/elsewhere (not in this edge).",
    ),
    edge(
        edge_id="morocco_jewish_to_israel_1948_64",
        year_start=1948,
        year_end=1964,
        from_polity="morocco",
        to_polity="israel",
        group=Religion.JEWISH,
        volume_est=250_000,
        volume_low=200_000,
        volume_high=280_000,
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        trigger_event_id="arab_israeli_war_1948",
        confidence=0.60,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
        notes="Largest Maghrebi Jewish aliyah tranche; mixes flight and organized emigration.",
    ),
    edge(
        edge_id="morocco_jewish_to_france_1956_67",
        year_start=1956,
        year_end=1967,
        from_polity="morocco",
        to_polity="france",
        group=Religion.JEWISH,
        volume_est=50_000,
        volume_low=30_000,
        volume_high=80_000,
        kind=MigrationKind.VOLUNTARY,
        confidence=0.45,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
        notes="Parallel Maghrebi Jewish migration to France; volume band wide.",
    ),
    edge(
        edge_id="nakba_palestinians_to_lebanon_1948",
        year_start=1948,
        year_end=1949,
        from_polity="israel",
        to_polity="lebanon",
        group=Religion.MUSLIM,
        volume_est=100_000,
        volume_low=70_000,
        volume_high=130_000,
        kind=MigrationKind.REFUGEE,
        trigger_event_id="arab_israeli_war_1948",
        confidence=0.50,
        source_ids=[SOURCE, "unhcr_population_api"],
        notes="1948 Palestinian refugees into Lebanon; Christian Palestinian minority folded into muslim/other schema limit — treat as majority-Muslim refugee flow.",
    ),
    edge(
        edge_id="nakba_palestinians_to_syria_1948",
        year_start=1948,
        year_end=1949,
        from_polity="israel",
        to_polity="syria",
        group=Religion.MUSLIM,
        volume_est=90_000,
        volume_low=70_000,
        volume_high=120_000,
        kind=MigrationKind.REFUGEE,
        trigger_event_id="arab_israeli_war_1948",
        confidence=0.50,
        source_ids=[SOURCE, "unhcr_population_api"],
        notes="1948 Palestinian refugees into Syria; volumes contested across Israeli/Arab sources.",
    ),
    edge(
        edge_id="iran_jewish_exodus_1979_85",
        year_start=1979,
        year_end=1985,
        from_polity="iran",
        to_polity="united_states",
        group=Religion.JEWISH,
        volume_est=40_000,
        volume_low=25_000,
        volume_high=60_000,
        kind=MigrationKind.EXPULSION_OR_FLIGHT,
        trigger_event_id="iranian_revolution_1979",
        confidence=0.50,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
        notes="Post-revolution Jewish emigration; large share to US (others to Israel not in this edge).",
    ),
]


def main() -> None:
    assert 5 <= len(EDGES) <= 10, len(EDGES)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for rec in EDGES:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(EDGES)} edges)")
    for e in EDGES:
        print(
            f"  {e['edge_id']}: {e['from_polity']}→{e['to_polity']} "
            f"{e['group']} ~{e['volume_est']:,} ({e['year_start']}-{e['year_end']}) "
            f"conf={e['confidence']}"
        )


if __name__ == "__main__":
    main()
