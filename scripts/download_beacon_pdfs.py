#!/usr/bin/env python3
"""Download open PDFs listed in docs/beacon-inventories/BEACON_*.md.

Parses each inventory's ``## Open PDFs`` section and writes files under::

    data/raw/beacons/<beacon_id>/<safe_filename>.pdf

Usage::

    .venv/bin/python scripts/download_beacon_pdfs.py --continue
    .venv/bin/python scripts/download_beacon_pdfs.py --beacon syrian_civil_war_refugees_2011_present
    .venv/bin/python scripts/download_beacon_pdfs.py --dry-run

``--continue`` (recommended): skip files already on disk; never abort the run
on a single URL failure (Unicode, SSL, 403, HTML masquerading as PDF, …).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV_DIR = ROOT / "docs" / "beacon-inventories"
OUT_ROOT = ROOT / "data" / "raw" / "beacons"

BEACON_RE = re.compile(r"\*\*beacon_id:\*\*\s*`?([a-z0-9_]+)`?", re.I)
OPEN_SECTION_RE = re.compile(
    r"^##\s+Open PDFs\s*\n(.*?)(?=^##\s|\Z)", re.I | re.M | re.S
)
# Allow parentheses in paths (Jewish Data Bank, Shaw, …). Stop at whitespace /
# markdown closers only — not at ')'.
URL_RE = re.compile(r"https?://[^\s\]\>\"'<>]+", re.I)
SOURCE_ID_RE = re.compile(r"`([a-z0-9_]+)`")


def _beacon_id_from_path(path: Path, text: str) -> str:
    m = BEACON_RE.search(text)
    if m:
        return m.group(1)
    name = path.stem
    if name.startswith("BEACON_"):
        return name[len("BEACON_") :]
    return name


def _looks_like_pdf_url(url: str) -> bool:
    """Accept direct .pdf paths and common open-repo download endpoints."""
    u = url.lower().split("#", 1)[0]
    path = u.split("?", 1)[0]
    if path.endswith(".pdf"):
        return True
    markers = (
        "/download/article-file/",
        "/viewcontent.cgi",
        "/bitstreams/",
        "/download",
        "/content",
        "viewfile/",
        "/article/download/",
        "/article/download",
    )
    return any(m in path for m in markers)


def _clean_url(url: str) -> str:
    return url.rstrip(".,;)]}>\"").strip()


def parse_open_pdfs(text: str) -> list[tuple[str | None, str]]:
    """Return [(proposed_source_id|None, url), …] from ## Open PDFs."""
    m = OPEN_SECTION_RE.search(text)
    if not m:
        return []
    block = m.group(1)
    out: list[tuple[str | None, str]] = []
    seen: set[str] = set()
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("<!--"):
            continue
        urls = [_clean_url(u) for u in URL_RE.findall(line)]
        urls = [u for u in urls if _looks_like_pdf_url(u)]
        if not urls:
            continue
        sid_m = SOURCE_ID_RE.search(line)
        sid = sid_m.group(1) if sid_m else None
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            out.append((sid, url))
    return out


def _safe_name(source_id: str | None, url: str) -> str:
    base = source_id or "unnamed"
    base = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_") or "unnamed"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}.pdf"


def _request_url(url: str) -> str:
    """Percent-encode non-ASCII path segments so http.client stays ASCII-safe."""
    parts = urllib.parse.urlsplit(url)
    # quote path but preserve already-encoded %xx and structural slashes
    path = urllib.parse.quote(parts.path, safe="/%:@+$&'()*,;=!")
    query = parts.query  # leave as-is; typically ASCII
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, path, query, parts.fragment)
    )


def download(
    url: str,
    dest: Path,
    *,
    timeout: int = 60,
    insecure: bool = False,
) -> tuple[bool, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True, "exists"

    req_url = _request_url(url)
    req = urllib.request.Request(
        req_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; conflux-atlas-beacon-pdf-fetcher/0.2; "
                "+local research)"
            ),
            "Accept": "application/pdf,*/*",
        },
    )
    ctx = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            data = resp.read()
    except Exception as e:  # noqa: BLE001 — continue mode must not crash the run
        return False, f"error: {e}"

    if data.startswith(b"%PDF"):
        dest.write_bytes(data)
        return True, f"wrote {len(data)} bytes"
    if "html" in ctype:
        return False, f"not pdf (Content-Type={ctype!r})"
    if "pdf" in ctype:
        dest.write_bytes(data)
        return True, f"wrote {len(data)} bytes (ctype pdf, no %PDF magic)"
    return False, f"not pdf (magic={data[:8]!r}, Content-Type={ctype!r})"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory-dir", type=Path, default=INV_DIR)
    p.add_argument("--out-dir", type=Path, default=OUT_ROOT)
    p.add_argument("--beacon", action="append", default=[], help="Limit to beacon_id(s)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--continue",
        dest="continue_",
        action="store_true",
        help="Skip existing files; never abort on a single URL failure (exit 0)",
    )
    p.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification (some campus mirrors)",
    )
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()

    paths = sorted(args.inventory_dir.glob("BEACON_*.md"))
    if not paths:
        sys.exit(f"no inventories under {args.inventory_dir}")

    want = set(args.beacon)
    n_urls = n_ok = n_fail = n_skip = 0
    failures: list[str] = []

    for path in paths:
        text = path.read_text(encoding="utf-8")
        bid = _beacon_id_from_path(path, text)
        if want and bid not in want:
            continue
        entries = parse_open_pdfs(text)
        if not entries:
            print(f"{bid}: no ## Open PDFs links")
            continue
        for sid, url in entries:
            n_urls += 1
            dest = args.out_dir / bid / _safe_name(sid, url)
            print(f"{bid}: {sid or '-'} → {url}")
            if args.dry_run:
                n_skip += 1
                continue
            # Always skip existing when --continue; also skip by default if present
            # (download() returns "exists"). --continue additionally softens exit.
            try:
                ok, msg = download(
                    url, dest, timeout=args.timeout, insecure=args.insecure
                )
            except Exception as e:  # noqa: BLE001
                ok, msg = False, f"error: {e}"
            rel = dest.relative_to(ROOT) if ok and msg != "exists" else (
                dest.relative_to(ROOT) if ok else dest.name
            )
            print(f"  {msg} → {rel}")
            if ok and msg == "exists":
                n_skip += 1
            elif ok:
                n_ok += 1
            else:
                n_fail += 1
                failures.append(f"{bid}\t{sid or '-'}\t{url}\t{msg}")
                if not args.continue_:
                    print("aborting (pass --continue to keep going)")
                    print(
                        f"done: urls={n_urls} downloaded={n_ok} "
                        f"skipped/exists={n_skip} failed={n_fail}"
                    )
                    sys.exit(1)

    print(
        f"done: urls={n_urls} downloaded={n_ok} skipped/exists={n_skip} failed={n_fail}"
    )
    if failures:
        fail_path = args.out_dir / "_failures.tsv"
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(
            "beacon_id\tsource_id\turl\terror\n" + "\n".join(failures) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {fail_path.relative_to(ROOT)}")
    if n_fail and not args.continue_:
        sys.exit(1)


if __name__ == "__main__":
    main()
