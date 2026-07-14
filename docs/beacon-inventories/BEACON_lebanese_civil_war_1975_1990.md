# Beacon inventory — Lebanese Civil War

**beacon_id:** `lebanese_civil_war_1975_1990`  
**Years:** 1975–1990  
**Priority:** high  
**Status:** inventory  
**Linked events:** *(none yet)*

## Candidate sources

| source_id (proposed) | citation | url / handle | years | data type | gate | demographic payload |
| --- | --- | --- | --- | --- | --- | --- |
| `labaki_abu_rjaili_2005` | Labaki, Boutros & Abu-Rjaili, Khalil — *L’émigration libanaise: données et analyses* (2005); cited via Tabar (2010) | http://data.infopro.com.lb/file/LebanonaCountryofEmigrationandImmigration2010PaulTabar.pdf | 1975–1990 | volumes | caution | Net emigration Apr 1975–Apr 1977: **272,500**; destination breakdown; war-total estimates **680k–990k** |
| `verdeil_ifpo_internal_migration` | Verdeil, Éric — “Internal Migration and Spatial Change” (*Beyrouth et ses urbanistes*, IFPO, 2019) | https://doi.org/10.4000/books.ifpo.13222 | 1975–1990 | volumes | accept | **~⅔** of Lebanese changed residence 1975–1990; **~⅓** did not return post-war |
| `unrwa_statistics_bulletin` | UNRWA — Statistics Bulletin / registration system | https://www.unrwa.org/what-we-do/eligibility-registration | 1948–present | totals | accept | Registered Palestine refugees in Lebanon; camp vs non-camp shares |
| `irfan_jprs_unrwa_lebanon` | Irfan, N. — “Palestinian refugees and ‘Lebanese exceptionalism’” (*Journal of Palestine Studies*, 2017) | UCL Discovery PDF | 1950–2014 | shares / methods | accept | UNRWA Lebanon camp-residence share vs Jordan — deprivation proxy |
| `michalak_palestinians_civil_war_1975` | Michalak, T. — “The Palestinians and the Outbreak of Civil War in Lebanon (1975)” | SAV journal PDF | 1970–1975 | methods / volumes | accept | PLO after 1970 Jordan expulsion; Shiite displacement from south |
| `hanafi_rsc_no_refuge_2010` | Hanafi, S. — “No refuge: Palestinians in Lebanon” (RSC Working Paper 64) | Oxford RSC PDF | 1975–2009 | totals | caution | Lebanon Palestinian estimate **~400,000**; UNRWA registered **425,640** |
| `cmi_lebanon_migration_policy` | Chr. Michelsen Inst. — Lebanon migration policy brief (synthesizes Labaki) | https://www.cmi.no/publications/8589-national-and-international-migration-policy-in-lebanon | 1865–2020 | volumes | caution | Civil-war wave **680k–990k** emigrants; triangulates Labaki/Tabar |
| `fisk_pity_the_nation_1990` | Fisk, Robert — *Pity the Nation* (1990) | needs_access (ISBN 0-684-19363-0) | 1975–1990 | context | caution | Narrative displacement chronology; no replicable volume tables |

## Open PDFs

- `labaki_abu_rjaili_2005` — http://data.infopro.com.lb/file/LebanonaCountryofEmigrationandImmigration2010PaulTabar.pdf
- `tabar_2010` — http://data.infopro.com.lb/file/LebanonaCountryofEmigrationandImmigration2010PaulTabar.pdf
- `unrwa_statistics_bulletin` — https://reliefweb.int/attachments/ec5eda81-fad5-327a-b0aa-8e702c1918f6/unrwa_in_figures_2018_eng_v1_31_1_2019_final.pdf
- `irfan_jprs_unrwa_lebanon` — https://discovery.ucl.ac.uk/id/eprint/10170515/3/Irfan_Palestinian%20Refugees%20JPRS%20article_July%202017.pdf
- `michalak_palestinians_civil_war_1975` — https://www.sav.sk/journals/uploads/112415016_Michalak.pdf
- `hanafi_rsc_no_refuge_2010` — https://www.rsc.ox.ac.uk/files/files-1/wp64-no-refuge-2010.pdf
- `labaki_mpra_19219` — https://mpra.ub.uni-muenchen.de/19219/1/MPRA_paper_19219.pdf
- `labaki_undesa_egm_2006` — https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/200605_egm_paper13_labaki.pdf
- `verdeil_ifpo_sommaire_cco_49` — https://ifporient.org/wp-content/uploads/2019/05/sommaire_CCO_49.pdf

No open path-ending-`.pdf` found for Verdeil IFPO chapter or CMI 8589 (HTML shell).

## Already on the desk

- `unhcr_population_api` — Lebanon COA stock from 1976; no COO; do not treat as Lebanese emigration
- `un_desa_ims` — Lebanon stocks from 1990 only (post-war)
- WJP Lebanon Jewish 3,000 (1970); Nakba-era edges touch Lebanon; no civil-war edges yet

## Gaps / next ingest actions

- Ingest Labaki/Abu-Rjaili 1975–1977 destination tables as edges
- Verdeil IFPO → internal-displacement volume anchors
- UNRWA Statistics Bulletin annual Lebanon registration 1970–1990
- Christian emigration shares still missing — destination-country census microdata
- Seed `lebanese_civil_war_1975` event once volumes land

**Skipped (REJECT):** Wikipedia casualty summaries; Reddit diaspora threads; Holy See diaspora range without methods; MigrationPolicy.org journalism rehash; AI listicles.
