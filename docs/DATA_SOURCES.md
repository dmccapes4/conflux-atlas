# Where to find more data

Pew 2010/2020 is ingested. Use this list to extend Conflux backward and sideways.

## Population totals (modern)

| Source | URL | Notes |
| --- | --- | --- |
| **UN World Population Prospects** | https://population.un.org/wpp/ | Best annual/5-year totals; Pew already used 2024 revision for 2010/2020 pops |
| **World Bank API** | https://data.worldbank.org/indicator/SP.POP.TOTL | Easy programmatic totals by country |
| **Our World in Data — population** | https://ourworldindata.org/population-growth | Charts + downloadable; good for quick checks |

## Religious composition (modern / near-modern)

| Source | URL | Notes |
| --- | --- | --- |
| **Pew Global Religious Futures** | https://www.pewresearch.org/religion/ | Parent project; reports + earlier composition datasets |
| **Pew 2010 global religious landscape** | Search Pew site for 2012 “Global Religious Landscape” | Earlier snapshot if you want a third modern point |
| **ARDA (Association of Religion Data Archives)** | https://www.thearda.com/ | National Profiles 2005 → `data/raw/arda/` |
| **World Religion Database (WRD)** | https://worldreligiondatabase.org/ | Academic; often institutional access |
| **Jewish Data Bank — World Jewish Population (AJYB)** | https://www.jewishdatabank.org/databank/search-results?search=world+jewish+population | **Ingested** Table 1 world + 2023/1970 country CJP → `wjp_*.jsonl`. Scripts: `ingest_wjp.py`. |

## Ottoman & late imperial (high priority for 1800–1922)

| Source | URL | Notes |
| --- | --- | --- |
| **Karpat, Ottoman Population 1830–1914** | PDF in `data/raw/ottoman/` | **Partial ingest** Table 4.3 → `karpat_religious_structure_summary.jsonl`. Appendices still hard. |
| **Basihos 2016/2018 (Turkey borders)** | PDF in `data/raw/ottoman/` | **Ingested** → `basihos_turkey_borders_population.jsonl`. |
| **McCarthy Ottoman Armenians** | PDF in `data/raw/ottoman/` | **Partial ingest** Six Vilayets Table One → `mccarthy_six_vilayets_religion.jsonl` (contested). |
| **Demographics of the Ottoman Empire (tables)** | https://en.wikipedia.org/wiki/Demographics_of_the_Ottoman_Empire | Bootstrap: `scripts/scrape_ottoman_wiki.py` → `data/raw/ottoman/wiki/` |
| **Cambridge History of Turkey / Islam** | Institutional | Qualitative + tables for conversion/millet context |

## Migration & diaspora volumes

| Source | URL | Notes |
| --- | --- | --- |
| **UNHCR Refugee Statistics API** | https://api.unhcr.org/population/v1/population/ | **Fetched** → `data/raw/unhcr/` via `scripts/fetch_unhcr_api.py` (web CSV download is Cloudflare-gated) |
| **UN DESA International Migrant Stock** | https://www.un.org/development/desa/pd/content/international-migrant-stock | **Downloaded** → `data/raw/un_desa_migrant_stock/`. Destination + OD ingested. |
| **Israel CBS** | https://www.cbs.gov.il/he/publications/Pages/2017/אוכלוסייה-ומרכיבי-גידול-ביישובים-ובאזורים-סטטיסטיים-2017.aspx | **Downloaded** (~110 files, ~50M) → `data/raw/cbs/population_madaf/` |
| **PCBS** | https://www.pcbs.gov.ps/ | **Downloaded** → `data/raw/pcbs/` |
| **Historical Jewish expulsions / exodus** | Jewish Data Bank + syntheses | Seed edges by hand from WJP PDFs / academic tables |

Bulk script: `bash scripts/download_migration_sources.sh` (notes in `data/raw/MIGRATION_DOWNLOAD_NOTES.txt`).

## Pre-modern / sparse (low confidence by design)

| Source | URL | Notes |
| --- | --- | --- |
| **Harvard Dataverse** | https://dataverse.harvard.edu/ | No single MENA demography dump — search per study |
| **Our World in Data — population** | https://ourworldindata.org/grapher/population | **Downloaded** CSV; religion grapher slug currently 404 (use Pew) |
| **Cambridge History of Turkey / Islam / Christianity** | PDFs in `data/raw/books/` | Narrative anchors, not annual shares |
| **Jizya / dhimmi scholarship** | PDFs in `data/raw/books/` | Proxies for historical minority shares — confidence 0.2–0.5 |

## Surveys & attitudes (optional overlays, not core shares)

| Source | URL | Notes |
| --- | --- | --- |
| **Arab Barometer** | https://www.arabbarometer.org/survey-data/data-downloads/ | **Ingested** Q1012 religion → `arab_barometer_religion_shares.jsonl` (survey shares, conf 0.40). Raw zips in `data/raw/arab_barometer/`. |
| **Middle Eastern Values Study (MEVS)** | https://mevs.org/research/data/ | **Scripted:** `bash scripts/download_mevs.sh` → `data/raw/mevs/` (live site CF-gated; discovery/download via Wayback) |

## OCR (scanned books / appendices)

| Tool | Notes |
| --- | --- |
| **ocr_forge** (`/home/dylanmccapes/dev/ocr_forge`) | Standalone EasyOCR forge tuned for **RTX 3060 12 GB**. Use for Karpat appendix pages where `pypdf` spacing is unusable. See forge README. |

## Suggested download order

1. UN WPP country totals for 1950–2025 (fill years between Pew anchors). → **Done via OWID** (`scripts/ingest_owid_population.py`); WPP xlsx still available for revision alignment.
2. Ottoman census tables → `data/raw/ottoman/` + bibliography rows. → **Wiki bootstrap ingested**; Karpat PDF not yet table-extracted.
3. 3–5 hand-coded migration edges — **done** (`edges.jsonl`).
4. Jewish Data Bank diaspora nodes for France/US/UK cross-checks against Pew.

Drop new raw files under `data/raw/<source>/` and add a `source_id` row to `BIBLIOGRAPHY.md` before ingesting.
