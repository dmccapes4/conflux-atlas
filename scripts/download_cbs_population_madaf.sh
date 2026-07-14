#!/usr/bin/env bash
# Download Israel CBS "population_madaf" Excel tables listed by
# scripts/list_cbs_population_madaf_urls.py
#
# Page:
# https://www.cbs.gov.il/he/publications/Pages/2017/…אוכלוסייה-ומרכיבי-גידול…-2017.aspx
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/data/raw/cbs/population_madaf"
URLS="${OUT}/urls.txt"
PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

echo "▸ Refreshing URL list from CBS SharePoint…"
"$PY" "${ROOT}/scripts/list_cbs_population_madaf_urls.py" --out-dir "${OUT}"

if [[ ! -f "${URLS}" ]]; then
  echo "Missing ${URLS}"
  exit 1
fi

mkdir -p "${OUT}/files"
n=$(grep -c . "${URLS}" || true)
echo "▸ wget ${n} files → ${OUT}/files/"

wget \
  --input-file="${URLS}" \
  --directory-prefix="${OUT}/files" \
  --no-clobber \
  --continue \
  --wait=0.5 --random-wait \
  --user-agent='ConfluxAtlas/0.1 (+research ingest; CBS DocLib)' \
  --restrict-file-names=windows \
  -e robots=off

echo ""
echo "✓ CBS files in ${OUT}/files"
find "${OUT}/files" -type f | wc -l
du -sh "${OUT}/files"
