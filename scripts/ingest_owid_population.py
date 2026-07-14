#!/usr/bin/env python3
"""Ingest Our World in Data population.csv → population_totals.jsonl.

Used by ConfluxModel to scale node size between religion anchors (hold shares,
overlay annual totals).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "owid_population"
DEFAULT_RAW = ROOT / "data" / "raw" / "owid" / "population.csv"
DEFAULT_OUT = ROOT / "data" / "processed" / "population_totals.jsonl"

# OWID Entity → Conflux polity_id (demo slice + greece)
ENTITY_TO_POLITY: dict[str, str] = {
    "Egypt": "egypt",
    "Turkey": "turkey",
    "Israel": "israel",
    "Lebanon": "lebanon",
    "Syria": "syria",
    "Iraq": "iraq",
    "Iran": "iran",
    "Saudi Arabia": "saudi_arabia",
    "Morocco": "morocco",
    "Yemen": "yemen",
    "France": "france",
    "United States": "united_states",
    "Greece": "greece",
}


def ingest(raw_path: Path, out_path: Path, year_min: int, year_max: int) -> int:
    import pandas as pd

    if not raw_path.is_file():
        raise FileNotFoundError(raw_path)

    df = pd.read_csv(raw_path)
    df = df[df["Entity"].isin(ENTITY_TO_POLITY)]
    df = df[(df["Year"] >= year_min) & (df["Year"] <= year_max)]
    df = df.dropna(subset=["Population"])

    rows: list[dict] = []
    for _, r in df.iterrows():
        polity_id = ENTITY_TO_POLITY[str(r["Entity"])]
        year = int(r["Year"])
        pop = int(round(float(r["Population"])))
        if pop < 0:
            continue
        rows.append(
            {
                "polity_id": polity_id,
                "year": year,
                "total_population": pop,
                "source_ids": [SOURCE_ID],
                "display_name": str(r["Entity"]),
                "owid_code": None if pd.isna(r.get("Code")) else str(r["Code"]),
            }
        )

    rows.sort(key=lambda x: (x["polity_id"], x["year"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--year-min", type=int, default=1900)
    p.add_argument("--year-max", type=int, default=2025)
    args = p.parse_args()
    n = ingest(args.raw, args.out, args.year_min, args.year_max)
    print(f"wrote {args.out} ({n} rows, {len(ENTITY_TO_POLITY)} polities)")


if __name__ == "__main__":
    main()
