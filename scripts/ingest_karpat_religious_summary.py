#!/usr/bin/env python3
"""Ingest Karpat Table 4.3 — empire-wide Muslim % by decade (Europe / Asia / Total).

Values are transcribed from the text-extractable Table 4.3 in
Karpat-Ottoman-Population-1830–1914.pdf (p.43 of the PDF extract). OCR spacing
is messy elsewhere; this summary table is clean enough for a cited JSONL seed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "karpat_ottoman_population_1830_1914"
DEFAULT_OUT = ROOT / "data" / "processed" / "karpat_religious_structure_summary.jsonl"
RAW_PDF = "Karpat-Ottoman-Population-1830–1914.pdf"

# year_mid → Europe / Asia / Total populations (000s omitted → persons) and Muslim %
# Source: Karpat Table 4.3 (populations in thousands in the print table).
TABLE_4_3 = [
    {
        "decade": "1820s",
        "year": 1825,
        "europe_population": 10_200_000,
        "europe_pct_muslim": 0.320,
        "asia_population": 11_100_000,
        "asia_pct_muslim_low": 0.80,
        "asia_pct_muslim_high": 0.90,
        "total_population": 21_300_000,
        "total_pct_muslim": 0.596,
    },
    {
        "decade": "1840s",
        "year": 1845,
        "europe_population": 15_500_000,
        "europe_pct_muslim": 0.361,
        "asia_population": None,
        "asia_pct_muslim_low": None,
        "asia_pct_muslim_high": None,
        "total_population": None,
        "total_pct_muslim": None,
    },
    {
        "decade": "1870s",
        "year": 1875,
        "europe_population": 10_150_000,
        "europe_pct_muslim": 0.430,
        "asia_population": 16_500_000,
        "asia_pct_muslim_low": 0.80,
        "asia_pct_muslim_high": 0.90,
        "total_population": 26_650_000,
        "total_pct_muslim": 0.680,
    },
    {
        "decade": "1890s",
        "year": 1895,
        "europe_population": 6_337_000,
        "europe_pct_muslim": 0.475,
        "asia_population": 16_000_000,
        "asia_pct_muslim_low": 0.875,
        "asia_pct_muslim_high": 0.875,
        "total_population": 22_337_000,
        "total_pct_muslim": 0.762,
    },
]


def ingest(out: Path) -> int:
    rows: list[dict] = []
    for t in TABLE_4_3:
        asia_mid = None
        if t["asia_pct_muslim_low"] is not None and t["asia_pct_muslim_high"] is not None:
            asia_mid = (t["asia_pct_muslim_low"] + t["asia_pct_muslim_high"]) / 2.0
        rows.append(
            {
                "series_id": f"karpat_t43_{t['decade']}",
                "polity_id": "ottoman_empire",
                "display_name": "Ottoman Empire",
                "year": t["year"],
                "year_precision": "decade",
                "decade_label": t["decade"],
                "europe_population": t["europe_population"],
                "europe_pct_muslim": t["europe_pct_muslim"],
                "asia_population": t["asia_population"],
                "asia_pct_muslim": asia_mid,
                "asia_pct_muslim_low": t["asia_pct_muslim_low"],
                "asia_pct_muslim_high": t["asia_pct_muslim_high"],
                "total_population": t["total_population"],
                "total_pct_muslim": t["total_pct_muslim"],
                # Approximate Pew-7 residual from Muslim % only (no Christian/Jewish split).
                "shares_total_approx": (
                    {
                        "muslim": t["total_pct_muslim"],
                        "christian": 0.0,
                        "jewish": 0.0,
                        "other": round(1.0 - t["total_pct_muslim"], 4),
                        "unaffiliated": 0.0,
                        "buddhist": 0.0,
                        "hindu": 0.0,
                    }
                    if t["total_pct_muslim"] is not None
                    else None
                ),
                "confidence": 0.50,
                "source_ids": [SOURCE_ID],
                "raw_file": RAW_PDF,
                "table": "4.3",
                "notes": (
                    "Karpat Table 4.3 summary. Territorial losses change denominators "
                    "across decades — do not treat as a fixed-geography time series. "
                    "Asia Muslim % sometimes given as a range (80–90)."
                ),
            }
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = ingest(args.out)
    print(f"wrote {args.out} ({n} decade rows)")


if __name__ == "__main__":
    main()
