#!/usr/bin/env python3
"""Catalog MEVS downloaded files → mevs_file_catalog.jsonl; stamp real microdata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "mevs_middle_eastern_values_study"
DEFAULT_DIR = ROOT / "data" / "raw" / "mevs" / "files"
DEFAULT_OUT = ROOT / "data" / "processed" / "mevs_file_catalog.jsonl"


def _kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".sav", ".dta", ".sas7bdat"}:
        # HTML stubs from Wayback are tiny
        if path.stat().st_size < 50_000:
            return "microdata_stub_or_html"
        return "microdata"
    if ext == ".pdf":
        return "pdf_doc"
    return "other"


def catalog(files_dir: Path, out: Path) -> int:
    rows = []
    for p in sorted(files_dir.iterdir()):
        if not p.is_file():
            continue
        rows.append(
            {
                "source_ids": [SOURCE_ID],
                "filename": p.name,
                "path": str(p.relative_to(ROOT)),
                "bytes": p.stat().st_size,
                "kind": _kind(p),
                "notes": "MEVS attitudes / questionnaires. Live site CF-gated; many files via Wayback.",
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
