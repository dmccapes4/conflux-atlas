#!/usr/bin/env python3
"""Ingest UNHCR COO×COA dump → processed OD refugee stock + migration edges.

Stock snapshots are not flows. We emit:
  1. ``unhcr_syria_refugee_stock_od.jsonl`` — annual origin→host stocks
  2. Append-safe edges into a sidecar that ``seed_beacon_tranche1.py`` merges,
     OR write edges directly when ``--write-edges``.

Default: processed OD jsonl only; edges are authored in seed_beacon_tranche1.py
from peak-year stocks with explicit confidence caps.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "unhcr_population_api"
DEFAULT_RAW = (
    ROOT / "data" / "raw" / "unhcr" / "population_by_coo_syr_2011_2024.jsonl"
)
DEFAULT_OUT = ROOT / "data" / "processed" / "unhcr_syria_refugee_stock_od.jsonl"

COA_TO_POLITY: dict[str, str] = {
    "TUR": "turkey",
    "LEB": "lebanon",
    "JOR": "jordan",
    "IRQ": "iraq",
    "EGY": "egypt",
    "ARE": "egypt",
    "GFR": "germany",
    "SWE": "sweden",
    "NETH": "netherlands",
    "FRA": "france",
    "USA": "united_states",
    "CAN": "canada",
}
COO_TO_POLITY = {"SYR": "syria"}


def _num(v) -> int:
    if v is None or v == "-" or v == "":
        return 0
    try:
        return int(float(str(v).replace(",", "")))
    except ValueError:
        return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    if not args.raw.is_file():
        sys.exit(f"missing raw dump: {args.raw} (run scripts/fetch_unhcr_coo.py first)")

    rows: list[dict] = []
    with args.raw.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            coo = str(r.get("query_coo") or r.get("coo") or "").upper()
            coa = str(r.get("query_coa") or r.get("coa") or "").upper()
            origin = COO_TO_POLITY.get(coo)
            dest = COA_TO_POLITY.get(coa)
            if not origin or not dest:
                continue
            refugees = _num(r.get("refugees"))
            if refugees <= 0:
                continue
            year = int(r["year"])
            rows.append(
                {
                    "origin_polity_id": origin,
                    "dest_polity_id": dest,
                    "year": year,
                    "refugees": refugees,
                    "asylum_seekers": _num(r.get("asylum_seekers")),
                    "coo_code": coo,
                    "coa_code": coa,
                    "source_ids": [SOURCE_ID],
                    "confidence": 0.75,
                    "notes": (
                        "UNHCR Refugee Statistics API stock (not flow) "
                        f"coo={coo} coa={coa}"
                    ),
                }
            )

    rows.sort(key=lambda x: (x["origin_polity_id"], x["dest_polity_id"], x["year"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
