#!/usr/bin/env python3
"""Ingest CBS Israel national population-by-group totals from locality tables.

Parses English header rows (Jews / Others / Arabs [/ Foreigners]) and the
national Total row. Arab column aggregates Muslims, Arab Christians, Druze —
mapped to `muslim` as a proxy with capped confidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "cbs_population_madaf"
DEFAULT_DIR = ROOT / "data" / "raw" / "cbs" / "population_madaf" / "files"
DEFAULT_OUT = ROOT / "data" / "processed" / "cbs_israel_population_groups.jsonl"


def _year_from_text(*parts: str) -> int | None:
    for p in parts:
        m = re.search(r"(20\d{2})", p)
        if m:
            return int(m.group(1))
    return None


def _num(v) -> int | None:
    import pandas as pd

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if s in {"..", "-", ""}:
            return None
        try:
            return int(round(float(s)))
        except ValueError:
            return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _parse_workbook(path: Path) -> dict | None:
    import pandas as pd

    try:
        xl = pd.ExcelFile(path)
    except Exception:
        return None

    for sheet in xl.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sheet, header=None, nrows=60)
        except Exception:
            continue
        blob = " ".join(str(x) for x in df.astype(str).values.ravel() if x != "nan")
        if "Arabs" not in blob or "Jews" not in blob:
            continue

        # Find English column header (may span 2 rows: Code/Total/.../Arabs then Jews/Others)
        colmap: dict[str, int] = {}
        hdr_i = None
        for i in range(len(df) - 1):
            row = [str(x).strip() if pd.notna(x) else "" for x in df.iloc[i].tolist()]
            nxt = [str(x).strip() if pd.notna(x) else "" for x in df.iloc[i + 1].tolist()]
            lower = [c.lower() for c in row]
            lower_n = [c.lower() for c in nxt]
            if "arabs" not in lower:
                continue
            # Merge this row + next for subheaders
            merged = list(lower)
            for j, c in enumerate(lower_n):
                if c in {"jews", "others"} and j < len(merged):
                    merged[j] = c
            if "jews" not in merged and "jews" not in lower_n:
                continue
            hdr_i = i
            for j, c in enumerate(merged):
                if c == "jews":
                    colmap["jews"] = j
                elif c == "others":
                    colmap["others"] = j
                elif c == "arabs":
                    colmap["arabs"] = j
                elif "total israelis" in c:
                    colmap["total_israelis"] = j
                elif c == "total":
                    colmap["total"] = j
                elif "foreign" in c:
                    colmap["foreigners"] = j
                elif "jews and others" in c:
                    colmap["jews_and_others"] = j
            # Also map from next row explicitly
            for j, c in enumerate(lower_n):
                if c == "jews":
                    colmap["jews"] = j
                elif c == "others":
                    colmap["others"] = j
            break
        if hdr_i is None or "jews" not in colmap or "arabs" not in colmap:
            continue

        for i in range(hdr_i + 1, len(df)):
            row = df.iloc[i].tolist()
            labels = [str(x).strip() for x in row if pd.notna(x)]
            if not any(lab in ("סך הכל", "Total") for lab in labels):
                continue
            # Skip header-ish rows that only say Total without big numbers
            jews = _num(row[colmap["jews"]]) if colmap["jews"] < len(row) else None
            arabs = _num(row[colmap["arabs"]]) if colmap["arabs"] < len(row) else None
            if jews is None or arabs is None or jews < 1000:
                continue
            others = 0
            if "others" in colmap and colmap["others"] < len(row):
                others = _num(row[colmap["others"]]) or 0
            total = None
            if "total_israelis" in colmap and colmap["total_israelis"] < len(row):
                total = _num(row[colmap["total_israelis"]])
            if total is None and "total" in colmap and colmap["total"] < len(row):
                total = _num(row[colmap["total"]])
            if total is None:
                total = jews + others + arabs
            year = _year_from_text(path.name, sheet, blob[:240])
            if year is None or total <= 0:
                continue
            shares = {
                "jewish": jews / total,
                "muslim": arabs / total,
                "other": others / total,
                "christian": 0.0,
                "unaffiliated": 0.0,
                "buddhist": 0.0,
                "hindu": 0.0,
            }
            return {
                "anchor_id": f"{SOURCE_ID}_israel_{year}",
                "polity_id": "israel",
                "year": year,
                "year_precision": "exact",
                "total_population": total,
                "shares": shares,
                "dominant_religion": "jewish",
                "confidence": 0.70,
                "source_ids": [SOURCE_ID],
                "notes": (
                    "CBS end-of-year population by group (national Total row). "
                    "Arab column = Muslims + Arab Christians + Druze (+Lebanese) — "
                    "mapped to muslim share as proxy. Denominator prefers Total Israelis when present."
                ),
                "display_name": "Israel",
                "counts": {"jewish": jews, "muslim": arabs, "other": others},
                "cbs_jews": jews,
                "cbs_others": others,
                "cbs_arabs": arabs,
                "raw_file": path.name,
                "sheet": sheet,
            }
    return None


def ingest(files_dir: Path, out: Path) -> int:
    by_year: dict[int, dict] = {}
    for path in sorted(files_dir.glob("*.xlsx")):
        rec = _parse_workbook(path)
        if not rec:
            continue
        y = rec["year"]
        by_year[y] = rec
    rows = [by_year[y] for y in sorted(by_year)]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--files-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = ingest(args.files_dir, args.out)
    print(f"wrote {args.out} ({n} year rows)")


if __name__ == "__main__":
    main()
