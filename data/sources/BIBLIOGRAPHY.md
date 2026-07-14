# Bibliography / source registry

Every `source_id` referenced in processed data must have a row here.

| source_id | title | url / citation | years covered | notes |
| --- | --- | --- | --- | --- |
| pew_global_religious_composition_2010_2020 | Dataset of Global Religious Composition Estimates for 2010 and 2020 | https://www.pewresearch.org/dataset/dataset-of-global-religious-composition-estimates-for-2010-and-2020/ | 2010, 2020 | **Ingested** → `anchors.jsonl` (402 country anchors). |
| hand_seed_v0 | Hand-compiled demo anchors (12 polities × 1900/1950/2000) | `scripts/seed_historical_anchors.py` | 1900, 1950, 2000 | Ballpark pops/shares for pygame slice; confidence 0.30–0.80. Israel@1900 = Ottoman Palestine geography. |
| hand_seed_edges_v0 | Hand-compiled demo migration edges | `scripts/seed_migration_edges.py` → `data/processed/edges.jsonl` | 1923–1985 | 10 edges (exchange, Jewish exodus, Nakba, Iran 1979). Volumes order-of-magnitude. |
| hand_seed_events_v0 | Hand-compiled demo events | `scripts/seed_events.py` → `data/processed/events.jsonl` | 1923, 1948, 1979 | 3 triggers linked to seeded edges (Lausanne, 1948 war, Iran 1979). |
| owid_population | Our World in Data — Population | https://ourworldindata.org/grapher/population | 1900–2023 | **Ingested** → `data/processed/population_totals.jsonl` (13 demo polities). Model overlays onto held shares. |
| ottoman_demographics_wiki | Demographics of the Ottoman Empire (Wikipedia bootstrap) | https://en.wikipedia.org/wiki/Demographics_of_the_Ottoman_Empire | 1520–1914 | **Ingested** → `ottoman_empire_population.jsonl` + `ottoman_1914_provinces.jsonl`. Cross-check vs Karpat. |
| un_wpp | UN World Population Prospects | https://population.un.org/wpp/ | 1950–2023 | **Ingested** Estimates → `population_totals_wpp.jsonl` (18 polities × annual). |
| karpat_ottoman_population_1830_1914 | Karpat, *Ottoman Population 1830–1914* | PDF in `data/raw/ottoman/` | 1830–1914 | **Partial ingest** → `karpat_religious_structure_summary.jsonl` (Table 4.3). Full appendix tables still OCR-hard. |
| seda_basihos_ottoman_population_2016 | Basihos, Ottoman population paper (2016/2018) | PDF in `data/raw/ottoman/` | 1520–1927 | **Ingested** → `basihos_turkey_borders_population.jsonl` (modern Turkey borders). |
| mccarthy_armenian_pop_ottoman | McCarthy, Armenian population in the Ottoman Empire | PDF in `data/raw/ottoman/` | late Ottoman | **Partial ingest** → `mccarthy_six_vilayets_religion.jsonl` (Table One; contested). |
| cambridge_history_of_turkey | *Cambridge History of Turkey* | PDF in `data/raw/books/` | longue durée | Narrative context, not share anchors |
| cambridge_history_of_islam_1970 | *Cambridge History of Islam* — Central Islamic Lands (1970) | PDF in `data/raw/books/` | pre-Islamic–WWI | Narrative |
| cambridge_history_of_christianity | *Cambridge History of Christianity* (9 vols) | PDFs in `data/raw/books/` | longue durée | Full Vols **1–5, 7–9**. Vol **6** is 18pp SAMPLE only (need *Reform and Expansion 1500–1660*). Priority for Conflux: 5, 8, 9. |
| jizya_islamic_law_concept | Concept of Jizyah under Islamic Law | PDF in `data/raw/books/` | classical–modern | Dhimmi / tax proxy — low confidence |
| jizya_modern_state | Jizya in the Modern State | PDF in `data/raw/books/` | modern | Same caveat |
| jewishdatabank_world_jewish_population | World Jewish Population (AJYB / DellaPergola series) | https://www.jewishdatabank.org/databank/search-results?search=world+jewish+population | ~1920s–2024 | **Cataloged** + **partial ingest** → `wjp_world_core_jewish_population.jsonl` (Table 1) + `wjp_country_core_jewish_population.jsonl` (2023 appendix + 1970 Shapiro). |
| un_desa_ims | UN DESA International Migrant Stock | https://www.un.org/development/desa/pd/content/international-migrant-stock | 1990–2024 | **Ingested** destination → `un_desa_migrant_stock_destination.jsonl`; **OD** → `un_desa_migrant_stock_od.jsonl` (demo polity pairs). |
| unhcr_population_api | UNHCR Refugee Statistics API | https://api.unhcr.org/population/v1/population/ | 1975–2024 | **Ingested** → `unhcr_refugee_stock_by_coa.jsonl` (COA stock) + **tranche-1** `unhcr_syria_refugee_stock_od.jsonl` (coo=SYR × host, 2011–2024). |
| beacon_tranche1_v0 | Beacon tranche-1 event/edge seed | `scripts/seed_beacon_tranche1.py` | 1975–2024 | Syria 2011 + Lebanon 1975 events; UNHCR OD + Labaki destination edges; Iran→Israel deepen. |
| labaki_abu_rjaili_2005 | Labaki & Abu-Rjaili — Lebanese emigration tables (via Tabar 2010) | PDF in `data/raw/beacons/lebanese_civil_war_1975_1990/` | 1975–1990 | **Partial** early-war destination edges; gate caution on confessional mix. |
| shaw_ottoman_census_system_1978 | Shaw — Ottoman census system and population 1831–1914 | PDF in `data/raw/beacons/ottoman_tanzimat_1800_1914/` | 1831–1914 | Downloaded open PDF; not yet table-extracted into anchors. |
| scpr_forced_dispersion_2016 | SCPR — Forced Dispersion demographic report | PDF in `data/raw/beacons/syrian_civil_war_refugees_2011_present/` | 2011–2014 | Downloaded; key-informant design → caution if used as validation. |
| idmc_syria_idp | IDMC — Syria IDP figure analysis | PDF in `data/raw/beacons/syrian_civil_war_refugees_2011_present/` | 2011– | Downloaded; not yet processed into jsonl. |
| arda_national_profiles_2005 | ARDA National Profiles, 2005 Update | https://www.thearda.com/ | ~2005 | **Ingested** → `arda_national_profiles_2005.jsonl` (WCD counts; conf capped; diverges from Pew). |
| world_bank_sp_pop_totl | World Bank SP.POP.TOTL | https://data.worldbank.org/indicator/SP.POP.TOTL | 1960–2025 | **Ingested** → `population_totals_worldbank.jsonl` (cross-check vs OWID). |
| pcbs_population | Palestinian Central Bureau of Statistics | https://www.pcbs.gov.ps/ | 2017–2026 | **Ingested** projections → `pcbs_projected_population.jsonl`; other indicator xlsx still raw. |
| cbs_population_madaf | CBS — Population & growth components in localities / statistical areas | https://www.cbs.gov.il/he/publications/Pages/2017/אוכלוסייה-ומרכיבי-גידול-ביישובים-ובאזורים-סטטיסטיים-2017.aspx | 2019–2024 | **Cataloged** + **partial ingest** → `cbs_israel_population_groups.jsonl` (national Jews/Arabs/Others). Locality microdata still raw. |
| arab_barometer | Arab Barometer microdata (English) | https://www.arabbarometer.org/survey-data/data-downloads/ | Waves II–VIII | **Cataloged** + **partial ingest** → `arab_barometer_religion_shares.jsonl` (Q1012 country×wave; conf 0.40). |
| mevs_middle_eastern_values_study | Middle Eastern Values Study (Moaddel et al.) | https://mevs.org/research/data/ | ~2000–2015 surveys | **Cataloged** → `mevs_file_catalog.jsonl` (2 real microdata files; many PDF stubs). |

See also `docs/DATA_SOURCES.md` for the full hunt list and `docs/STRATEGY_V0.2.md` for the publishable-path plan (v0.1 kept in `docs/STRATEGY.md` for provenance).

Download URL contracts (offline pytest): `data/sources/CANONICAL_URLS.json` — update with scripts when hosts move files.

Add rows as files land in `data/raw/`.
