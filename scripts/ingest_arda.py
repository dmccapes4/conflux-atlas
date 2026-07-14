#!/usr/bin/env python3
"""Ingest ARDA National Profiles 2005 (SPSS .SAV) → religion count/share JSONL.

Counts come from World Christian Database–style fields in the ARDA extract.
They often diverge from Pew (e.g. Egypt Christian %). Confidence is capped;
use as a mid-2000s cross-check, not as a replacement for Pew anchors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import Religion, dominant_from_shares, slugify_country  # noqa: E402

SOURCE_ID = "arda_national_profiles_2005"
DEFAULT_SAV = (
    ROOT / "data" / "raw" / "arda" / "Data from the ARDA National Profiles, 2005 Update.SAV"
)
DEFAULT_OUT = ROOT / "data" / "processed" / "arda_national_profiles_2005.jsonl"

# Map ARDA count columns → Pew-7 buckets (remainder → other)
REL_COLS = {
    "CHSTIAN": Religion.CHRISTIAN.value,
    "MUSLIMS": Religion.MUSLIM.value,
    "JEWS": Religion.JEWISH.value,
    "BUDDHIST": Religion.BUDDHIST.value,
    "HINDUS": Religion.HINDU.value,
}
OTHER_COLS = (
    "BAHAIS",
    "CHINUNI",
    "CONFUCIA",
    "ETHNOREL",
    "JAINS",
    "SHINTO",
    "SIKHS",
    "SPIRITIS",
    "TAOISTS",
    "ZOROASTR",
)

# Prefer ISO3 → polity_id for demo continuity
ISO_TO_POLITY = {
    "EGY": "egypt",
    "TUR": "turkey",
    "ISR": "israel",
    "LBN": "lebanon",
    "SYR": "syria",
    "IRQ": "iraq",
    "IRN": "iran",
    "SAU": "saudi_arabia",
    "MAR": "morocco",
    "YEM": "yemen",
    "FRA": "france",
    "USA": "united_states",
    "GRC": "greece",
    "JOR": "jordan",
    "PSE": "palestine",
}


def _f(v) -> float:
    try:
        if v is None or (isinstance(v, float) and v != v):
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def ingest(sav: Path, out: Path, year: int = 2005) -> int:
    import pyreadstat

    df, _meta = pyreadstat.read_sav(sav)
    rows: list[dict] = []
    for _, r in df.iterrows():
        iso = str(r.get("ISO3") or "").strip()
        name = str(r.get("ICOUNTRY") or "").strip()
        if not name or name.lower() == "nan":
            continue
        polity_id = ISO_TO_POLITY.get(iso) or slugify_country(name)
        pop = _f(r.get("POPWCD"))
        if pop <= 0:
            continue

        counts: dict[str, float] = {rel.value: 0.0 for rel in Religion}
        for col, rel in REL_COLS.items():
            counts[rel] += _f(r.get(col))
        other = sum(_f(r.get(c)) for c in OTHER_COLS)
        counts[Religion.OTHER.value] += other
        # unaffiliated not in this extract
        counted = sum(counts.values())
        if counted <= 0:
            continue
        # If WCD groups leave a residual vs POPWCD, fold into other
        residual = pop - counted
        if residual > 0:
            counts[Religion.OTHER.value] += residual
            counted = pop
        shares = {k: (v / counted if counted else 0.0) for k, v in counts.items()}
        # drop empty keys optional — keep all Pew-7 for schema friendliness
        for rel in Religion:
            shares.setdefault(rel.value, 0.0)

        conf = 0.55
        notes = (
            "ARDA National Profiles 2005 (WCD-derived counts). "
            "Often differs from Pew; Egypt Christian % typically high vs Pew."
        )
        if polity_id == "palestine" and shares.get("jewish", 0) > 0.05:
            conf = 0.35
            notes += " Jewish share for PSE looks anomalous — treat with extreme caution."

        int_counts = {k: int(round(v)) for k, v in counts.items() if v > 0}
        rows.append(
            {
                "anchor_id": f"{SOURCE_ID}_{polity_id}_{year}",
                "polity_id": polity_id,
                "year": year,
                "year_precision": "decade",
                "total_population": int(round(pop)),
                "shares": shares,
                "dominant_religion": dominant_from_shares(shares).value,
                "confidence": conf,
                "source_ids": [SOURCE_ID],
                "notes": notes,
                "display_name": name,
                "country_code": iso or None,
                "counts": int_counts,
            }
        )

    rows.sort(key=lambda x: x["polity_id"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sav", type=Path, default=DEFAULT_SAV)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--year", type=int, default=2005)
    args = p.parse_args()
    n = ingest(args.sav, args.out, args.year)
    print(f"wrote {args.out} ({n} country rows)")


if __name__ == "__main__":
    main()
