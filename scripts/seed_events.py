#!/usr/bin/env python3
"""Seed events.jsonl for triggers already referenced by migration edges.

v0 covers Lausanne 1923, 1948 Arab–Israeli war / Nakba context, and Iran 1979.
Contested 1976 Lebanon events deferred (see STRATEGY).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import Event, EventEffect, EventEffectType  # noqa: E402

OUT = ROOT / "data" / "processed" / "events.jsonl"
SOURCE = "hand_seed_events_v0"


def event(**kwargs) -> dict:
    if "source_ids" not in kwargs:
        kwargs["source_ids"] = [SOURCE]
    elif SOURCE not in kwargs["source_ids"]:
        kwargs["source_ids"] = [SOURCE, *kwargs["source_ids"]]
    return Event(**kwargs).model_dump(mode="json")


EVENTS: list[dict] = [
    event(
        event_id="lausanne_population_exchange_1923",
        year=1923,
        year_end=1924,
        title="Lausanne compulsory population exchange (Greece–Turkey)",
        affected_polities=["turkey", "greece"],
        effects=[
            EventEffect(
                type=EventEffectType.MIGRATION_BURST,
                edge_id="greco_turkish_christians_1923",
            ),
            EventEffect(
                type=EventEffectType.MIGRATION_BURST,
                edge_id="greco_turkish_muslims_1923",
            ),
            EventEffect(
                type=EventEffectType.CONFIDENCE_RESET,
                polity_id="turkey",
                confidence=0.55,
            ),
        ],
        confidence=0.85,
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914"],
        notes="Treaty of Lausanne Articles on exchange; high structural confidence, volume on edges.",
    ),
    event(
        event_id="arab_israeli_war_1948",
        year=1948,
        year_end=1949,
        title="1948 Arab–Israeli War / Nakba / Jewish exodus wave",
        affected_polities=[
            "israel",
            "palestine",
            "lebanon",
            "syria",
            "egypt",
            "iraq",
            "yemen",
            "morocco",
        ],
        effects=[
            EventEffect(type=EventEffectType.MIGRATION_BURST, edge_id="iraq_jewish_exodus_1949_51"),
            EventEffect(type=EventEffectType.MIGRATION_BURST, edge_id="yemen_jewish_airlift_1949_50"),
            EventEffect(type=EventEffectType.MIGRATION_BURST, edge_id="egypt_jewish_exodus_1948_67"),
            EventEffect(type=EventEffectType.MIGRATION_BURST, edge_id="morocco_jewish_to_israel_1948_64"),
            EventEffect(type=EventEffectType.MIGRATION_BURST, edge_id="nakba_palestinians_to_lebanon_1948"),
            EventEffect(type=EventEffectType.MIGRATION_BURST, edge_id="nakba_palestinians_to_syria_1948"),
            EventEffect(
                type=EventEffectType.CONFIDENCE_RESET,
                polity_id="israel",
                confidence=0.50,
            ),
        ],
        confidence=0.70,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population", "unhcr_population_api"],
        notes=(
            "Umbrella trigger for 1948–early-1950s displacement edges already seeded. "
            "Volumes contested; event marks structural break, not a single headcount."
        ),
    ),
    event(
        event_id="iranian_revolution_1979",
        year=1979,
        year_end=1985,
        title="Iranian Revolution and post-1979 Jewish emigration",
        affected_polities=["iran", "united_states", "israel"],
        effects=[
            EventEffect(
                type=EventEffectType.MIGRATION_BURST,
                edge_id="iran_jewish_exodus_1979_85",
            ),
            EventEffect(
                type=EventEffectType.CONFIDENCE_RESET,
                polity_id="iran",
                confidence=0.45,
            ),
        ],
        confidence=0.65,
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
        notes="Links seeded Iran→US Jewish flight edge; Israel-bound flow not yet a separate edge.",
    ),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for rec in EVENTS:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(EVENTS)} events)")
    for e in EVENTS:
        print(f"  {e['event_id']}: {e['title']} ({e['year']})")


if __name__ == "__main__":
    main()
