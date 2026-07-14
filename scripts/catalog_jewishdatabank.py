#!/usr/bin/env python3
"""Catalog Jewish Data Bank World Jewish Population PDFs → JSONL index."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "jewishdatabank_world_jewish_population"
DEFAULT_DIR = ROOT / "data" / "raw" / "jewishdatabank" / "pdfs"
DEFAULT_OUT = ROOT / "data" / "processed" / "jewishdatabank_wjp_catalog.jsonl"


def _guess_year(name: str) -> int | None:
    m = re.match(r"(19\d{2}|20\d{2})_", name)
    if m:
        return int(m.group(1))
    m = re.search(r"(19\d{2}|20\d{2})", name)
    return int(m.group(1)) if m else None


def catalog(pdf_dir: Path, out: Path) -> int:
    rows = []
    for p in sorted(pdf_dir.glob("*.pdf")):
        rows.append(
            {
                "source_ids": [SOURCE_ID],
                "filename": p.name,
                "path": str(p.relative_to(ROOT)),
                "bytes": p.stat().st_size,
                "year_guess": _guess_year(p.name),
                "notes": "AJYB / DellaPergola World Jewish Population PDF — tables not yet extracted to JSONL.",
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = catalog(args.pdf_dir, args.out)
    print(f"wrote {args.out} ({n} PDFs)")


if __name__ == "__main__":
    main()
