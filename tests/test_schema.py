"""Phase 0 — schema validation (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from conflux.schema import Anchor, Event, MigrationEdge, Religion

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def test_anchor_shares_must_sum_near_one() -> None:
    with pytest.raises(ValidationError):
        Anchor(
            anchor_id="bad",
            polity_id="egypt",
            year=2000,
            total_population=1,
            shares={"muslim": 0.5, "christian": 0.1},
            dominant_religion=Religion.MUSLIM,
            confidence=0.5,
            source_ids=["hand_seed_v0"],
        )


def test_processed_anchors_validate() -> None:
    path = PROCESSED / "anchors.jsonl"
    assert path.is_file()
    for row in _load_jsonl(path):
        Anchor.model_validate(row)


def test_processed_edges_validate() -> None:
    path = PROCESSED / "edges.jsonl"
    assert path.is_file()
    for row in _load_jsonl(path):
        MigrationEdge.model_validate(row)


def test_processed_events_validate_and_link() -> None:
    events = [Event.model_validate(r) for r in _load_jsonl(PROCESSED / "events.jsonl")]
    edges = [MigrationEdge.model_validate(r) for r in _load_jsonl(PROCESSED / "edges.jsonl")]
    event_ids = {e.event_id for e in events}
    # Seeded triggers must remain; new events are allowed (subset, not equality —
    # the gate should fail on regression, not on adding a 4th event).
    assert {
        "lausanne_population_exchange_1923",
        "arab_israeli_war_1948",
        "iranian_revolution_1979",
    } <= event_ids
    for edge in edges:
        if edge.trigger_event_id:
            assert edge.trigger_event_id in event_ids
