#!/usr/bin/env python3
"""Upsert beacon tranche-1 events + migration edges into processed jsonl.

Tranche (BEACON_INGEST_CONNASCENCE.md):
  - syrian_civil_war_2011 + UNHCR stock-derived OD edges (SYR→hosts)
  - lebanese_civil_war_1975 + Labaki/Tabar early-war destination edges
  - deepen iranian_revolution_1979 with Israel-bound Jewish edge

Does not rewrite the v0 demo seeds from scratch — loads existing files,
upserts by id, writes back. Re-run after fetch/ingest_unhcr_coo.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import (  # noqa: E402
    Event,
    EventEffect,
    EventEffectType,
    MigrationEdge,
    MigrationKind,
    Religion,
)

EVENTS_PATH = ROOT / "data" / "processed" / "events.jsonl"
EDGES_PATH = ROOT / "data" / "processed" / "edges.jsonl"
OD_PATH = ROOT / "data" / "processed" / "unhcr_syria_refugee_stock_od.jsonl"
SOURCE = "beacon_tranche1_v0"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def _dump(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _upsert(rows: list[dict], key: str, new_rows: list[dict]) -> list[dict]:
    by = {r[key]: r for r in rows}
    for r in new_rows:
        by[r[key]] = r
    return [by[k] for k in sorted(by)]


def _od_stock(origin: str, dest: str, year: int) -> int | None:
    if not OD_PATH.exists():
        return None
    for r in _load(OD_PATH):
        if (
            r["origin_polity_id"] == origin
            and r["dest_polity_id"] == dest
            and int(r["year"]) == year
        ):
            return int(r["refugees"])
    return None


def _syria_edge(dest: str, year: int, *, lo_frac: float = 0.85, hi_frac: float = 1.15) -> dict:
    stock = _od_stock("syria", dest, year)
    if stock is None or stock <= 0:
        raise SystemExit(f"missing UNHCR OD stock syria→{dest}@{year}; run ingest_unhcr_coo.py")
    est = stock
    low = max(0, int(est * lo_frac))
    high = int(est * hi_frac)
    return MigrationEdge(
        edge_id=f"syria_refugees_to_{dest}_2011_{year}",
        year_start=2011,
        year_end=year,
        from_polity="syria",
        to_polity=dest,
        group=Religion.MUSLIM,
        volume_est=est,
        volume_low=low,
        volume_high=high,
        kind=MigrationKind.REFUGEE,
        trigger_event_id="syrian_civil_war_2011",
        confidence=0.65,
        source_ids=[SOURCE, "unhcr_population_api"],
        notes=(
            f"UNHCR Refugee Statistics API stock at {year} (not a flow). "
            "Used as order-of-magnitude displacement magnitude for the 2011–"
            f"{year} burst; conservation settlement may abstain without brackets."
        ),
    ).model_dump(mode="json")


def build_events() -> list[dict]:
    syria_hosts = ["turkey", "lebanon", "jordan", "iraq", "germany", "egypt"]
    syria_effects = [
        EventEffect(
            type=EventEffectType.MIGRATION_BURST,
            edge_id=f"syria_refugees_to_{d}_2011_2015",
        )
        for d in syria_hosts
    ] + [
        EventEffect(
            type=EventEffectType.CONFIDENCE_RESET,
            polity_id="syria",
            confidence=0.40,
        )
    ]
    return [
        Event(
            event_id="syrian_civil_war_2011",
            year=2011,
            year_end=2024,
            title="Syrian Civil War & regional refugee crisis",
            affected_polities=[
                "syria",
                "turkey",
                "lebanon",
                "jordan",
                "iraq",
                "egypt",
                "germany",
                "sweden",
                "france",
            ],
            effects=syria_effects,
            source_ids=[SOURCE, "unhcr_population_api"],
            confidence=0.80,
            notes=(
                "Beacon syrian_civil_war_refugees_2011_present. "
                "Shock window for 2010–2020 policy transitions on contact polities."
            ),
        ).model_dump(mode="json"),
        Event(
            event_id="lebanese_civil_war_1975",
            year=1975,
            year_end=1990,
            title="Lebanese Civil War",
            affected_polities=["lebanon", "syria", "israel", "palestine"],
            effects=[
                EventEffect(
                    type=EventEffectType.MIGRATION_BURST,
                    edge_id="lebanon_emigrants_to_syria_1975_77",
                ),
                EventEffect(
                    type=EventEffectType.MIGRATION_BURST,
                    edge_id="lebanon_emigrants_to_france_1975_77",
                ),
                EventEffect(
                    type=EventEffectType.MIGRATION_BURST,
                    edge_id="lebanon_emigrants_to_united_states_1975_77",
                ),
                EventEffect(
                    type=EventEffectType.CONFIDENCE_RESET,
                    polity_id="lebanon",
                    confidence=0.45,
                ),
            ],
            source_ids=[SOURCE, "labaki_abu_rjaili_2005"],
            confidence=0.70,
            notes=(
                "Beacon lebanese_civil_war_1975_1990. Early-war Labaki destination "
                "tables (via Tabar 2010). Full-war 680k–990k total not yet edged."
            ),
        ).model_dump(mode="json"),
    ]


def deepen_iran_event(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        if e["event_id"] != "iranian_revolution_1979":
            out.append(e)
            continue
        effects = list(e.get("effects") or [])
        ids = {x.get("edge_id") for x in effects}
        if "iran_jewish_exodus_to_israel_1979_85" not in ids:
            effects.append(
                {
                    "type": "migration_burst",
                    "edge_id": "iran_jewish_exodus_to_israel_1979_85",
                    "polity_id": None,
                    "confidence": None,
                }
            )
        pols = list(e.get("affected_polities") or [])
        if "israel" not in pols:
            pols.append("israel")
        src = list(e.get("source_ids") or [])
        if SOURCE not in src:
            src.append(SOURCE)
        e = dict(e)
        e["effects"] = effects
        e["affected_polities"] = pols
        e["source_ids"] = src
        e["notes"] = (
            (e.get("notes") or "")
            + " Tranche-1: added Israel-bound Jewish edge from WJP-era synthesis."
        ).strip()
        out.append(e)
    return out


def build_edges() -> list[dict]:
    hosts = ["turkey", "lebanon", "jordan", "iraq", "germany", "egypt"]
    edges = [_syria_edge(d, 2015) for d in hosts]
    # Labaki/Tabar early-war destination counts (inventory; caution volumes).
    labaki = [
        ("syria", 73_250, 60_000, 90_000),
        ("france", 21_126, 15_000, 30_000),
        ("united_states", 14_515, 10_000, 25_000),
    ]
    for dest, est, lo, hi in labaki:
        edges.append(
            MigrationEdge(
                edge_id=f"lebanon_emigrants_to_{dest}_1975_77",
                year_start=1975,
                year_end=1977,
                from_polity="lebanon",
                to_polity=dest,
                group=Religion.CHRISTIAN,  # Labaki wave heavily Christian; schema single-group
                volume_est=est,
                volume_low=lo,
                volume_high=hi,
                kind=MigrationKind.REFUGEE,
                trigger_event_id="lebanese_civil_war_1975",
                confidence=0.55,
                source_ids=[SOURCE, "labaki_abu_rjaili_2005"],
                notes=(
                    "Labaki & Abu-Rjaili early-war net emigration Apr 1975–Apr 1977 "
                    "via Tabar (2010). Group tag is a schema compromise (mixed "
                    "confessional outflow)."
                ),
            ).model_dump(mode="json")
        )
    edges.append(
        MigrationEdge(
            edge_id="iran_jewish_exodus_to_israel_1979_85",
            year_start=1979,
            year_end=1985,
            from_polity="iran",
            to_polity="israel",
            group=Religion.JEWISH,
            volume_est=25_000,
            volume_low=15_000,
            volume_high=40_000,
            kind=MigrationKind.EXPULSION_OR_FLIGHT,
            trigger_event_id="iranian_revolution_1979",
            confidence=0.45,
            source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
            notes="Complement to US-bound edge; order-of-magnitude from WJP decline.",
        ).model_dump(mode="json")
    )
    return edges


def main() -> None:
    events = deepen_iran_event(_upsert(_load(EVENTS_PATH), "event_id", build_events()))
    edges = _upsert(_load(EDGES_PATH), "edge_id", build_edges())
    # validate
    for e in events:
        Event.model_validate(e)
    for e in edges:
        MigrationEdge.model_validate(e)
    _dump(EVENTS_PATH, events)
    _dump(EDGES_PATH, edges)
    print(f"wrote {EVENTS_PATH} ({len(events)} events)")
    print(f"wrote {EDGES_PATH} ({len(edges)} edges)")
    for eid in (
        "syrian_civil_war_2011",
        "lebanese_civil_war_1975",
        "iranian_revolution_1979",
    ):
        print(f"  event {eid}: OK")


if __name__ == "__main__":
    main()
