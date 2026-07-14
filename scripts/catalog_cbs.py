#!/usr/bin/env python3
"""Catalog CBS population_madaf Excel files → cbs_file_catalog.jsonl (no table parse yet)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "cbs_population_madaf"
DEFAULT_DIR = ROOT / "data" / "raw" / "cbs" / "population_madaf" / "files"
DEFAULT_OUT = ROOT / "data" / "processed" / "cbs_file_catalog.jsonl"


def _guess_year(name: str) -> int | None:
    m = re.search(r"(20\d{2})", name)
    return int(m.group(1)) if m else None


def catalog(files_dir: Path, out: Path) -> int:
    rows = []
    for p in sorted(files_dir.iterdir()):
        if not p.is_file() or p.suffix.lower() not in {".xls", ".xlsx"}:
            continue
        rows.append(
            {
                "source_ids": [SOURCE_ID],
                "filename": p.name,
                "path": str(p.relative_to(ROOT)),
                "bytes": p.stat().st_size,
                "year_guess": _guess_year(p.name),
                "notes": "Locality / statistical-area population tables (Hebrew). National religion shares not yet extracted.",
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--files-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = catalog(args.files_dir, args.out)
    print(f"wrote {args.out} ({n} files)")


if __name__ == "__main__":
    main()
