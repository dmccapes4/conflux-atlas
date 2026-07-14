#!/usr/bin/env python3
"""Ingest Pew Religious Composition 2010–2020 → data/processed/anchors.jsonl."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import (  # noqa: E402
    PEW_RELIGION_COLUMNS,
    Anchor,
    YearPrecision,
    dominant_from_shares,
    parse_int_count,
    shares_from_pew_percent_row,
    slugify_country,
)

SOURCE_ID = "pew_global_religious_composition_2010_2020"
DEFAULT_RAW = (
    ROOT
    / "data"
    / "raw"
    / "Religious-Composition-2010-2020-dataset"
    / "Religious Composition 2010-2020 dataset"
)
DEFAULT_OUT = ROOT / "data" / "processed" / "anchors.jsonl"

# Tiny absolute counts among core Conflux religions → slight confidence haircut.
# Ignore buddhist/hindu/other micro-counts (e.g. Israel Buddhists) for this score.
SMALL_COUNT_THRESHOLD = 10_000
CORE_RELIGIONS = frozenset({"christian", "muslim", "jewish", "unaffiliated"})
BASE_CONFIDENCE = 0.92
SMALL_MINORITY_CONFIDENCE = 0.85


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _confidence(counts: dict[str, int], total: int) -> float:
    if total <= 0:
        return 0.5
    for rel, n in counts.items():
        if rel in CORE_RELIGIONS and 0 < n < SMALL_COUNT_THRESHOLD:
            return SMALL_MINORITY_CONFIDENCE
    return BASE_CONFIDENCE


def ingest(raw_dir: Path, out_path: Path) -> int:
    pct_path = raw_dir / "Religious Composition 2010-2020 (percentages).csv"
    unr_path = raw_dir / "Religious Composition 2010-2020 (unrounded counts).csv"
    if not pct_path.is_file() or not unr_path.is_file():
        raise FileNotFoundError(f"missing Pew CSVs under {raw_dir}")

    pct_rows = _load_csv(pct_path)
    unr_rows = _load_csv(unr_path)
    unr_idx = {(r["Country"], r["Year"]): r for r in unr_rows}

    anchors: list[Anchor] = []
    for row in pct_rows:
        if row.get("Level") != "1":
            continue
        country = row["Country"]
        year = int(row["Year"])
        polity_id = slugify_country(country)
        shares = shares_from_pew_percent_row(row)
        total = parse_int_count(row["Population"])

        unr = unr_idx.get((country, str(year)), {})
        counts = {
            PEW_RELIGION_COLUMNS[col].value: parse_int_count(unr.get(col))
            for col in PEW_RELIGION_COLUMNS
        }
        # Prefer unrounded population when present
        if unr.get("Population"):
            total = parse_int_count(unr["Population"])

        conf = _confidence(counts, total)
        notes = ""
        if conf < BASE_CONFIDENCE:
            notes = (
                f"At least one religion has unrounded count < {SMALL_COUNT_THRESHOLD}; "
                "treat small minorities cautiously."
            )

        anchor = Anchor(
            anchor_id=f"pew_{polity_id}_{year}",
            polity_id=polity_id,
            year=year,
            year_precision=YearPrecision.EXACT,
            total_population=total,
            shares=shares,
            dominant_religion=dominant_from_shares(shares),
            regime=None,
            confidence=conf,
            source_ids=[SOURCE_ID],
            notes=notes,
            display_name=country,
            region=row.get("Region"),
            country_code=str(row.get("Countrycode") or ""),
            counts=counts,
        )
        anchors.append(anchor)

    anchors.sort(key=lambda a: (a.polity_id, a.year))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for a in anchors:
            f.write(json.dumps(a.model_dump(mode="json"), ensure_ascii=False) + "\n")

    return len(anchors)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = ingest(args.raw_dir, args.out)
    print(f"Wrote {n} anchors → {args.out}")


if __name__ == "__main__":
    main()
