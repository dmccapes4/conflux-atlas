#!/usr/bin/env python3
"""Ingest Basihos (2016/2018) Ottoman population within modern Turkey borders.

Parses Appendix Table 3 from the SSRN PDF in data/raw/ottoman/.
Geography is *modern Turkey borders*, not the full Ottoman Empire — polity_id
`turkey_modern_borders` to avoid colliding with empire-wide series.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "seda_basihos_ottoman_population_2016"
DEFAULT_PDF = ROOT / "data" / "raw" / "ottoman" / "Ottoman-Population-Seda-Basihos-2016.pdf"
DEFAULT_OUT = ROOT / "data" / "processed" / "basihos_turkey_borders_population.jsonl"

POLITY_ID = "turkey_modern_borders"


def parse_table3(text: str) -> list[tuple[int, int]]:
    """Extract (year, population) pairs from Table 3 block."""
    # Numbers appear as "6 947 125" (space thousands) or "6947125"
    rows: list[tuple[int, int]] = []
    # Match year then spaced integer on same/near line
    for m in re.finditer(
        r"\b(1[5-9]\d{2}|20\d{2})\s+(\d{1,3}(?:\s\d{3})+|\d{6,})\b",
        text,
    ):
        year = int(m.group(1))
        pop = int(m.group(2).replace(" ", ""))
        if 1500 <= year <= 1930 and 1_000_000 <= pop <= 30_000_000:
            rows.append((year, pop))
    # Dedupe by year (table printed in three columns)
    by_year: dict[int, int] = {}
    for y, p in rows:
        by_year[y] = p
    return sorted(by_year.items())


def ingest(pdf: Path, out: Path) -> int:
    import pypdf

    reader = pypdf.PdfReader(str(pdf))
    blob = "\n".join((page.extract_text() or "") for page in reader.pages)
    # Prefer appendix Table 3 section
    idx = blob.find("Table 3: Ottoman Population within the current Borders")
    chunk = blob[idx : idx + 1500] if idx >= 0 else blob
    pairs = parse_table3(chunk)
    if len(pairs) < 10:
        # Fallback: whole doc, keep known construction years only
        known = {
            1520, 1535, 1580, 1620, 1785, 1820, 1831, 1874, 1881, 1884, 1897, 1910, 1913, 1920, 1923, 1927
        }
        pairs = [(y, p) for y, p in parse_table3(blob) if y in known]

    rows = []
    for year, pop in pairs:
        rows.append(
            {
                "series_id": f"basihos_turkey_borders_{year}",
                "polity_id": POLITY_ID,
                "display_name": "Turkey (modern borders)",
                "year": year,
                "year_precision": "exact",
                "total_population": pop,
                "confidence": 0.55,
                "source_ids": [SOURCE_ID],
                "raw_file": pdf.name,
                "notes": (
                    "Basihos reconstruction of Ottoman-era population living within "
                    "current borders of the Republic of Turkey (Appendix Table 3). "
                    "Not empire-wide; not religion shares."
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
    p.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = ingest(args.pdf, args.out)
    print(f"wrote {args.out} ({n} year rows)")


if __name__ == "__main__":
    main()
