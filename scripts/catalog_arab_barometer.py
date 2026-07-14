#!/usr/bin/env python3
"""Catalog Arab Barometer zip downloads → arab_barometer_catalog.jsonl."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "arab_barometer"
DEFAULT_DIR = ROOT / "data" / "raw" / "arab_barometer"
DEFAULT_OUT = ROOT / "data" / "processed" / "arab_barometer_catalog.jsonl"


def _wave_guess(name: str) -> str | None:
    m = re.search(r"(Wave\s*[IVX]+|AB[IVX]+|Wave-?([IVX]+|\d+)|AB(II|III|IV|V|VI|VII|VIII))", name, re.I)
    return m.group(0) if m else None


def catalog(raw_dir: Path, out: Path) -> int:
    rows = []
    for p in sorted(raw_dir.glob("*.zip")):
        members = []
        try:
            with zipfile.ZipFile(p) as zf:
                members = zf.namelist()[:20]
        except zipfile.BadZipFile:
            members = ["<bad zip>"]
        rows.append(
            {
                "source_ids": [SOURCE_ID],
                "filename": p.name,
                "path": str(p.relative_to(ROOT)),
                "bytes": p.stat().st_size,
                "wave_guess": _wave_guess(p.name),
                "zip_members_sample": members,
                "notes": "Attitude / values microdata — not census religion shares. Microdata extract TBD.",
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = catalog(args.raw_dir, args.out)
    print(f"wrote {args.out} ({n} zips)")


if __name__ == "__main__":
    main()
