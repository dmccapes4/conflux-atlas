#!/usr/bin/env python3
"""Ingest Ottoman Wikipedia scrape tables → processed JSONL.

Outputs:
  data/processed/ottoman_empire_population.jsonl  — empire totals by year
  data/processed/ottoman_1914_provinces.jsonl      — 1914 Muslim/non-Muslim by province

These are bootstrap / low-confidence until cross-checked against Karpat.
Religion shares at empire scale are NOT invented here — totals only for the
empire series; 1914 provinces keep Muslim vs non-Muslim counts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "ottoman_demographics_wiki"
WIKI = ROOT / "data" / "raw" / "ottoman" / "wiki"
OUT_EMPIRE = ROOT / "data" / "processed" / "ottoman_empire_population.jsonl"
OUT_1914 = ROOT / "data" / "processed" / "ottoman_1914_provinces.jsonl"


def _parse_ottoman_int(raw) -> int | None:
    """Parse wiki numbers like '1.249.067', '341.903 (74.8%)', or '16.128.361'."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    # drop parenthetical percents
    s = re.sub(r"\([^)]*\)", "", s).strip()
    s = s.replace("\t", "").replace(" ", "").replace(",", "")
    # European thousands: dots between digit groups
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    else:
        s = re.sub(r"[^\d.]", "", s)
        if s.count(".") == 1 and len(s.split(".")[-1]) <= 2:
            # unlikely decimal in census headcounts; treat as thousands if 3+ digit groups
            pass
        s = s.replace(".", "")
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def ingest_empire(wiki: Path, out: Path) -> int:
    import pandas as pd

    path = wiki / "00_year__pop.csv"
    df = pd.read_csv(path)
    rows = []
    for _, r in df.iterrows():
        year = _parse_ottoman_int(r.get("Year"))
        # Year is plain int — don't use ottoman thousands parser wrongly
        try:
            year = int(float(str(r.get("Year")).strip()))
        except (TypeError, ValueError):
            continue
        pop = _parse_ottoman_int(r.get("Pop."))
        if pop is None:
            continue
        rows.append(
            {
                "polity_id": "ottoman_empire",
                "year": year,
                "total_population": pop,
                "source_ids": [SOURCE_ID],
                "display_name": "Ottoman Empire",
                "confidence": 0.35,
                "notes": "Wikipedia Demographics of the Ottoman Empire — empire totals; cross-check Karpat.",
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def ingest_1914(wiki: Path, out: Path) -> int:
    import pandas as pd

    path = wiki / "04_1914_official_census_values_malefemale_aggregated11_province.csv"
    df = pd.read_csv(path, header=None)
    # row0 title, row1 headers Province,Muslim,Armenian,Greek
    rows = []
    for i in range(2, len(df)):
        province = str(df.iloc[i, 0]).strip()
        if not province or province.lower() in {"nan", "province"}:
            continue
        muslim = _parse_ottoman_int(df.iloc[i, 1])
        armenian = _parse_ottoman_int(df.iloc[i, 2])
        greek = _parse_ottoman_int(df.iloc[i, 3])
        if muslim is None and armenian is None and greek is None:
            continue
        muslim = muslim or 0
        armenian = armenian or 0
        greek = greek or 0
        # Duplicate footer: same grand total in every column
        if province.lower() == "total" and muslim == armenian == greek:
            continue
        total = muslim + armenian + greek
        if total <= 0:
            continue
        rec = {
            "year": 1914,
            "province": province,
            "muslim": muslim,
            "armenian": armenian,
            "greek": greek,
            "total_population": total,
            "muslim_share": round(muslim / total, 4) if total else None,
            "source_ids": [SOURCE_ID],
            "confidence": 0.40,
            "notes": "1914 Ottoman official census (wiki); Muslim / Armenian / Greek columns. European thousand-dots parsed.",
        }
        rows.append(rec)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wiki", type=Path, default=WIKI)
    args = p.parse_args()
    n1 = ingest_empire(args.wiki, OUT_EMPIRE)
    n2 = ingest_1914(args.wiki, OUT_1914)
    print(f"wrote {OUT_EMPIRE} ({n1} empire years)")
    print(f"wrote {OUT_1914} ({n2} provinces)")


if __name__ == "__main__":
    main()
