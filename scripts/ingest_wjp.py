#!/usr/bin/env python3
"""Ingest World Jewish Population (AJYB / DellaPergola) PDF tables → JSONL.

Extracts:
  - Table 1 world core Jewish population time series (prefer revised estimates)
    → data/processed/wjp_world_core_jewish_population.jsonl
  - Country core Jewish population (CJP) rows from 2023 appendix + 1970 Shapiro
    country tables → data/processed/wjp_country_core_jewish_population.jsonl

PDF tables that are image-only are skipped; text-extractable pages only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import slugify_country  # noqa: E402

SOURCE_ID = "jewishdatabank_world_jewish_population"
DEFAULT_PDF_DIR = ROOT / "data" / "raw" / "jewishdatabank" / "pdfs"
DEFAULT_OUT_WORLD = ROOT / "data" / "processed" / "wjp_world_core_jewish_population.jsonl"
DEFAULT_OUT_COUNTRY = ROOT / "data" / "processed" / "wjp_country_core_jewish_population.jsonl"

# Explicit polity_id overrides for Conflux demo continuity
NAME_TO_POLITY: dict[str, str] = {
    "united states": "united_states",
    "us": "united_states",
    "u.s.": "united_states",
    "u.s.a.": "united_states",
    "great britain": "united_kingdom",
    "united kingdom": "united_kingdom",
    "uk": "united_kingdom",
    "soviet union": "soviet_union",
    "ussr": "soviet_union",
    "russia": "russia",
    "russian federation": "russia",
    "czechoslovakia": "czechoslovakia",
    "republic of south africa": "south_africa",
    "south africa": "south_africa",
    "syria and lebanon": "syria_lebanon_combined",
    "total state of israel": "israel",
    "state of israel": "israel",
    "israel": "israel",
    "west bank": "west_bank_settlements",
    "gaza": "gaza",
    "france": "france",
    "turkey": "turkey",
    "iran": "iran",
    "egypt": "egypt",
    "iraq": "iraq",
    "syria": "syria",
    "lebanon": "lebanon",
    "morocco": "morocco",
    "tunisia": "tunisia",
    "algeria": "algeria",
    "libya": "libya",
    "yemen": "yemen",
    "ethiopia": "ethiopia",
    "canada": "canada",
    "argentina": "argentina",
    "germany": "germany",
    "australia": "australia",
    "brazil": "brazil",
    "hungary": "hungary",
    "mexico": "mexico",
    "ukraine": "ukraine",
    "netherlands": "netherlands",
    "belgium": "belgium",
    "italy": "italy",
    "switzerland": "switzerland",
    "greece": "greece",
    "jordan": "jordan",
    "india": "india",
    "china": "china",
    "japan": "japan",
    "united arab emirates": "uae",
}

SKIP_NAME_PREFIXES = (
    "total",
    "rest of",
    "europe",
    "america",
    "asia",
    "africa",
    "oceania",
    "european union",
    "former",
    "fsu",
    "other",
    "north",
    "central",
    "south america",
)

NUM = r"\d{1,3}(?:,\d{3})+|\d+"


def _parse_int(s: str) -> int | None:
    s = s.replace(",", "").strip()
    if not s or s in {".", "-", "—"}:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _polity_for(name: str) -> str:
    key = name.strip().lower()
    key = re.sub(r"\s+", " ", key)
    if key in NAME_TO_POLITY:
        return NAME_TO_POLITY[key]
    return slugify_country(name)


# Names that appear in appendix with glued footnote letters (Turkeyl, Israelo, …)
_FOOTNOTE_BASES = {
    *NAME_TO_POLITY.keys(),
    "israel",
    "total state of israel",
    "state of israel",
    "turkey",
    "russia",
    "china",
    "west bank",
    "united kingdom",
    "gaza",
    "czechia",
    "slovakia",
    "serbia",
    "croatia",
    "slovenia",
    "estonia",
    "latvia",
    "lithuania",
    "belarus",
    "moldova",
    "ukraine",
    "azerbaijan",
    "kazakhstan",
    "uzbekistan",
    "georgia",
    "armenia",
    "kyrgyzstan",
    "turkmenistan",
    "singapore",
    "philippines",
    "indonesia",
    "thailand",
    "taiwan",
    "japan",
    "india",
    "ethiopia",
    "morocco",
    "tunisia",
    "egypt",
    "iran",
    "france",
    "germany",
    "brazil",
    "mexico",
    "argentina",
    "uruguay",
    "chile",
    "venezuela",
    "paraguay",
    "peru",
    "suriname",
    "panama",
    "gibraltar",
    "monaco",
    "channel islands",
    "bosnia-herzegovina",
    "north macedonia",
    "south korea",
    "sri lanka",
    "united arab emirates",
    "botswana",
    "kenya",
    "madagascar",
    "congo d.r.",
}


def _strip_footnote_letter(name: str) -> str:
    """Strip DellaPergola glued footnote letters (Turkeyl, Israelo, West Bankp)."""
    name = name.strip()
    # [Total State of Israel]i → Total State of Israel
    name = re.sub(r"^\[", "", name)
    name = re.sub(r"\][a-z]?$", "", name)
    name = name.strip("[]").strip()
    low = name.lower()
    if low in _FOOTNOTE_BASES or low in NAME_TO_POLITY:
        return name
    m = re.match(r"^(.+)([a-z])$", name)
    if not m:
        return name
    base = m.group(1).rstrip()
    if base.lower() in _FOOTNOTE_BASES or base.lower() in NAME_TO_POLITY:
        return base
    return name


def _should_skip_country(name: str) -> bool:
    low = name.lower().strip()
    if not low or low.startswith("["):
        return True
    if low.startswith("total ") and "israel" not in low:
        return True
    return any(low.startswith(p) for p in SKIP_NAME_PREFIXES if p != "total")


def _load_pdf_text(path: Path) -> list[str]:
    import pypdf

    reader = pypdf.PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def parse_table1_world(pages: list[str], pdf_name: str) -> list[dict]:
    """Parse DellaPergola Table 1 world CJP series (original + revised)."""
    blob = "\n".join(pages[:20])
    if "Table 1 World core Jewish population" not in blob and "Table 1 World core Jewish" not in blob:
        # older wording
        if "World core Jewish population estimates" not in blob:
            return []

    rows: list[dict] = []
    # 1900, Jan. 1 10,728,500 10,600,000 1.55 1,625 ...
    line_re = re.compile(
        rf"^(?P<year>\d{{4}})(?:,\s*(?:Jan\.?\s*1|May\s*1))?\s+"
        rf"(?P<a>{NUM})(?:\s+(?P<b>{NUM}))?",
        re.M,
    )
    for m in line_re.finditer(blob):
        year = int(m.group("year"))
        if year < 1800 or year > 2100:
            continue
        original = _parse_int(m.group("a"))
        revised = _parse_int(m.group("b")) if m.group("b") else None
        if original is None or original < 1_000_000:
            continue
        if revised is not None and revised >= 1_000_000:
            best = revised
            estimate_kind = "revised"
        else:
            best = original
            estimate_kind = "original"
            revised = None
        rows.append(
            {
                "series_id": f"wjp_world_cjp_{year}",
                "year": year,
                "year_precision": "exact",
                "core_jewish_population": best,
                "original_estimate": original,
                "revised_estimate": revised,
                "estimate_kind": estimate_kind,
                "confidence": 0.75 if estimate_kind == "revised" else 0.65,
                "source_ids": [SOURCE_ID],
                "raw_file": pdf_name,
                "notes": (
                    "World core Jewish population (CJP) from DellaPergola AJYB Table 1. "
                    "Prefer revised estimate when published."
                ),
            }
        )
    # Dedupe by year keeping last (table may appear twice)
    by_year: dict[int, dict] = {}
    for r in rows:
        by_year[r["year"]] = r
    return [by_year[y] for y in sorted(by_year)]


def parse_appendix_countries(pages: list[str], pdf_name: str, year: int) -> list[dict]:
    """Parse DellaPergola appendix country rows only (not ranked % tables).

    Appendix line shape:
      France 65,800,000 440,000 6.69 S B 2018  ...
    Require xx.xx rate + source-type letter so Table 4/6 false matches drop out.
    """
    row_re = re.compile(
        rf"^(?P<name>\[?[A-Z][A-Za-z \-\.']+?\]?[a-z]?)\s+"
        rf"(?P<total>{NUM})\s+(?P<cjp>{NUM})\s+(?P<per>\d+\.\d{{2}})\s+"
        rf"(?P<source>[A-Z]{{1,3}}(?:,[A-Z])*)\b",
        re.M,
    )
    out: list[dict] = []
    by_polity: dict[str, dict] = {}
    # Only scan pages that look like the country appendix
    for page in pages:
        if "Accuracy" not in page and "populationb" not in page and "Law of" not in page:
            if "Core\nJewish\npopulation" not in page and "Core Jewish" not in page:
                continue
            if "Jews per" not in page and "per \ntotal 1000" not in page and "1000" not in page:
                continue
        for m in row_re.finditer(page):
            name = _strip_footnote_letter(m.group("name"))
            name = name.strip("[]")
            if _should_skip_country(name):
                continue
            total = _parse_int(m.group("total"))
            cjp = _parse_int(m.group("cjp"))
            if total is None or cjp is None or cjp > total:
                continue
            per = float(m.group("per"))
            if per > 1000:
                continue
            polity = _polity_for(name)
            rec = {
                "anchor_id": f"wjp_cjp_{polity}_{year}",
                "polity_id": polity,
                "display_name": name,
                "year": year,
                "year_precision": "exact",
                "core_jewish_population": cjp,
                "total_population": total,
                "jews_per_1000": per,
                "source_type": m.group("source"),
                "confidence": 0.70,
                "source_ids": [SOURCE_ID],
                "raw_file": pdf_name,
                "definition": "core_jewish_population",
                "notes": (
                    "AJYB/DellaPergola appendix country CJP. "
                    "Not a full religion-share anchor — Jewish headcount only."
                ),
            }
            prev = by_polity.get(polity)
            # Prefer Total State of Israel over regional Israel/West Bank slices
            if polity == "israel":
                if "total state of israel" in name.lower() or name.lower() == "state of israel":
                    by_polity[polity] = rec
                elif prev is None:
                    by_polity[polity] = rec
                continue
            if prev is None or cjp > prev["core_jewish_population"]:
                by_polity[polity] = rec
    return list(by_polity.values())


def parse_shapiro_1970_tables(pages: list[str], pdf_name: str) -> list[dict]:
    """Parse Shapiro 1970 continental country tables (Total + Jewish columns)."""
    blob = "\n".join(pages)
    # Country  TotalPop  JewishPop — Jewish may use 1.4501 footnote glued
    row_re = re.compile(
        rf"^(?P<name>[A-Z][A-Za-z \.\-']+(?:\s+\([^)]+\))?)\s+"
        rf"(?P<total>{NUM})\s+(?P<jews>{NUM})(?P<foot>[a-zxz*]*)\s*$",
        re.M,
    )
    out: list[dict] = []
    seen: set[str] = set()
    for m in row_re.finditer(blob):
        name = m.group("name").strip().rstrip(".")
        name = re.sub(r"\s+\.\.+$", "", name).strip()
        if _should_skip_country(name):
            continue
        if name.lower() in {"country", "city"}:
            continue
        total = _parse_int(m.group("total"))
        jews = _parse_int(m.group("jews"))
        if total is None or jews is None:
            continue
        if jews > total:
            continue
        # Filter city-table false positives: cities lack huge totals paired oddly —
        # require total pop >= 100k or known micro-states
        if total < 25_000 and name.lower() not in {"gibraltar", "malta", "luxembourg"}:
            continue
        polity = _polity_for(name)
        if polity in seen:
            continue
        seen.add(polity)
        out.append(
            {
                "anchor_id": f"wjp_cjp_{polity}_1970",
                "polity_id": polity,
                "display_name": name,
                "year": 1970,
                "year_precision": "exact",
                "core_jewish_population": jews,
                "total_population": total,
                "jews_per_1000": round(1000.0 * jews / total, 3) if total else None,
                "confidence": 0.60,
                "source_ids": [SOURCE_ID],
                "raw_file": pdf_name,
                "definition": "estimated_jewish_population",
                "notes": (
                    "Shapiro AJYB 1971 country tables (end-1970 estimates). "
                    "Pre-DellaPergola CJP methodology; confidence capped."
                ),
            }
        )
    return out


def find_pdf(pdf_dir: Path, prefix: str) -> Path | None:
    hits = sorted(pdf_dir.glob(f"{prefix}*.pdf"))
    return hits[0] if hits else None


def ingest(pdf_dir: Path, out_world: Path, out_country: Path) -> tuple[int, int]:
    world_rows: list[dict] = []
    country_rows: list[dict] = []

    pdf_2023 = find_pdf(pdf_dir, "2023")
    if pdf_2023:
        pages = _load_pdf_text(pdf_2023)
        world_rows = parse_table1_world(pages, pdf_2023.name)
        country_rows.extend(parse_appendix_countries(pages, pdf_2023.name, 2023))
    # Fallback Table 1 from 2022 / 2020 if 2023 missing
    if not world_rows:
        for prefix in ("2022", "2021", "2020"):
            pdf = find_pdf(pdf_dir, prefix)
            if not pdf:
                continue
            world_rows = parse_table1_world(_load_pdf_text(pdf), pdf.name)
            if world_rows:
                break

    pdf_1970 = find_pdf(pdf_dir, "1970")
    if pdf_1970:
        country_rows.extend(parse_shapiro_1970_tables(_load_pdf_text(pdf_1970), pdf_1970.name))

    out_world.parent.mkdir(parents=True, exist_ok=True)
    with out_world.open("w", encoding="utf-8") as f:
        for r in world_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with out_country.open("w", encoding="utf-8") as f:
        for r in sorted(country_rows, key=lambda x: (x["year"], x["polity_id"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(world_rows), len(country_rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    p.add_argument("--out-world", type=Path, default=DEFAULT_OUT_WORLD)
    p.add_argument("--out-country", type=Path, default=DEFAULT_OUT_COUNTRY)
    args = p.parse_args()
    n_w, n_c = ingest(args.pdf_dir, args.out_world, args.out_country)
    print(f"wrote {args.out_world} ({n_w} world years)")
    print(f"wrote {args.out_country} ({n_c} country rows)")


if __name__ == "__main__":
    main()
