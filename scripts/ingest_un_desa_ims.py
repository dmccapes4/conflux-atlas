#!/usr/bin/env python3
"""Ingest UN DESA International Migrant Stock (destination, both sexes) → JSONL.

Reads Table 1 of undesa_pd_2024_ims_stock_by_sex_and_destination.xlsx.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "un_desa_ims"
DEFAULT_RAW = (
    ROOT
    / "data"
    / "raw"
    / "un_desa_migrant_stock"
    / "undesa_pd_2024_ims_stock_by_sex_and_destination.xlsx"
)
DEFAULT_OUT = ROOT / "data" / "processed" / "un_desa_migrant_stock_destination.jsonl"

# Exact country labels in the DESA workbook → polity_id
NAME_TO_POLITY: dict[str, str] = {
    "Egypt": "egypt",
    "Türkiye": "turkey",
    "Turkey": "turkey",
    "Israel": "israel",
    "Lebanon": "lebanon",
    "Syrian Arab Republic": "syria",
    "Iraq": "iraq",
    "Iran (Islamic Republic of)": "iran",
    "Saudi Arabia": "saudi_arabia",
    "Morocco": "morocco",
    "Yemen": "yemen",
    "France": "france",
    "France*": "france",
    "United States of America": "united_states",
    "United States of America*": "united_states",
    "Greece": "greece",
    "Jordan": "jordan",
    "Libya": "libya",
    "Tunisia": "tunisia",
    "Algeria": "algeria",
    "State of Palestine": "palestine",
}

YEARS = (1990, 1995, 2000, 2005, 2010, 2015, 2020, 2024)


def ingest(raw: Path, out: Path) -> int:
    import openpyxl

    wb = openpyxl.load_workbook(raw, read_only=True, data_only=True)
    ws = wb["Table 1"]
    rows_out: list[dict] = []
    for row in ws.iter_rows(min_row=11, values_only=True):
        name = row[1]
        if not name or not isinstance(name, str):
            continue
        name = name.strip()
        polity = NAME_TO_POLITY.get(name)
        if not polity:
            continue
        # both-sexes block: cols 5..12 → YEARS
        for i, year in enumerate(YEARS):
            val = row[5 + i]
            if val is None:
                continue
            try:
                stock = int(round(float(val)))
            except (TypeError, ValueError):
                continue
            rows_out.append(
                {
                    "polity_id": polity,
                    "year": year,
                    "migrant_stock": stock,
                    "sex": "both",
                    "display_name": name,
                    "source_ids": [SOURCE_ID],
                    "confidence": 0.85,
                    "notes": "UN DESA IMS 2024 Table 1 — international migrant stock at mid-year, destination.",
                }
            )
    rows_out.sort(key=lambda x: (x["polity_id"], x["year"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows_out:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows_out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = ingest(args.raw, args.out)
    print(f"wrote {args.out} ({n} rows)")


if __name__ == "__main__":
    main()
