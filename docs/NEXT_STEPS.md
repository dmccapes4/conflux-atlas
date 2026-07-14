# Next steps

Ordered for a working pygame slice, not a complete history.

## 1. Sources desk (this week)

- [x] Download Pew Global Religious Composition 2010 & 2020 (ingested).
- [x] Pull population totals for the v0 polity list — OWID → `population_totals.jsonl` (UN WPP xlsx still raw for later).
- [x] Capture Ottoman census summary tables into `data/raw/ottoman/` + wiki ingest → processed JSONL (cross-check Karpat still open).
- [x] Start `data/sources/BIBLIOGRAPHY.md` — every `source_id` used in JSON must appear there.

## 2. Normalize to anchors (before pygame)

- [x] Define religion + polity enums in `conflux/schema.py` (Pydantic or dataclasses).
- [x] Script: Pew CSV/XLS → `data/processed/anchors.jsonl` for MENA + diaspora countries of interest.
- [x] Hand seed: 12 polities × 1900 / 1950 / 2000 → `scripts/seed_historical_anchors.py` → `anchors_historical_seed.jsonl` (merged into `anchors.jsonl`).
- [x] Manual seed file: 10 migration edges → `scripts/seed_migration_edges.py` → `data/processed/edges.jsonl`.

## 3. Minimal engine (OGrE-shaped)

- [x] `conflux/model.py` — load anchors/events/edges; build runtime graph for year `Y`.
- [x] Interpolation policy: **hold + event delta** (no naive linear share morphing yet). *(v0: hold + edge fade viz; event-delta accounting deferred)*
- [x] `conflux/sim.py` — pygame loop: year scrubber, node size = pop, color = dominant religion, edge thickness = volume, alpha = confidence.
- [x] `requirements.txt` + `run.sh` + `main.py` (copy the ogre ergonomics: venv, one command launch).

## 4. First demo slice

- [x] Time window: **1900–2025** only.
- [x] ~12 polities (core MENA + Turkey + France/US diaspora stubs).
- [x] Narrate: Ottoman late censuses → WWI/mandates → 1948 migrations → late-20th-c displacements → Pew 2010/2020.

## 5. Explicitly later

- Pre-1800 backfill and dynamic polity lineage UI.
- Political organizations as overlays (PLO, MB, IRGC, …).
- Conversion-wave mechanics as continuous processes (vs event bursts).
- Recording/narration pipeline (steal from ogre when the loop is worth filming).

## Suggested first coding session

1. Lock enums + empty `anchors.jsonl` / `events.jsonl` / `edges.jsonl`.
2. Hand-enter Israel + Egypt + Turkey for 1900 / 1950 / 2000 / 2020 with rough pops + shares + confidence.
3. Draw three nodes in pygame and scrub the year. Ship that before any scraper.
