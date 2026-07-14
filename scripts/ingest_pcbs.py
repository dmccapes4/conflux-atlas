#!/usr/bin/env python3
"""Ingest PCBS projected-population workbook → long JSONL (Palestine)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "pcbs_population"
DEFAULT_RAW = ROOT / "data" / "raw" / "pcbs" / "projected-population-in-the-palestine.xlsx"
DEFAULT_OUT = ROOT / "data" / "processed" / "pcbs_projected_population.jsonl"


def ingest(raw: Path, out: Path) -> int:
    import pandas as pd

    df = pd.read_excel(raw, sheet_name=0, header=None)
    # Row0 headers; row1 region labels; data from row2:
    # col4=Year, col5=West Bank, col6=Gaza Strip, col7=Palestine total
    rows: list[dict] = []
    for i in range(2, len(df)):
        year_cell = df.iloc[i, 4]
        pal = df.iloc[i, 7]
        wb = df.iloc[i, 5]
        gz = df.iloc[i, 6]
        if pd.isna(year_cell) or pd.isna(pal):
            continue
        year = int(float(year_cell))
        rows.append(
            {
                "polity_id": "palestine",
                "year": year,
                "total_population": int(round(float(pal))),
                "west_bank": None if pd.isna(wb) else int(round(float(wb))),
                "gaza_strip": None if pd.isna(gz) else int(round(float(gz))),
                "source_ids": [SOURCE_ID],
                "display_name": "Palestine",
                "confidence": 0.75,
                "notes": (
                    "PCBS projected population (revised estimates based on 2017 census). "
                    f"Source cell: {df.iloc[2, 3] if len(df) > 2 else ''}"
                ),
                "raw_file": raw.name,
            }
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = ingest(args.raw, args.out)
    print(f"wrote {args.out} ({n} rows)")


if __name__ == "__main__":
    main()
