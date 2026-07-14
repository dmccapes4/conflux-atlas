"""Conflux Atlas v0 schema — anchors, polities, migrations, events."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Religion(str, Enum):
    CHRISTIAN = "christian"
    MUSLIM = "muslim"
    UNAFFILIATED = "unaffiliated"
    BUDDHIST = "buddhist"
    HINDU = "hindu"
    JEWISH = "jewish"
    OTHER = "other"


# Pew CSV column → Religion
PEW_RELIGION_COLUMNS: dict[str, Religion] = {
    "Christians": Religion.CHRISTIAN,
    "Muslims": Religion.MUSLIM,
    "Religiously_unaffiliated": Religion.UNAFFILIATED,
    "Buddhists": Religion.BUDDHIST,
    "Hindus": Religion.HINDU,
    "Jews": Religion.JEWISH,
    "Other_religions": Religion.OTHER,
}


class YearPrecision(str, Enum):
    EXACT = "exact"
    DECADE = "decade"
    CENTURY = "century"
    RANGE = "range"


class MigrationKind(str, Enum):
    VOLUNTARY = "voluntary"
    REFUGEE = "refugee"
    EXPULSION_OR_FLIGHT = "expulsion_or_flight"
    SETTLEMENT_POLICY = "settlement_policy"
    CONQUEST_ELITE = "conquest_elite"
    CONVERSION_WAVE = "conversion_wave"
    OTHER = "other"


class Anchor(BaseModel):
    """Cited demographic snapshot for a polity at a year."""

    anchor_id: str
    polity_id: str
    year: int
    year_precision: YearPrecision = YearPrecision.EXACT
    total_population: int = Field(ge=0)
    shares: dict[str, float]
    dominant_religion: Religion
    regime: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_ids: list[str]
    notes: str = ""
    # Provenance helpers (optional; keep Pew codes for joins)
    display_name: str | None = None
    region: str | None = None
    country_code: str | None = None
    counts: dict[str, int] | None = None

    @field_validator("shares")
    @classmethod
    def _known_religions(cls, v: dict[str, float]) -> dict[str, float]:
        allowed = {r.value for r in Religion}
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(f"unknown religion keys: {sorted(unknown)}")
        for k, x in v.items():
            if not 0.0 <= x <= 1.0 + 1e-9:
                raise ValueError(f"share out of range for {k}: {x}")
        return v

    @model_validator(mode="after")
    def _shares_sum(self) -> Anchor:
        s = sum(self.shares.values())
        if abs(s - 1.0) > 0.02:
            raise ValueError(f"shares sum to {s}, expected ~1.0")
        return self


class MigrationEdge(BaseModel):
    """Directed migration / displacement burst between polities."""

    edge_id: str
    year_start: int
    year_end: int
    from_polity: str
    to_polity: str
    group: Religion
    volume_est: int = Field(ge=0)
    volume_low: int | None = Field(default=None, ge=0)
    volume_high: int | None = Field(default=None, ge=0)
    kind: MigrationKind
    trigger_event_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_ids: list[str]
    notes: str = ""

    @model_validator(mode="after")
    def _years_and_band(self) -> MigrationEdge:
        if self.year_end < self.year_start:
            raise ValueError("year_end must be >= year_start")
        if self.from_polity == self.to_polity:
            raise ValueError("from_polity and to_polity must differ")
        low = self.volume_low if self.volume_low is not None else self.volume_est
        high = self.volume_high if self.volume_high is not None else self.volume_est
        if not low <= self.volume_est <= high:
            raise ValueError("volume_est must lie within [volume_low, volume_high]")
        return self


class EventEffectType(str, Enum):
    MIGRATION_BURST = "migration_burst"
    CONFIDENCE_RESET = "confidence_reset"
    OTHER = "other"


class EventEffect(BaseModel):
    type: EventEffectType
    edge_id: str | None = None
    polity_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class Event(BaseModel):
    """Discrete historical trigger linked to migration edges / confidence resets."""

    event_id: str
    year: int
    year_end: int | None = None
    title: str
    affected_polities: list[str] = Field(default_factory=list)
    effects: list[EventEffect] = Field(default_factory=list)
    source_ids: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""

    @model_validator(mode="after")
    def _year_end(self) -> Event:
        if self.year_end is not None and self.year_end < self.year:
            raise ValueError("year_end must be >= year")
        return self


def slugify_country(name: str) -> str:
    """Stable polity_id from Pew Country label."""
    s = name.strip().lower()
    for old, new in (
        (" ", "_"),
        ("-", "_"),
        ("'", ""),
        (".", ""),
        (",", ""),
        ("(", ""),
        (")", ""),
    ):
        s = s.replace(old, new)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def shares_from_pew_percent_row(row: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for col, rel in PEW_RELIGION_COLUMNS.items():
        out[rel.value] = float(row[col]) / 100.0
    return out


def dominant_from_shares(shares: dict[str, float]) -> Religion:
    key = max(shares, key=shares.get)  # type: ignore[arg-type]
    return Religion(key)


def parse_int_count(raw: str | int | float | None) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw).strip().replace(",", "").replace("<", "").replace(">", "")
    if not s or s.lower() in {"na", "n/a", "-"}:
        return 0
    return int(float(s))
