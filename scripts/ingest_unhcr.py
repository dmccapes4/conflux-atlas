#!/usr/bin/env python3
"""Ingest UNHCR population-by-coa API dump → processed refugee stock series.

Note: this fetch has country-of-asylum aggregates only (coo is blank). Useful as
host-country refugee *stock* overlays, not directed origin→destination edges.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "unhcr_population_api"
DEFAULT_RAW = ROOT / "data" / "raw" / "unhcr" / "population_by_coa_1975_2024.jsonl"
DEFAULT_OUT = ROOT / "data" / "processed" / "unhcr_refugee_stock_by_coa.jsonl"

# Legacy / ISO query codes from fetch_unhcr_api.py → Conflux polity_id
COA_TO_POLITY: dict[str, str] = {
    "ISR": "israel",
    "JOR": "jordan",
    "LEB": "lebanon",
    "SYR": "syria",
    "IRQ": "iraq",
    "ARE": "egypt",  # legacy UNHCR Egypt code
    "IRN": "iran",
    "TUR": "turkey",
    "YEM": "yemen",
    "SAU": "saudi_arabia",
    "LBY": "libya",
    "TUN": "tunisia",
    "ALG": "algeria",
    "MOR": "morocco",
    "FRA": "france",
    "USA": "united_states",
    "GFR": "germany",
    "GBR": "united_kingdom",
    "CAN": "canada",
    "UAE": "united_arab_emirates",
    "QAT": "qatar",
    "KUW": "kuwait",
    "BAH": "bahrain",
    "OMN": "oman",
    "SUD": "sudan",
    "GAZ": "palestine_gaza",  # often empty / zero in this dump
}


def _num(v) -> int:
    if v is None or v == "-" or v == "":
        return 0
    try:
        return int(float(str(v).replace(",", "")))
    except ValueError:
        return 0


def ingest(raw: Path, out: Path) -> int:
    rows_out: list[dict] = []
    with raw.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            code = str(r.get("query_coa") or r.get("coa") or "").upper()
            polity = COA_TO_POLITY.get(code)
            if not polity:
                continue
            year = int(r["year"])
            refugees = _num(r.get("refugees"))
            asylum = _num(r.get("asylum_seekers"))
            idps = _num(r.get("idps"))
            returned = _num(r.get("returned_refugees"))
            rows_out.append(
                {
                    "polity_id": polity,
                    "year": year,
                    "refugees": refugees,
                    "asylum_seekers": asylum,
                    "idps": idps,
                    "returned_refugees": returned,
                    "persons_of_concern": refugees + asylum + idps,
                    "coa_code": code,
                    "coa_name": r.get("query_coa_name") or r.get("coa_name"),
                    "source_ids": [SOURCE_ID],
                    "confidence": 0.75,
                    "notes": "UNHCR stock by country of asylum; origin (coo) not present in this dump.",
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
