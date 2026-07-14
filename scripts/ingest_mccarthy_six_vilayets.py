#!/usr/bin/env python3
"""Ingest McCarthy Table One — Six Vilayets religious counts (contested).

Compares Armenian Patriarchate Statistics vs Ottoman registration (McCarthy's
corrected figures). Confidence capped; pair with Karpat / other cites.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "mccarthy_armenian_pop_ottoman"
DEFAULT_OUT = ROOT / "data" / "processed" / "mccarthy_six_vilayets_religion.jsonl"
RAW_PDF = "Arm-pop-Ottoman-Emp-Justin-McCarthy.pdf"

# McCarthy Table One (text-extractable). Year ~1913 publication of Patriarchate figures;
# Ottoman registration corrected for undercount — treat as ~1890s–1914 eastern provinces snapshot.
SERIES = [
    {
        "estimate_id": "patriarchate_statistics",
        "label": "Armenian Patriarchate Statistics (Léart/Zohrab)",
        "year": 1913,
        "counts": {
            "armenian_christian": 1_018_000,
            "other_christian": 165_000,
            "muslim": 1_432_000,
            "jewish": 0,
        },
        "total": 2_615_000,
        "confidence": 0.25,
        "notes": (
            "McCarthy argues these Patriarchate figures are invented (Paris 1913). "
            "Retained for contrast only — do not treat as ground truth."
        ),
    },
    {
        "estimate_id": "ottoman_registration_corrected",
        "label": "Ottoman registration (McCarthy corrected)",
        "year": 1914,
        "counts": {
            "armenian_christian": 784_917,
            "other_christian": 176_845,
            "muslim": 3_173_918,
            "jewish": 2_955,
        },
        "total": 4_138_635,
        "confidence": 0.45,
        "notes": (
            "McCarthy's Ottoman registration figures for approximate Six Vilayets "
            "borders, corrected for undercounts of women/children. Contested historiography."
        ),
    },
]


def _shares(counts: dict[str, int], total: int) -> dict[str, float]:
    christian = counts["armenian_christian"] + counts["other_christian"]
    muslim = counts["muslim"]
    jewish = counts["jewish"]
    other = max(0, total - christian - muslim - jewish)
    return {
        "christian": christian / total,
        "muslim": muslim / total,
        "jewish": jewish / total,
        "other": other / total,
        "unaffiliated": 0.0,
        "buddhist": 0.0,
        "hindu": 0.0,
    }


def ingest(out: Path) -> int:
    rows = []
    for s in SERIES:
        shares = _shares(s["counts"], s["total"])
        rows.append(
            {
                "anchor_id": f"mccarthy_six_vilayets_{s['estimate_id']}",
                "polity_id": "ottoman_six_vilayets",
                "display_name": "Ottoman Six Vilayets (eastern Anatolia)",
                "year": s["year"],
                "year_precision": "decade",
                "total_population": s["total"],
                "counts_detail": s["counts"],
                "shares": shares,
                "dominant_religion": max(shares, key=shares.get),
                "estimate_id": s["estimate_id"],
                "estimate_label": s["label"],
                "confidence": s["confidence"],
                "source_ids": [SOURCE_ID],
                "raw_file": RAW_PDF,
                "notes": s["notes"],
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
    print(f"wrote {args.out} ({n} estimate rows)")


if __name__ == "__main__":
    main()
