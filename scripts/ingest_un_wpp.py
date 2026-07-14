#!/usr/bin/env python3
"""Ingest UN WPP 2024 Estimates → population_totals_wpp.jsonl (demo ISO3 set).

Total Population as of 1 January is stored in thousands in the workbook;
we convert to persons.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "un_wpp"
DEFAULT_RAW = (
    ROOT / "data" / "raw" / "un_wpp" / "WPP2024_GEN_F01_DEMOGRAPHIC_INDICATORS_FULL.xlsx"
)
DEFAULT_OUT = ROOT / "data" / "processed" / "population_totals_wpp.jsonl"

ISO_TO_POLITY = {
    "EGY": "egypt",
    "TUR": "turkey",
    "ISR": "israel",
    "LBN": "lebanon",
    "SYR": "syria",
    "IRQ": "iraq",
    "IRN": "iran",
    "SAU": "saudi_arabia",
    "MAR": "morocco",
    "YEM": "yemen",
    "FRA": "france",
    "USA": "united_states",
    "GRC": "greece",
    "JOR": "jordan",
    "PSE": "palestine",
    "DZA": "algeria",
    "TUN": "tunisia",
    "LBY": "libya",
}


def ingest(raw: Path, out: Path, year_min: int, year_max: int) -> int:
    import openpyxl

    wb = openpyxl.load_workbook(raw, read_only=True, data_only=True)
    ws = wb["Estimates"]
    rows_out: list[dict] = []
    for row in ws.iter_rows(min_row=18, values_only=True):
        iso = row[5]
        typ = row[8]
        if typ != "Country/Area" or iso not in ISO_TO_POLITY:
            continue
        year = row[10]
        pop_thousands = row[11]  # 1 January
        if year is None or pop_thousands is None:
            continue
        year = int(year)
        if year < year_min or year > year_max:
            continue
        pop = int(round(float(pop_thousands) * 1000))
        rows_out.append(
            {
                "polity_id": ISO_TO_POLITY[iso],
                "year": year,
                "total_population": pop,
                "source_ids": [SOURCE_ID],
                "display_name": str(row[2]),
                "iso3": iso,
                "confidence": 0.95,
                "notes": "UN WPP 2024 Estimates — Total Population as of 1 January.",
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
    p.add_argument("--year-min", type=int, default=1950)
    p.add_argument("--year-max", type=int, default=2023)
    args = p.parse_args()
    n = ingest(args.raw, args.out, args.year_min, args.year_max)
    print(f"wrote {args.out} ({n} rows)")


if __name__ == "__main__":
    main()
