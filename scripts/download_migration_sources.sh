#!/usr/bin/env bash
# Download public migration / demography files for Conflux Atlas.
# Skips paywalled / login / JS-challenge sources (noted in NOTES.txt).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="${ROOT}/data/raw"
UA='Mozilla/5.0 (compatible; ConfluxAtlas/0.1; +research ingest)'
WGET=(wget --no-clobber --continue --wait=1 --random-wait --user-agent="$UA" -e robots=off)

mkdir -p \
  "${RAW}/un_desa_migrant_stock" \
  "${RAW}/unhcr" \
  "${RAW}/pcbs" \
  "${RAW}/arab_barometer" \
  "${RAW}/owid" \
  "${RAW}/harvard_dataverse"

NOTES="${RAW}/MIGRATION_DOWNLOAD_NOTES.txt"
cat > "${NOTES}" << 'EOF'
Conflux Atlas — migration / diaspora / survey download notes
============================================================

DOWNLOADED by scripts/download_migration_sources.sh
- UN DESA International Migrant Stock (xlsx) → data/raw/un_desa_migrant_stock/
  (IOM Migration Data Portal surfaces these; no separate IOM bulk dump)
- UNHCR Refugee Statistics API dumps → data/raw/unhcr/ (via fetch_unhcr_api.py)
- PCBS population indicators (xlsx) + sample yearbook zips → data/raw/pcbs/
- Arab Barometer English microdata zips (CSV where available) → data/raw/arab_barometer/

NOT auto-downloaded (manual / gated)
- Israel CBS: publications are portal/SharePoint-ish; grab Statistical Abstract
  “Population” chapter Excel from https://www.cbs.gov.il/ (Aliyah / religion tables)
- UNHCR web “Download” CSV button: Cloudflare-challenged; use API dump instead
- OWID “share-of-population-by-religion”: grapher slug 404 as of 2026-07; Pew already covers modern religion shares
- Harvard Dataverse: no single MENA demography dump; search manually for specific studies
- Cambridge History of Islam / Lapidus / jizya scholarship: books / JSTOR — not wget
- MEVS: no public bulk URL found
- Jewish Data Bank WJP: already handled by download_jewishdatabank_wjp.sh
EOF

echo "▸ UN DESA International Migrant Stock (IOM-facing totals)"
DESA=(
  'https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx'
  'https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/undesa_pd_2024_ims_stock_by_sex_and_destination.xlsx'
  'https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/undesa_pd_2024_ims_stock_by_sex_and_origin.xlsx'
  'https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/undesa_pd_2020_ims_stock_by_sex_destination_and_origin.xlsx'
)
for u in "${DESA[@]}"; do
  "${WGET[@]}" -P "${RAW}/un_desa_migrant_stock" "$u" || echo "WARN: failed $u"
done

echo "▸ PCBS population indicators"
PCBS=(
  'https://www.pcbs.gov.ps/media/f4np1lnh/projected-population-in-the-palestine.xlsx'
  'https://www.pcbs.gov.ps/media/mjuiee2o/estimated-population-growth-rate-in-palestine.xlsx'
  'https://www.pcbs.gov.ps/media/jtyhnter/sex-ratio-in-palestine.xlsx'
  'https://www.pcbs.gov.ps/media/4a0pboo1/life-expectancy-at-birth-in-palestine.xlsx'
  'https://www.pcbs.gov.ps/downloads/zip/2484-x.zip'
  'https://www.pcbs.gov.ps/portals/_pcbs/PressRelease/Press_En_WPD2025E.pdf'
)
for u in "${PCBS[@]}"; do
  "${WGET[@]}" -P "${RAW}/pcbs" "$u" || echo "WARN: failed $u"
done

echo "▸ Arab Barometer (English microdata — prefer CSV zips when present)"
AB=(
  'https://www.arabbarometer.org/wp-content/uploads/ArabBarometer_WaveVIII_English_v2.zip'
  'https://www.arabbarometer.org/wp-content/uploads/AB7_English_Version6.zip'
  'https://www.arabbarometer.org/wp-content/uploads/ENG-Arab-Barometer-Wave-VI-Part-1_DEC.zip'
  'https://www.arabbarometer.org/wp-content/uploads/ENG-Arab-Barometer-Wave-VI-Part-2-1.zip'
  'https://www.arabbarometer.org/wp-content/uploads/ENG-Arab-Barometer-Wave-VI-Part-3_DEC.zip'
  'https://www.arabbarometer.org/wp-content/uploads/ArabBarometer_WaveV_ENG.zip'
  'https://www.arabbarometer.org/wp-content/uploads/ABIV_English.csv.zip'
  'https://www.arabbarometer.org/wp-content/uploads/ABIII_English.csv.zip'
  'https://www.arabbarometer.org/wp-content/uploads/ABII_English.csv.zip'
)
for u in "${AB[@]}"; do
  "${WGET[@]}" -P "${RAW}/arab_barometer" "$u" || echo "WARN: failed $u"
done

echo "▸ OWID population CSV (religion grapher currently 404; keep population companion)"
"${WGET[@]}" -P "${RAW}/owid" \
  'https://ourworldindata.org/grapher/population.csv' \
  || echo "WARN: OWID population.csv failed"

echo "▸ UNHCR API (JSONL) — MENA + diaspora asylum countries"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  "${ROOT}/.venv/bin/python" "${ROOT}/scripts/fetch_unhcr_api.py" || echo "WARN: UNHCR API fetch failed"
else
  python3 "${ROOT}/scripts/fetch_unhcr_api.py" || echo "WARN: UNHCR API fetch failed"
fi

echo ""
echo "✓ Done. See ${NOTES}"
du -sh \
  "${RAW}/un_desa_migrant_stock" \
  "${RAW}/pcbs" \
  "${RAW}/arab_barometer" \
  "${RAW}/unhcr" \
  "${RAW}/owid" 2>/dev/null || true
