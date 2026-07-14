#!/usr/bin/env python3
"""Fetch UNHCR Refugee Statistics API filtered by country of origin (coo).

Unlike ``fetch_unhcr_api.py`` (COA aggregates with blank COO), this pull keeps
origin×asylum pairs — required for Syria-outflow edges.

Writes: data/raw/unhcr/population_by_coo_<COO>_1975_2024.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "unhcr"
API = "https://api.unhcr.org/population/v1/population/"
UA = "ConfluxAtlas/0.1 (+research ingest)"

# Host countries (UNHCR legacy codes) for Syria-origin stocks.
DEFAULT_COA = [
    "TUR",
    "LEB",
    "JOR",
    "IRQ",
    "EGY",  # may be ARE in legacy — try both
    "ARE",
    "GFR",
    "SWE",
    "NETH",
    "FRA",
    "USA",
    "CAN",
]

YEAR_FROM = 2011
YEAR_TO = 2024
PAGE_LIMIT = 10000


def fetch(*, coo: str, coa: str | None, year_from: int, year_to: int) -> list[dict]:
    params: dict[str, str | int] = {
        "limit": PAGE_LIMIT,
        "yearFrom": year_from,
        "yearTo": year_to,
        "coo": coo,
    }
    if coa:
        params["coa"] = coa
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{API}?{qs}",
        headers={"Accept": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    return data.get("items") or []


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coo", default="SYR", help="UNHCR origin code (default SYR)")
    p.add_argument("--year-from", type=int, default=YEAR_FROM)
    p.add_argument("--year-to", type=int, default=YEAR_TO)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for coa in DEFAULT_COA:
        try:
            items = fetch(
                coo=args.coo,
                coa=coa,
                year_from=args.year_from,
                year_to=args.year_to,
            )
        except Exception as e:
            print(f"WARN {args.coo}->{coa}: {e}", file=sys.stderr)
            continue
        print(f"{args.coo}->{coa}: {len(items)} rows")
        for it in items:
            it = dict(it)
            it["query_coo"] = args.coo
            it["query_coa"] = coa
            rows.append(it)

    out = OUT / f"population_by_coo_{args.coo.lower()}_{args.year_from}_{args.year_to}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
