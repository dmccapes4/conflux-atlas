# Conflux Atlas — Data Validation Report

- **Generated (UTC):** 2026-07-14T10:22:54.379696+00:00
- **Verdict:** **PASS**
- **Counts:** PASS=27 · FAIL=0 · WARN=0 · INFO=1
- **Processed dir:** `data/processed`

## Checks

| Status | Check | Detail |
| --- | --- | --- |
| PASS | `bibliography` | 24 source_ids registered |
| PASS | `file:anchors.jsonl` | 438 rows (min 400) — Pew (+ merged hand seeds) religion-share anchors |
| PASS | `file:anchors_historical_seed.jsonl` | 36 rows (min 30) — Hand historical seed (pre-merge copy) |
| PASS | `file:edges.jsonl` | 10 rows (min 8) — Hand-seeded migration edges |
| PASS | `file:events.jsonl` | 3 rows (min 3) — Event triggers linked to edges |
| PASS | `file:population_totals.jsonl` | 1612 rows (min 1000) — OWID population totals |
| PASS | `file:population_totals_wpp.jsonl` | 1332 rows (min 1000) — UN WPP population totals |
| PASS | `file:population_totals_worldbank.jsonl` | 1158 rows (min 800) — World Bank SP.POP.TOTL |
| PASS | `file:unhcr_refugee_stock_by_coa.jsonl` | 1079 rows (min 500) — UNHCR COA refugee stock |
| PASS | `file:un_desa_migrant_stock_destination.jsonl` | 144 rows (min 100) — UN DESA destination stock |
| PASS | `file:un_desa_migrant_stock_od.jsonl` | 1757 rows (min 1000) — UN DESA dest×origin stock |
| PASS | `file:wjp_world_core_jewish_population.jsonl` | 17 rows (min 10) — WJP world CJP series |
| PASS | `file:wjp_country_core_jewish_population.jsonl` | 176 rows (min 100) — WJP country CJP |
| PASS | `file:arab_barometer_religion_shares.jsonl` | 64 rows (min 40) — AB Q1012 survey shares |
| PASS | `file:arda_national_profiles_2005.jsonl` | 238 rows (min 100) — ARDA 2005 national profiles |
| PASS | `file:cbs_israel_population_groups.jsonl` | 6 rows (min 4) — CBS Israel group totals |
| PASS | `file:pcbs_projected_population.jsonl` | 10 rows (min 8) — PCBS Palestine projections |
| PASS | `file:ottoman_empire_population.jsonl` | 8 rows (min 5) — Ottoman wiki empire series |
| PASS | `file:ottoman_1914_provinces.jsonl` | 34 rows (min 20) — Ottoman 1914 provinces |
| PASS | `file:karpat_religious_structure_summary.jsonl` | 4 rows (min 3) — Karpat Table 4.3 |
| PASS | `file:basihos_turkey_borders_population.jsonl` | 16 rows (min 10) — Basihos Turkey-border pops |
| PASS | `file:mccarthy_six_vilayets_religion.jsonl` | 2 rows (min 2) — McCarthy Six Vilayets |
| PASS | `schema:anchors` | all 438 Anchor-valid |
| PASS | `schema:edges` | all 10 MigrationEdge-valid |
| PASS | `schema:events` | all 3 Event-valid |
| PASS | `edge→event` | 9 edges with triggers; all resolve in events.jsonl |
| PASS | `source_ids→bib` | all 18 referenced source_ids registered |
| INFO | `engine_wiring` | model.py mentions: ['OWID/WPP overlays', 'event-delta flag', 'WPP totals', 'WJP CJP', 'DESA OD', 'events'] |

## Shape of the data

| File | Rows | Notes |
| --- | ---: | --- |
| `anchors.jsonl` | 438 | years 1900–2020 |
| `anchors_historical_seed.jsonl` | 36 | years 1900–2000 |
| `arab_barometer_religion_shares.jsonl` | 64 | years 2011–2024 |
| `arda_national_profiles_2005.jsonl` | 238 | years 2005–2005 |
| `basihos_turkey_borders_population.jsonl` | 16 | years 1520–1927 |
| `cbs_israel_population_groups.jsonl` | 6 | years 2019–2024 |
| `edges.jsonl` | 10 | years 1923–1979 |
| `events.jsonl` | 3 | years 1923–1979 |
| `karpat_religious_structure_summary.jsonl` | 4 | years 1825–1895 |
| `mccarthy_six_vilayets_religion.jsonl` | 2 | years 1913–1914 |
| `ottoman_1914_provinces.jsonl` | 34 | years 1914–1914 |
| `ottoman_empire_population.jsonl` | 8 | years 1520–1919 |
| `pcbs_projected_population.jsonl` | 10 | years 2017–2026 |
| `population_totals.jsonl` | 1612 | years 1900–2023 |
| `population_totals_worldbank.jsonl` | 1158 | years 1960–2025 |
| `population_totals_wpp.jsonl` | 1332 | years 1950–2023 |
| `un_desa_migrant_stock_destination.jsonl` | 144 | years 1990–2024 |
| `un_desa_migrant_stock_od.jsonl` | 1757 | years 1990–2024 |
| `unhcr_refugee_stock_by_coa.jsonl` | 1079 | years 1975–2024 |
| `wjp_country_core_jewish_population.jsonl` | 176 | years 1970–2023 |
| `wjp_world_core_jewish_population.jsonl` | 17 | years 1880–2023 |

### Anchor density (top polities)

| polity_id | n_anchors |
| --- | ---: |
| `egypt` | 5 |
| `france` | 5 |
| `iran` | 5 |
| `iraq` | 5 |
| `israel` | 5 |
| `lebanon` | 5 |
| `morocco` | 5 |
| `saudi_arabia` | 5 |
| `syria` | 5 |
| `turkey` | 5 |
| `united_states` | 5 |
| `yemen` | 5 |

Distinct polities: **201**. Year histogram: {1900: 12, 1950: 12, 2000: 12, 2010: 201, 2020: 201}

### Inter-anchor gaps (demo slice)

| polity_id | years | gaps (Δy) | max_gap |
| --- | --- | --- | ---: |
| `egypt` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `france` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `iran` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `iraq` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `israel` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `lebanon` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `morocco` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `saudi_arabia` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `syria` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `turkey` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `united_states` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |
| `yemen` | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 |

Anchor confidence: n=438 min=0.30 median=0.85 max=0.92

## Notes

- Schema checks apply to `anchors.jsonl`, `edges.jsonl`, `events.jsonl` (Pydantic `Anchor` / `MigrationEdge` / `Event`).
- Overlay series (WJP, DESA, UNHCR, …) are presence + JSON-parse validated; they are not yet required to validate as full `Anchor` records.
- A PASS here means the *data desk* is coherent. Engine wiring (events/edges mutating node state) is a separate concern — see STRATEGY / technical review.

