#!/usr/bin/env python3
"""Ingest UN DESA IMS 2024 bilateral destination×origin stocks (demo polity set).

Reads Table 1 of undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx.
Emits one row per (dest, origin, year) where both ends map to Conflux polities.
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
    / "undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx"
)
DEFAULT_OUT = ROOT / "data" / "processed" / "un_desa_migrant_stock_od.jsonl"

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
    "Russian Federation": "russia",
    "Germany": "germany",
    "United Kingdom": "united_kingdom",
    "United Kingdom*": "united_kingdom",
}

YEARS = (1990, 1995, 2000, 2005, 2010, 2015, 2020, 2024)


def _polity(name: object) -> str | None:
    if not isinstance(name, str):
        return None
    return NAME_TO_POLITY.get(name.strip())


def ingest(raw: Path, out: Path) -> int:
    import openpyxl

    wb = openpyxl.load_workbook(raw, read_only=True, data_only=True)
    ws = wb["Table 1"]
    rows_out: list[dict] = []
    for row in ws.iter_rows(min_row=11, values_only=True):
        dest_p = _polity(row[1])
        orig_p = _polity(row[5])
        if not dest_p or not orig_p or dest_p == orig_p:
            continue
        for i, year in enumerate(YEARS):
            val = row[7 + i]
            if val is None:
                continue
            try:
                stock = int(round(float(val)))
            except (TypeError, ValueError):
                continue
            if stock <= 0:
                continue
            rows_out.append(
                {
                    "to_polity": dest_p,
                    "from_polity": orig_p,
                    "year": year,
                    "migrant_stock": stock,
                    "sex": "both",
                    "display_destination": str(row[1]).strip(),
                    "display_origin": str(row[5]).strip(),
                    "source_ids": [SOURCE_ID],
                    "confidence": 0.80,
                    "notes": (
                        "UN DESA IMS 2024 Table 1 — international migrant stock at mid-year "
                        "by destination and origin (both sexes). Stock, not flow."
                    ),
                }
            )
    rows_out.sort(key=lambda x: (x["to_polity"], x["from_polity"], x["year"]))
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
    print(f"wrote {args.out} ({n} OD×year rows)")


if __name__ == "__main__":
    main()
