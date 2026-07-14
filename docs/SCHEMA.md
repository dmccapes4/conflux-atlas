# Data model (v0)

## Anchor snapshot (source of truth)

One row = one cited estimate for a polity at a year (or year range midpoint).

```json
{
  "anchor_id": "pew_israel_2020",
  "polity_id": "israel",
  "year": 2020,
  "year_precision": "exact",
  "total_population": 8800376,
  "shares": {
    "christian": 0.019,
    "muslim": 0.147,
    "unaffiliated": 0.044,
    "buddhist": 0.0,
    "hindu": 0.002,
    "jewish": 0.770,
    "other": 0.018
  },
  "dominant_religion": "jewish",
  "regime": null,
  "confidence": 0.92,
  "source_ids": ["pew_global_religious_composition_2010_2020"],
  "notes": "",
  "display_name": "Israel",
  "region": "Middle East-North Africa",
  "country_code": "376",
  "counts": {"jewish": 6780636, "muslim": 1296427}
}
```

Religion keys match Pew’s seven categories. `shares` values should sum to 1.0 within a small epsilon; validation fails otherwise.

**Ingested:** `scripts/ingest_pew.py` → `data/processed/anchors.jsonl` (402 Level-1 country anchors for 2010 and 2020).

**Hand seed:** `scripts/seed_historical_anchors.py` → 36 anchors (12 polities × 1900/1950/2000), merged into the same `anchors.jsonl` (`source_id`: `hand_seed_v0`).

## Polity registry

```json
{
  "polity_id": "ottoman_empire",
  "display_name": "Ottoman Empire",
  "valid_from": 1299,
  "valid_to": 1922,
  "succeeds": ["rum_sultanate"],
  "succeeded_by": ["turkey", "syria", "iraq", "lebanon", "palestine_mandate", "..."],
  "geo_region_ids": ["anatolia", "levant", "balkans", "egypt"]
}
```

## Migration edge

```json
{
  "edge_id": "iraq_jewish_exodus_1950s",
  "year_start": 1948,
  "year_end": 1951,
  "from_polity": "iraq",
  "to_polity": "israel",
  "group": "jewish",
  "volume_est": 120000,
  "volume_low": 110000,
  "volume_high": 130000,
  "kind": "expulsion_or_flight",
  "trigger_event_id": "arab_israeli_war_1948",
  "confidence": 0.65,
  "source_ids": ["hand_seed_edges_v0"],
  "notes": "…"
}
```

`kind` enum (v0): `voluntary`, `refugee`, `expulsion_or_flight`, `settlement_policy`, `conquest_elite`, `conversion_wave`, `other`.

**Seeded:** `scripts/seed_migration_edges.py` → `data/processed/edges.jsonl` (10 edges). Pydantic model: `MigrationEdge` in `conflux/schema.py`.

**Seeded:** `scripts/seed_events.py` → `data/processed/events.jsonl` (3 events). Pydantic model: `Event` in `conflux/schema.py`.

```json
{
  "event_id": "lausanne_population_exchange_1923",
  "year": 1923,
  "year_end": 1924,
  "title": "Lausanne compulsory population exchange (Greece–Turkey)",
  "affected_polities": ["turkey", "greece"],
  "effects": [
    {"type": "migration_burst", "edge_id": "greco_turkish_christians_1923"},
    {"type": "confidence_reset", "polity_id": "turkey", "confidence": 0.55}
  ],
  "source_ids": ["hand_seed_events_v0"],
  "confidence": 0.85
}
```

## Runtime node (derived, for pygame)

Built each tick from anchors + applied events — **not** hand-authored for every year.

```json
{
  "polity_id": "israel",
  "year": 2026,
  "total_population": 9500000,
  "shares": {"jewish": 0.74, "muslim": 0.18, "christian": 0.02, "other": 0.06},
  "confidence": 0.9,
  "display_name": "Israel"
}
```

## Confidence rules (draft)

- New anchor from a strong modern source → set high (e.g. 0.85–0.98).
- Between anchors with no event → gentle decay toward a floor (do not invent precision).
- Event with weak volume estimates → raise *structural* confidence that *something* moved; keep volume confidence separate if needed later.
- Pre-1500 default floor ≈ 0.2–0.4 unless a specialist source supports higher.
