#!/usr/bin/env python3
"""List MEVS survey file URLs from the four study pages.

mevs.org and psc.isr.umich.edu are Cloudflare-gated from this environment.
We discover links from Wayback Machine page snapshots, then resolve each file
to a Wayback `id_` URL when possible (with live URL kept as fallback).

Studies:
  - Comparative Cross-National Study (MENA fundamentalism / values)
  - Comparative Panel Survey (Egypt, Tunisia, Turkey)
  - Comparative Values Surveys of Islamic Countries (CVSIC)
  - Youth fundamentalism (Egypt & Saudi Arabia)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "mevs"
UA = "ConfluxAtlas/0.1 (+research ingest; Wayback fallback for MEVS)"

PAGES = [
    {
        "slug": "comparative-cross-national-study-of-religious-fundamentalism-developmental-idealism-values-and-morality-in-the-middle-east-and-north-africa",
        "url": "https://mevs.org/research/data/comparative-cross-national-study-of-religious-fundamentalism-developmental-idealism-values-and-morality-in-the-middle-east-and-north-africa/",
        "short": "cross_national_fundamentalism_mena",
        "fallback_ts": "20200812060843",
    },
    {
        "slug": "comparative-panel-survey-on-the-dynamics-of-change-belief-formation-and-political-engagement-in-egypt-tunisia-and-turkey",
        "url": "https://mevs.org/research/data/comparative-panel-survey-on-the-dynamics-of-change-belief-formation-and-political-engagement-in-egypt-tunisia-and-turkey/",
        "short": "panel_egypt_tunisia_turkey",
        "fallback_ts": "20200812061738",
    },
    {
        "slug": "comparative-values-surveys-of-islamic-countries",
        "url": "https://mevs.org/research/data/comparative-values-surveys-of-islamic-countries/",
        "short": "cvsic",
        "fallback_ts": "20200812061401",
    },
    {
        "slug": "religious-fundamentalism-attitudes-toward-political-violence-and-developmental-idealism-among-youth-in-egypt-and-saudi-arabi",
        "url": "https://mevs.org/research/data/religious-fundamentalism-attitudes-toward-political-violence-and-developmental-idealism-among-youth-in-egypt-and-saudi-arabi/",
        "short": "youth_egypt_saudi",
        "fallback_ts": "20200812072750",
    },
]

FILE_EXT = re.compile(
    r"\.(sav|dta|csv|xlsx?|zip|pdf|por|rdata|rda|sas7bdat)(?:$|\?)",
    re.I,
)
SKIP = re.compile(r"favicon|cropped-favicon|\.jpg|\.png|\.gif|\.svg|\.webp", re.I)


def _get(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _get_json(url: str, timeout: int = 90) -> object:
    return json.loads(_get(url, timeout=timeout).decode("utf-8"))


def wayback_page_html(page_url: str, fallback_ts: str | None = None) -> tuple[str, str]:
    """Return (html, snapshot_ts) via CDX → id_ capture, with optional fixed ts."""
    ts = None
    original = page_url
    try:
        cdx = (
            "https://web.archive.org/cdx/search/cdx?"
            + urllib.parse.urlencode(
                {
                    "url": page_url,
                    "output": "json",
                    "filter": "statuscode:200",
                    "fl": "timestamp,original",
                    "limit": "1",
                    "fastLatest": "true",
                }
            )
        )
        rows = _get_json(cdx)
        if isinstance(rows, list) and len(rows) >= 2:
            ts, original = rows[1][0], rows[1][1]
    except Exception as e:
        print(f"  CDX warning: {e}", file=sys.stderr)

    if not ts:
        if not fallback_ts:
            raise RuntimeError(f"no Wayback snapshot for {page_url}")
        ts = fallback_ts

    last_err: Exception | None = None
    for attempt_ts in ([ts, fallback_ts] if fallback_ts and fallback_ts != ts else [ts]):
        if not attempt_ts:
            continue
        snap = f"https://web.archive.org/web/{attempt_ts}id_/{original}"
        for attempt in range(3):
            try:
                html = _get(snap).decode("utf-8", errors="replace")
                if "Just a moment" in html and len(html) < 10000:
                    raise RuntimeError("got Cloudflare interstitial from Wayback")
                return html, attempt_ts
            except Exception as e:
                last_err = e
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"no Wayback snapshot for {page_url}: {last_err}")


def extract_file_urls(html: str, page_url: str) -> list[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    out: list[str] = []
    seen: set[str] = set()
    for h in hrefs:
        h = unescape(h.strip())
        h = re.sub(r"^https?://web\.archive\.org/web/\d+id_/", "", h)
        h = re.sub(r"^https?://web\.archive\.org/web/\d+/", "", h)
        if h.startswith("//"):
            h = "https:" + h
        if h.startswith("/"):
            h = urllib.parse.urljoin("https://mevs.org/", h)
        if not h.startswith("http"):
            h = urllib.parse.urljoin(page_url, h)
        if SKIP.search(h):
            continue
        if not FILE_EXT.search(h):
            continue
        # normalize www
        if "psc.isr.umich.edu" in h and "www.psc" not in h:
            h = h.replace("://psc.isr.umich.edu", "://www.psc.isr.umich.edu")
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def wayback_file_url(live_url: str, sleep_s: float = 1.0) -> str | None:
    """Resolve a live file URL to a Wayback id_ URL, or None."""
    time.sleep(sleep_s)
    # Try availability API first
    api = "https://archive.org/wayback/available?" + urllib.parse.urlencode(
        {"url": live_url}
    )
    try:
        d = _get_json(api, timeout=60)
        snap = (d.get("archived_snapshots") or {}).get("closest") or {}
        if str(snap.get("status")) == "200" and snap.get("timestamp"):
            ts = snap["timestamp"]
            return f"https://web.archive.org/web/{ts}id_/{live_url}"
    except Exception as e:
        print(f"  availability miss {live_url.split('/')[-1]}: {e}", file=sys.stderr)

    # CDX fallback
    time.sleep(sleep_s)
    cdx = (
        "https://web.archive.org/cdx/search/cdx?"
        + urllib.parse.urlencode(
            {
                "url": live_url,
                "output": "json",
                "filter": "statuscode:200",
                "fl": "timestamp,mimetype,length",
                "limit": "5",
                "fastLatest": "true",
            }
        )
    )
    try:
        rows = _get_json(cdx, timeout=60)
        if isinstance(rows, list) and len(rows) >= 2:
            # skip HTML 404 captures
            for row in rows[1:]:
                ts, mime, length = row[0], (row[1] or ""), int(row[2] or 0)
                if "html" in mime.lower() and length < 2000:
                    continue
                return f"https://web.archive.org/web/{ts}id_/{live_url}"
    except Exception as e:
        print(f"  cdx miss {live_url.split('/')[-1]}: {e}", file=sys.stderr)
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument(
        "--resolve-wayback",
        action="store_true",
        default=True,
        help="Resolve each file to a Wayback id_ URL (default on)",
    )
    p.add_argument(
        "--no-resolve-wayback",
        action="store_false",
        dest="resolve_wayback",
    )
    p.add_argument("--sleep", type=float, default=1.2, help="Delay between Wayback API calls")
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    urls_path = args.out_dir / "urls.txt"
    live_urls_path = args.out_dir / "urls_live.txt"
    manifest_path = args.out_dir / "manifest.jsonl"
    meta_path = args.out_dir / "meta.json"

    download_urls: list[str] = []
    live_urls: list[str] = []
    meta_studies: list[dict] = []

    with manifest_path.open("w", encoding="utf-8") as mf:
        for study in PAGES:
            print(f"▸ {study['short']}", file=sys.stderr)
            try:
                html, page_ts = wayback_page_html(
                    study["url"], fallback_ts=study.get("fallback_ts")
                )
            except Exception as e:
                print(f"  FAIL page scrape: {e}", file=sys.stderr)
                continue
            files = extract_file_urls(html, study["url"])
            print(f"  found {len(files)} files (page snapshot {page_ts})", file=sys.stderr)
            study_rec = {
                "short": study["short"],
                "page": study["url"],
                "page_snapshot_ts": page_ts,
                "n_files": len(files),
            }
            meta_studies.append(study_rec)

            for live in files:
                live_urls.append(live)
                wb = None
                if args.resolve_wayback:
                    wb = wayback_file_url(live, sleep_s=args.sleep)
                # Soft Wayback link auto-picks a snapshot; works when live hosts are CF-gated.
                soft = f"https://web.archive.org/web/2020id_/{live}"
                use = wb or soft
                download_urls.append(use)
                mf.write(
                    json.dumps(
                        {
                            "study": study["short"],
                            "page": study["url"],
                            "live_url": live,
                            "download_url": use,
                            "via_wayback": True,
                            "wayback_resolved": bool(wb),
                            "filename": urllib.parse.unquote(live.rstrip("/").split("/")[-1]),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                flag = "WB-RESOLVED" if wb else "WB-SOFT"
                print(f"  [{flag}] {live.split('/')[-1][:70]}", file=sys.stderr)

    # unique preserve order
    def uniq(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for u in seq:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    download_urls = uniq(download_urls)
    live_urls = uniq(live_urls)

    urls_path.write_text("\n".join(download_urls) + ("\n" if download_urls else ""), encoding="utf-8")
    live_urls_path.write_text("\n".join(live_urls) + ("\n" if live_urls else ""), encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "source_id": "mevs_middle_eastern_values_study",
                "note": (
                    "Live mevs.org / psc.isr.umich.edu are Cloudflare-gated. "
                    "urls.txt prefers Wayback id_ captures; urls_live.txt has originals."
                ),
                "studies": meta_studies,
                "n_download_urls": len(download_urls),
                "n_live_urls": len(live_urls),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"wrote {urls_path} ({len(download_urls)} urls)")
    print(f"wrote {live_urls_path} ({len(live_urls)} urls)")
    print(f"wrote {manifest_path}")
    print("download with:  bash scripts/download_mevs.sh")


if __name__ == "__main__":
    main()
