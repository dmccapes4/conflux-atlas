#!/usr/bin/env bash
# Download World Jewish Population PDFs listed by list_jewishdatabank_wjp_urls.py
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/data/raw/jewishdatabank"
URLS="${OUT}/urls.txt"

if [[ ! -f "${URLS}" ]]; then
  echo "Missing ${URLS} — run:"
  echo "  ${ROOT}/.venv/bin/python ${ROOT}/scripts/list_jewishdatabank_wjp_urls.py"
  exit 1
fi

mkdir -p "${OUT}/pdfs"
cd "${OUT}/pdfs"

# -nc: skip existing; --content-disposition ignored (paths already have filenames)
# --restrict-file-names=windows: safer local names with spaces/commas
wget \
  --input-file="${URLS}" \
  --directory-prefix="${OUT}/pdfs" \
  --no-clobber \
  --continue \
  --wait=1 --random-wait \
  --user-agent='ConfluxAtlas/0.1 (+local research ingest)' \
  --restrict-file-names=windows \
  -e robots=off

echo ""
echo "✓ PDFs in ${OUT}/pdfs"
ls -1 "${OUT}/pdfs" | wc -l
