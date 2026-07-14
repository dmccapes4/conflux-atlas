#!/usr/bin/env python3
"""Resolve CBS publication page → DocLib file URLs → urls.txt

CBS publication pages are SharePoint shells; files live under
  /he/publications/DocLib/{CbsPublishingFolderLevel1}/{CbsPublishingFolderLevel2}/

This script reads those folder fields from the page list item, lists Files via
REST, and writes absolute download URLs for wget.

Default page: Population & components of growth in localities and statistical areas
(אוכלוסייה ומרכיבי גידול… 2014–2024).
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
OUT_DIR = ROOT / "data" / "raw" / "cbs" / "population_madaf"
DEFAULT_PAGE = (
    "https://www.cbs.gov.il/he/publications/Pages/2017/"
    "%D7%90%D7%95%D7%9B%D7%9C%D7%95%D7%A1%D7%99%D7%99%D7%94-"
    "%D7%95%D7%9E%D7%A8%D7%9B%D7%99%D7%91%D7%99-"
    "%D7%92%D7%99%D7%93%D7%95%D7%9C-"
    "%D7%91%D7%99%D7%99%D7%A9%D7%95%D7%91%D7%99%D7%9D-"
    "%D7%95%D7%91%D7%90%D7%96%D7%95%D7%A8%D7%99%D7%9D-"
    "%D7%A1%D7%98%D7%98%D7%99%D7%A1%D7%98%D7%99%D7%99%D7%9D-2017.aspx"
)
UA = "ConfluxAtlas/0.1 (+research ingest; CBS DocLib fetch)"
ORIGIN = "https://www.cbs.gov.il"


def _get(url: str, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": accept},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def _get_json(url: str) -> dict:
    raw = _get(url, accept="application/json;odata=verbose")
    return json.loads(raw.decode("utf-8"))


def page_context(page_url: str) -> tuple[str, str, int]:
    """Return (webAbsoluteUrl, listGuid, pageItemId)."""
    html = _get(page_url).decode("utf-8", errors="replace")
    web = re.search(r'"webAbsoluteUrl"\s*:\s*"([^"]+)"', html)
    list_id = re.search(r'"listId"\s*:\s*"\{?([0-9a-fA-F-]+)\}?"', html)
    item = re.search(r'"pageItemId"\s*:\s*(\d+)', html)
    if not (web and list_id and item):
        raise RuntimeError("could not parse _spPageContextInfo from page HTML")
    return web.group(1), list_id.group(1), int(item.group(1))


def folder_levels(web: str, list_guid: str, item_id: int) -> tuple[str, str, str]:
    url = (
        f"{web}/_api/Web/Lists(guid'{list_guid}')/Items({item_id})"
        f"?$select=Title,CbsPublishingFolderLevel1,CbsPublishingFolderLevel2"
    )
    d = _get_json(url)["d"]
    l1 = d.get("CbsPublishingFolderLevel1")
    l2 = d.get("CbsPublishingFolderLevel2")
    if not l1 or not l2:
        raise RuntimeError(f"missing DocLib folder fields on item {item_id}: {d}")
    return str(l1), str(l2), str(d.get("Title") or "")


def list_files(web: str, l1: str, l2: str) -> list[dict]:
    # Server-relative folder under the publications web
    folder = f"DocLib/{l1}/{l2}"
    quoted = urllib.parse.quote(folder, safe="/")
    url = (
        f"{web}/_api/web/GetFolderByServerRelativeUrl('{quoted}')/Files"
        f"?$select=Name,ServerRelativeUrl,Length,TimeLastModified&$top=5000"
    )
    d = _get_json(url)
    return d.get("d", {}).get("results", [])


def abs_url(server_relative: str) -> str:
    # Encode path segments for wget (Hebrew filenames, spaces, commas)
    if not server_relative.startswith("/"):
        server_relative = "/" + server_relative
    return ORIGIN + urllib.parse.quote(server_relative, safe="/")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--page", default=DEFAULT_PAGE, help="CBS publication page URL")
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = p.parse_args()

    web, list_guid, item_id = page_context(args.page)
    l1, l2, title = folder_levels(web, list_guid, item_id)
    files = list_files(web, l1, l2)
    if not files:
        print(f"No files in DocLib/{l1}/{l2}", file=sys.stderr)
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    urls_path = args.out_dir / "urls.txt"
    manifest_path = args.out_dir / "manifest.jsonl"
    meta_path = args.out_dir / "meta.json"

    urls: list[str] = []
    with manifest_path.open("w", encoding="utf-8") as mf:
        for f in sorted(files, key=lambda x: x.get("Name") or ""):
            rel = f.get("ServerRelativeUrl") or ""
            u = abs_url(rel)
            urls.append(u)
            mf.write(
                json.dumps(
                    {
                        "name": f.get("Name"),
                        "server_relative_url": rel,
                        "url": u,
                        "length": f.get("Length"),
                        "modified": f.get("TimeLastModified"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    urls_path.write_text("\n".join(urls) + "\n", encoding="utf-8")
    meta = {
        "page": args.page,
        "title": title,
        "doclib_folder": f"DocLib/{l1}/{l2}",
        "n_files": len(urls),
        "total_bytes": sum(int(f.get("Length") or 0) for f in files),
        "source_id": "cbs_population_madaf",
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"title: {title}")
    print(f"folder: DocLib/{l1}/{l2}")
    print(f"files: {len(urls)}")
    print(f"wrote {urls_path}")
    print(f"wrote {manifest_path}")
    print("download with:  bash scripts/download_cbs_population_madaf.sh")


if __name__ == "__main__":
    main()
