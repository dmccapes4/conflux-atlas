#!/usr/bin/env python3
"""Ingest Arab Barometer Q1012 religion → country×wave share JSONL.

Survey self-ID composition — **not** census religion shares. Confidence capped.
Skips refused/missing from the denominator. Uses WT/wt when present.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "arab_barometer"
DEFAULT_DIR = ROOT / "data" / "raw" / "arab_barometer"
DEFAULT_OUT = ROOT / "data" / "processed" / "arab_barometer_religion_shares.jsonl"

# Official AB COUNTRY codes (stable across waves)
COUNTRY_TO_POLITY: dict[int, str] = {
    1: "algeria",
    5: "egypt",
    7: "iraq",
    8: "jordan",
    9: "kuwait",
    10: "lebanon",
    11: "libya",
    12: "mauritania",
    13: "morocco",
    14: "oman",
    15: "palestine",
    16: "qatar",
    17: "saudi_arabia",
    19: "sudan",
    21: "tunisia",
    22: "yemen",
}

COUNTRY_DISPLAY = {
    "algeria": "Algeria",
    "egypt": "Egypt",
    "iraq": "Iraq",
    "jordan": "Jordan",
    "kuwait": "Kuwait",
    "lebanon": "Lebanon",
    "libya": "Libya",
    "mauritania": "Mauritania",
    "morocco": "Morocco",
    "oman": "Oman",
    "palestine": "Palestine",
    "qatar": "Qatar",
    "saudi_arabia": "Saudi Arabia",
    "sudan": "Sudan",
    "tunisia": "Tunisia",
    "yemen": "Yemen",
}

NAME_TO_COUNTRY_CODE = {v.lower(): k for k, v in {
    1: "Algeria",
    5: "Egypt",
    7: "Iraq",
    8: "Jordan",
    9: "Kuwait",
    10: "Lebanon",
    11: "Libya",
    12: "Mauritania",
    13: "Morocco",
    14: "Oman",
    15: "Palestine",
    16: "Qatar",
    17: "Saudi Arabia",
    19: "Sudan",
    21: "Tunisia",
    22: "Yemen",
}.items()}
# Kingdom of Saudi Arabia variant
NAME_TO_COUNTRY_CODE["kingdom of saudi arabia"] = 17
NAME_TO_COUNTRY_CODE["saudi arabia"] = 17

# Wave metadata: approximate fieldwork mid-year
WAVE_META: dict[str, dict] = {
    "ABII": {"wave": "II", "year": 2011},
    "ABIII": {"wave": "III", "year": 2013},
    "ABIV": {"wave": "IV", "year": 2016},
    "WaveV": {"wave": "V", "year": 2019},
    "WaveVI": {"wave": "VI", "year": 2021},
    "WaveVII": {"wave": "VII", "year": 2022},
    "WaveVIII": {"wave": "VIII", "year": 2024},
}


def _wave_key(filename: str) -> str | None:
    f = filename.lower()
    # Most-specific first (wave-vi contains wave-v; waveviii contains wavev)
    if re.search(r"(^|[^a-z])abii([^a-z]|$)", f) and "abiii" not in f:
        return "ABII"
    if "abiii" in f:
        return "ABIII"
    if "abiv" in f:
        return "ABIV"
    if re.search(r"wave[_\s-]*viii|waveviii", f):
        return "WaveVIII"
    if re.search(r"(^|[^a-z])ab7([^0-9a-z]|$)|wave[_\s-]*vii([^i]|$)|wavevii([^i]|$)", f):
        return "WaveVII"
    if re.search(r"wave[_\s-]*vi([^i]|$)|wave[_-]?6([^0-9]|$)", f):
        return "WaveVI"
    if re.search(r"wave[_\s-]*v([^i]|$)|wavev([^i]|$)", f):
        return "WaveV"
    return None


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if v != v:  # NaN
            return None
        return float(v)
    s = str(v).strip()
    if s in {"", "NA", "na", "None", "."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _country_code(v) -> int | None:
    # "5. Egypt" or "5" or 5.0 or "Egypt" / "Algeria"
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in {"na", "none", "."}:
        return None
    m = re.match(r"^(\d+)", s)
    if m:
        return int(m.group(1))
    # Strip leading "N. " if present after failed digit-only
    m2 = re.match(r"^\d+\.\s*(.+)$", s)
    label = (m2.group(1) if m2 else s).strip().lower()
    return NAME_TO_COUNTRY_CODE.get(label)


def _map_religion(raw) -> str | None:
    """Map Q1012 raw value → Pew-7 bucket, or None to exclude."""
    if raw is None:
        return None
    if isinstance(raw, float) and raw != raw:
        return None
    s = str(raw).strip().lower()
    if s in {"", "na", "none", ".", "0", "0.0", "0. missing"}:
        return None
    # Numeric codes (common across recent waves)
    try:
        code = int(float(s.split()[0].rstrip(".")))
    except ValueError:
        code = None
        text = s
    else:
        text = s

    if code is not None:
        if code in {98, 99, 100, -8, -9, 99999}:
            return None
        if code == 1:
            return "muslim"
        if code == 2:
            return "christian"
        if code == 3:
            # Wave V: Jewish; some waves: Other
            if "jewish" in text:
                return "jewish"
            if "other" in text or "something" in text:
                return "other"
            return "other"
        if code == 4:
            return "unaffiliated"  # no religion / atheist
        if code in {5, 90}:
            return "other"
        return None

    if "muslim" in text:
        return "muslim"
    if "christian" in text:
        return "christian"
    if "jewish" in text:
        return "jewish"
    if "atheist" in text or "no religion" in text or "unspecific" in text:
        return "unaffiliated"
    if "other" in text or "something" in text:
        return "other"
    if "declined" in text or "refus" in text or "missing" in text or "don't know" in text or "dont know" in text:
        return None
    return None


def _iter_zip_rows(zpath: Path):
    """Yield (row_dict) from first CSV or DTA member."""
    with zipfile.ZipFile(zpath) as zf:
        members = [
            n
            for n in zf.namelist()
            if not n.startswith("__MACOSX") and not n.endswith("/")
        ]
        dta = [n for n in members if n.lower().endswith(".dta")]
        csv_m = [n for n in members if n.lower().endswith(".csv")]
        if dta:
            import pyreadstat

            with tempfile.TemporaryDirectory() as td:
                zf.extract(dta[0], td)
                path = Path(td) / dta[0]
                df, _meta = pyreadstat.read_dta(str(path))
                for _, series in df.iterrows():
                    yield series.to_dict()
            return
        if csv_m:
            with zf.open(csv_m[0]) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
                reader = csv.DictReader(text)
                for row in reader:
                    yield row


def _pick(row: dict, *names: str):
    lower = {str(k).lower(): k for k in row}
    for n in names:
        if n in row:
            return row[n]
        if n.lower() in lower:
            return row[lower[n.lower()]]
    return None


def aggregate_zip(zpath: Path) -> list[dict]:
    wk = _wave_key(zpath.name)
    if not wk:
        return []
    meta = WAVE_META[wk]
    # country → religion → weight sum
    tallies: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    n_raw: dict[int, int] = defaultdict(int)
    n_valid: dict[int, int] = defaultdict(int)

    for row in _iter_zip_rows(zpath):
        ccode = _country_code(_pick(row, "COUNTRY", "country"))
        if ccode is None or ccode not in COUNTRY_TO_POLITY:
            continue
        n_raw[ccode] += 1
        rel = _map_religion(_pick(row, "Q1012", "q1012"))
        if rel is None:
            continue
        wt = _to_float(_pick(row, "WT", "wt", "weight", "wt_final"))
        if wt is None or wt <= 0:
            wt = 1.0
        tallies[ccode][rel] += wt
        n_valid[ccode] += 1

    out: list[dict] = []
    for ccode, rel_w in sorted(tallies.items()):
        denom = sum(rel_w.values())
        if denom <= 0 or n_valid[ccode] < 50:
            continue
        shares = {
            "muslim": 0.0,
            "christian": 0.0,
            "jewish": 0.0,
            "unaffiliated": 0.0,
            "other": 0.0,
            "buddhist": 0.0,
            "hindu": 0.0,
        }
        for k, w in rel_w.items():
            shares[k] = w / denom
        # Normalize tiny float drift
        ssum = sum(shares.values())
        if ssum > 0:
            shares = {k: v / ssum for k, v in shares.items()}
        polity = COUNTRY_TO_POLITY[ccode]
        dominant = max(shares, key=shares.get)
        out.append(
            {
                "anchor_id": f"arab_barometer_{meta['wave']}_{polity}",
                "polity_id": polity,
                "display_name": COUNTRY_DISPLAY.get(polity, polity),
                "year": meta["year"],
                "year_precision": "exact",
                "wave": meta["wave"],
                "shares": shares,
                "dominant_religion": dominant,
                "n_respondents_raw": n_raw[ccode],
                "n_respondents_religion": n_valid[ccode],
                "weighted": True,
                "confidence": 0.40,
                "source_ids": [SOURCE_ID],
                "raw_file": zpath.name,
                "notes": (
                    "Arab Barometer Q1012 self-identified religion (weighted when WT present). "
                    "Survey sample composition — not a census share. Some countries skip Q1012."
                ),
            }
        )
    return out


def ingest(raw_dir: Path, out: Path) -> int:
    rows: list[dict] = []
    # Wave VI is split across 3 zips — merge by polity after collecting
    wave6: dict[str, dict] = {}
    for zpath in sorted(raw_dir.glob("*.zip")):
        wk = _wave_key(zpath.name)
        part = aggregate_zip(zpath)
        if wk == "WaveVI":
            for r in part:
                # Later parts overwrite if same polity (parts are mostly disjoint countries)
                wave6[r["polity_id"]] = r
            continue
        rows.extend(part)
    rows.extend(wave6.values())

    # Dedupe key wave+polity (prefer higher n)
    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["wave"], r["polity_id"])
        prev = best.get(key)
        if prev is None or r["n_respondents_religion"] > prev["n_respondents_religion"]:
            best[key] = r
    final = sorted(best.values(), key=lambda x: (x["year"], x["wave"], x["polity_id"]))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in final:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(final)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    n = ingest(args.raw_dir, args.out)
    print(f"wrote {args.out} ({n} country×wave rows)")


if __name__ == "__main__":
    main()
