#!/usr/bin/env python3
"""Ingest World Bank SP.POP.TOTL → population_totals_worldbank.jsonl (cross-check vs OWID)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "world_bank_sp_pop_totl"
DEFAULT_RAW = (
    ROOT
    / "data"
    / "raw"
    / "API_SP.POP.TOTL_DS2_EN_csv_v2_3107"
    / "API_SP.POP.TOTL_DS2_EN_csv_v2_3107.csv"
)
DEFAULT_OUT = ROOT / "data" / "processed" / "population_totals_worldbank.jsonl"

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
    import pandas as pd

    df = pd.read_csv(raw, skiprows=4)
    year_cols = [c for c in df.columns if str(c).isdigit()]
    rows: list[dict] = []
    for _, r in df.iterrows():
        code = str(r.get("Country Code") or "").strip()
        polity = ISO_TO_POLITY.get(code)
        if not polity:
            continue
        name = str(r.get("Country Name") or code)
        for yc in year_cols:
            year = int(yc)
            if year < year_min or year > year_max:
                continue
            val = r.get(yc)
            if pd.isna(val):
                continue
            pop = int(round(float(val)))
            if pop < 0:
                continue
            rows.append(
                {
                    "polity_id": polity,
                    "year": year,
                    "total_population": pop,
                    "source_ids": [SOURCE_ID],
                    "display_name": name,
                    "iso3": code,
                    "confidence": 0.88,
                }
            )
    rows.sort(key=lambda x: (x["polity_id"], x["year"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--year-min", type=int, default=1960)
    p.add_argument("--year-max", type=int, default=2025)
    args = p.parse_args()
    n = ingest(args.raw, args.out, args.year_min, args.year_max)
    print(f"wrote {args.out} ({n} rows)")


if __name__ == "__main__":
    main()
