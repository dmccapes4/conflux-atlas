#!/usr/bin/env python3
"""Fetch UNHCR Refugee Statistics API → data/raw/unhcr/*.jsonl

API: https://api.unhcr.org/population/v1/population/
Filter by country of asylum (coa) ISO3. Aggregates when coa is omitted.
"""

from __future__ import annotations

import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "unhcr"
API = "https://api.unhcr.org/population/v1/population/"
UA = "ConfluxAtlas/0.1 (+research ingest)"

# UNHCR `coa` filter uses their legacy `code`, NOT ISO3.
# See data/raw/unhcr/countries.json (iso vs code).
COA_CODES = [
    "ISR",  # Israel
    "GAZ",  # State of Palestine
    "JOR",  # Jordan
    "LEB",  # Lebanon
    "SYR",  # Syrian Arab Rep.
    "IRQ",  # Iraq
    "ARE",  # Egypt (UNHCR code ARE; ISO EGY) — NOT UAE
    "IRN",  # Iran
    "TUR",  # Türkiye
    "YEM",  # Yemen
    "SAU",  # Saudi Arabia
    "UAE",  # United Arab Emirates (confirm in countries.json)
    "QAT",  # Qatar
    "KUW",  # Kuwait
    "BAH",  # Bahrain
    "OMN",  # Oman
    "LBY",  # Libya
    "TUN",  # Tunisia
    "ALG",  # Algeria
    "MOR",  # Morocco
    "SUD",  # Sudan
    "FRA",  # France
    "GFR",  # Germany
    "GBR",  # United Kingdom
    "USA",  # United States
    "CAN",  # Canada
]

YEAR_FROM = 1975
YEAR_TO = 2024
PAGE_LIMIT = 10000


def fetch(coa: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "limit": PAGE_LIMIT,
            "yearFrom": YEAR_FROM,
            "yearTo": YEAR_TO,
            "coa": coa,
        }
    )
    req = urllib.request.Request(
        f"{API}?{params}",
        headers={"Accept": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    return data.get("items") or []


def load_code_map() -> dict[str, dict]:
    path = OUT / "countries.json"
    if not path.is_file():
        return {}
    items = json.loads(path.read_text(encoding="utf-8"))
    return {str(it.get("code")): it for it in items}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    code_map = load_code_map()
    codes = list(COA_CODES)

    jsonl_path = OUT / "population_by_coa_1975_2024.jsonl"
    csv_path = OUT / "population_by_coa_1975_2024.csv"
    rows: list[dict] = []

    for coa in codes:
        meta = code_map.get(coa, {})
        try:
            items = fetch(coa)
        except Exception as e:
            print(f"WARN {coa}: {e}", file=sys.stderr)
            continue
        label = meta.get("name") or coa
        print(f"{coa} ({label}): {len(items)} rows")
        for it in items:
            it = dict(it)
            it["query_coa"] = coa
            it["query_coa_iso"] = meta.get("iso")
            it["query_coa_name"] = meta.get("name")
            rows.append(it)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if rows:
        fields = sorted({k for r in rows for k in r.keys()})
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    meta = {
        "api": API,
        "year_from": YEAR_FROM,
        "year_to": YEAR_TO,
        "coa_codes": codes,
        "n_rows": len(rows),
        "note": (
            "UNHCR `coa` uses legacy codes (LEB, GAZ, GFR, ARE=Egypt, UAE=Emirates), not always ISO3. "
            "See countries.json. Country-of-asylum filter; origin often aggregated as '-'."
        ),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {jsonl_path} ({len(rows)} rows)")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
