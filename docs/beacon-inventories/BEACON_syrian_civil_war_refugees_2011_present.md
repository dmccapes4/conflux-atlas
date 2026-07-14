# Beacon inventory — Syrian Civil War & Regional Refugee Crisis

**beacon_id:** `syrian_civil_war_refugees_2011_present`  
**Years:** 2011–present  
**Priority:** very_high  
**Status:** inventory  
**Linked events:** *(none yet)*

## Candidate sources

| source_id (proposed) | citation | url / handle | years | data type | gate | demographic payload |
| --- | --- | --- | --- | --- | --- | --- |
| `unhcr_syria_situation_portal` | UNHCR — Syria Regional Refugee Response situation portal | https://data.unhcr.org/en/situations/syria | 2011–present | volumes | accept | Host-country POC totals; resettlement + self-organized return series |
| `unhcr_refugee_statistics_methodology` | UNHCR — Refugee Data Finder methodology + API (COO×COA) | https://www.unhcr.org/refugee-statistics/methodology | 1951–present | methods / volumes | accept | Stock by origin×asylum; `coo=SYR` filter for Syria-outflow series |
| `unhcr_hdx_population_world` | HDX — UNHCR population data for world (COO×COA) | https://data.humdata.org/dataset/unhcr-population-data-for-world | 1951–present | volumes | accept | Full origin–destination refugee stock — fixes desk COA-only gap |
| `idmc_syria_idp` | IDMC — Syria IDP figure analysis / GRID methodology | IDMC figure-analysis PDF | 2011–present | volumes | accept | Syria IDP stock; new-displacement vs stock distinction |
| `scpr_forced_dispersion_2016` | SCPR — *Forced Dispersion: Syrian Human Status, Demographic Report 2016* | https://scpr-syria.org/publications/forced-dispersion-syrian-human-status-the-demographic-report-2016/ | 2011–2014 | totals / methods | caution | Population Status Survey 2014; key-informant design |
| `scpr_displacement_determinants` | SCPR — “Determinants of forced displacement in the Syrian conflict” | SCPR PDF | 2014 | methods / volumes | caution | Governorate-level displacement correlates |
| `jordan_dos_census_2015` | Jordan Dept. of Statistics — General Population & Housing Census 2015 | DOS Census 2015 Eng PDF | 2015 | totals | accept | **1.3M Syrians** in Jordan; **953,289** classified refugees |
| `unhcr_vasyr_lebanon` | UNHCR/UNICEF/WFP — VASyR Lebanon | UNHCR microdata catalog | 2013–present | shares / methods | accept | Annual cluster sample on registered refugees; age/sex/governorate |
| `afad_syrian_refugees_turkey_2013` | Turkey AFAD — Survey on Syrian Refugees in Turkey | ReliefWeb AFAD 2013 PDF | 2013 | shares / methods | accept | Camp + urban household survey demographic profile |
| `erf_jordan_syrian_refugee_triangulation` | ERF — Census vs UNHCR vs JLMPS triangulation | ERF working paper 1288 | 2015–2016 | methods | caution | Documents universe mismatch: UNHCR registered ⊂ census Syrians |
| `world_bank_ieg_refugee_shock` | World Bank IEG — Lebanon/Jordan refugee shock evaluation | IEG PDF | 2011–2015 | volumes | caution | Aggregate displacement + host government estimates vs UNHCR registered |

## Open PDFs

- `unhcr_refugee_statistics_methodology` — https://popdata.unhcr.org/ASR_instructions.pdf
- `idmc_syria_idp` — https://api.internal-displacement.org/sites/default/files/2021-05/figure-analysis-syr.pdf
- `idmc_syria_spotlight_2019` — https://api.internal-displacement.org/sites/default/files/publications/documents/2019-IDMC-GRID-spotlight-syria.pdf
- `idmc_grid_2024` — https://disasterdisplacement.org/wp-content/uploads/2024/07/IDMC-GRID-2024-Global-Report-on-Internal-Displacement-2.pdf
- `scpr_forced_dispersion_2016` — https://scpr-syria.org/wp-content/uploads/2024/08/Forced_Dispersion_A_Demographic_Report_En.pdf
- `scpr_displacement_determinants` — https://scpr-syria.org/wp-content/uploads/2024/08/SCPR_The-determinants-of-forced-displacement-in-the-Syrian-conflict_EN.pdf
- `jordan_dos_census_2015` — http://dosweb.dos.gov.jo/wp-content/uploads/2017/08/Census2015_Eng.pdf
- `afad_syrian_refugees_turkey_2013` — https://reliefweb.int/attachments/69f0839d-daae-31c2-80d5-89addf050c40/AFADSurveyonSyrianRefugeesinTurkey2013.pdf
- `erf_jordan_syrian_refugee_triangulation` — https://erf.org.eg/app/uploads/2019/02/1288.pdf
- `world_bank_lbn_esia_summary` — https://www.worldbank.org/content/dam/Worldbank/document/MNA/LBN-ESIA%20of%20Syrian%20Conflict-%20EX%20SUMMARY%20ENGLISH.pdf
- `unhcr_vasyr_2024_exec_summary` — https://ialebanon.unhcr.org/vasyr/files/vasyr_reports/vasyr-2024-executive-summary.pdf
- `scpr_forced_dispersion_press_release` — https://scpr-syria.org/wp-content/uploads/2024/08/SCPR_Forced_Dispersion_PressRelease_En-1.pdf
- `jordan_dos_census_2015_main_result` — http://www.dos.gov.jo/dos_home_e/main/population/census2015/Main_Result.pdf
- `unhcr_vasyr_2018` — https://reliefweb.int/attachments/7e3380ea-2b5d-3bb1-a445-4f33f1549b0b/VASyR-2018.pdf
- `unhcr_syria_registered_stats_2015` — https://reliefweb.int/attachments/3c50ee7f-2ffa-3ab0-81ce-c1735015c37e/ExternalStatisticalReportonUNHCRRegisteredSyriansasof31December2015.pdf

## Already on the desk

- `unhcr_refugee_stock_by_coa.jsonl` — Lebanon/Jordan/Turkey COA stocks + Syria IDPs; **no COO**
- `un_desa_migrant_stock_od.jsonl` — Syria→Lebanon/Jordan/Germany pairs present; Turkey may be partial
- Population totals for host denominators

## Gaps / next ingest actions

- **#1:** refetch UNHCR/HDX with `coo=SYR` → Syria-origin×host annual edges
- Ingest IDMC annual Syria IDP series (stock + new displacement)
- SCPR 2014 annex tables → governorate IDP/resident counts (conf ~0.55)
- Jordan Census 2015 microtables; VASyR microdata; Turkey DGMM registration series
- Seed `syrian_civil_war_2011` event once COO×COA edges land

**Skipped (REJECT):** Situation-portal widgets without methodology; ReliefWeb headlines; IEMed policy briefs without tables; Quora/Reddit/Twitter; Wikipedia; AI stat farms; UN News without annex.
