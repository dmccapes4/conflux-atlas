#!/usr/bin/env bash
# Download Middle Eastern Values Study (MEVS) files listed by list_mevs_urls.py
#
# Pages (Cloudflare-gated live; discovery via Wayback):
#   https://mevs.org/research/data/comparative-cross-national-study-of-religious-fundamentalism-developmental-idealism-values-and-morality-in-the-middle-east-and-north-africa/
#   https://mevs.org/research/data/comparative-panel-survey-on-the-dynamics-of-change-belief-formation-and-political-engagement-in-egypt-tunisia-and-turkey/
#   https://mevs.org/research/data/comparative-values-surveys-of-islamic-countries/
#   https://mevs.org/research/data/religious-fundamentalism-attitudes-toward-political-violence-and-developmental-idealism-among-youth-in-egypt-and-saudi-arabi/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/data/raw/mevs"
URLS="${OUT}/urls.txt"
PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

echo "▸ Listing MEVS file URLs (Wayback page scrape; soft id_ download links)…"
# Default: no per-file CDX resolve (faster). Soft Wayback links usually work.
"$PY" "${ROOT}/scripts/list_mevs_urls.py" --out-dir "${OUT}" --no-resolve-wayback

if [[ ! -s "${URLS}" ]]; then
  echo "No URLs in ${URLS}"
  exit 1
fi

mkdir -p "${OUT}/files"
n=$(grep -c . "${URLS}" || true)
echo "▸ wget ${n} files → ${OUT}/files/"
echo "  (Wayback can be slow; --continue resumes)"

wget \
  --input-file="${URLS}" \
  --directory-prefix="${OUT}/files" \
  --no-clobber \
  --continue \
  --wait=2 --random-wait \
  --tries=3 \
  --retry-connrefused \
  --user-agent='ConfluxAtlas/0.1 (+research ingest; MEVS via Wayback)' \
  --restrict-file-names=windows \
  -e robots=off \
  || true

echo ""
echo "✓ MEVS files in ${OUT}/files"
find "${OUT}/files" -type f ! -name '*.html' | wc -l
# flag tiny/HTML failures
echo "suspicious (tiny or HTML):"
find "${OUT}/files" -type f \( -size -2k -o -name '*.html' \) 2>/dev/null | head -20 || true
du -sh "${OUT}/files"
echo "See ${OUT}/meta.json and manifest.jsonl"
