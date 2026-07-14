#!/usr/bin/env python3
"""List World Jewish Population PDF URLs from Berman Jewish DataBank.

The public search UI is JS-rendered; the underlying API is:

  GET https://www.jewishdatabank.org/api/search
      ?what=...&source=DataBank&startingFrom=<page>&perPage=50

Each hit may include FileMediaList (comma-separated site-relative PDF paths).

Writes:
  data/raw/jewishdatabank/urls.txt          — one absolute URL per line
  data/raw/jewishdatabank/manifest.jsonl    — study metadata + urls

Usage:
  .venv/bin/python scripts/list_jewishdatabank_wjp_urls.py
  .venv/bin/python scripts/list_jewishdatabank_wjp_urls.py --all   # every search hit, not just WJP titles
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "jewishdatabank"
API = "https://www.jewishdatabank.org/api/search"
ORIGIN = "https://www.jewishdatabank.org"
UA = "ConfluxAtlas/0.1 (+local research ingest; contact via project README)"

WJP_TITLE = re.compile(r"world jewish population", re.I)
BRIEFING = re.compile(r"briefing|databank posts new reports|databank brief", re.I)


def _get(page: int, per_page: int, query: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "what": query,
            "source": "DataBank",
            "startingFrom": page,
            "acceptFilterData": "true",
            "perPage": per_page,
            "sortBy": "Date",
        }
    )
    req = urllib.request.Request(
        f"{API}?{params}",
        headers={"Accept": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def _absolute_file_urls(file_media_list: str | None) -> list[str]:
    if not file_media_list:
        return []
    # Multiple files are joined as ", /content/..." — filenames themselves may contain commas.
    raw = file_media_list.strip()
    parts = re.split(r",\s+(?=/)", raw)
    urls: list[str] = []
    for part in parts:
        path = part.strip().rstrip(",")
        if not path:
            continue
        if not path.startswith("/"):
            path = "/" + path
        encoded = urllib.parse.quote(path, safe="/")
        urls.append(ORIGIN + encoded)
    return urls


def fetch_all(query: str, per_page: int = 50) -> list[dict]:
    hits: list[dict] = []
    page = 0
    while True:
        data = _get(page, per_page, query)
        batch = data.get("res") or []
        if not batch:
            break
        hits.extend(batch)
        total = (data.get("Data") or {}).get("ResultsDataBank")
        print(f"page {page}: +{len(batch)} (have {len(hits)}"
              + (f" / {total}" if total is not None else "") + ")", file=sys.stderr)
        if total is not None and len(hits) >= int(total):
            break
        if len(batch) < per_page and page > 0:
            break
        page += 1
        if page > 50:
            break
    # de-dupe by Id
    seen: set[str] = set()
    out: list[dict] = []
    for h in hits:
        i = str(h.get("Id"))
        if i in seen:
            continue
        seen.add(i)
        out.append(h)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--query",
        default="world jewish population",
        help="DataBank search `what` parameter",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Keep every search hit (default: title matches World Jewish Population, drop briefings)",
    )
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = p.parse_args()

    hits = fetch_all(args.query)
    if not args.all:
        hits = [
            h
            for h in hits
            if WJP_TITLE.search(h.get("Title") or "")
            and not BRIEFING.search(h.get("Title") or "")
        ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    urls_path = args.out_dir / "urls.txt"
    manifest_path = args.out_dir / "manifest.jsonl"

    all_urls: list[str] = []
    with manifest_path.open("w", encoding="utf-8") as mf:
        for h in sorted(hits, key=lambda x: (x.get("Date") or "", x.get("Id") or "")):
            urls = _absolute_file_urls(h.get("FileMediaList"))
            all_urls.extend(urls)
            rec = {
                "id": h.get("Id"),
                "title": h.get("Title"),
                "date": h.get("Date"),
                "investigator": h.get("Investigator"),
                "study_url": f"{ORIGIN}/databank/search-results/study/{h.get('Id')}",
                "pdf_urls": urls,
            }
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # unique preserve order
    seen_u: set[str] = set()
    unique_urls: list[str] = []
    for u in all_urls:
        if u not in seen_u:
            seen_u.add(u)
            unique_urls.append(u)

    urls_path.write_text("\n".join(unique_urls) + ("\n" if unique_urls else ""), encoding="utf-8")
    print(f"studies: {len(hits)}")
    print(f"pdf urls: {len(unique_urls)}")
    print(f"wrote {urls_path}")
    print(f"wrote {manifest_path}")
    print("download with:  bash scripts/download_jewishdatabank_wjp.sh")


if __name__ == "__main__":
    main()
