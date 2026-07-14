#!/usr/bin/env python3
"""Hand-seed anchors for 12 polities × 1900 / 1950 / 2000.

These are compiled ballpark estimates for the first Conflux demo slice — not
census microdata. Confidence is intentionally modest; notes flag anachronistic
borders (esp. 1900) and contested figures (Lebanon, late Ottoman Anatolia).

Writes:
  data/processed/anchors_historical_seed.jsonl
Merges into:
  data/processed/anchors.jsonl  (replaces prior hand_seed_v0 rows only)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import Anchor, Religion, YearPrecision, dominant_from_shares  # noqa: E402

OUT = ROOT / "data" / "processed" / "anchors_historical_seed.jsonl"
ANCHORS = ROOT / "data" / "processed" / "anchors.jsonl"
SOURCE = "hand_seed_v0"

# polity_id must match Pew slugify where possible
POLITIES: dict[str, dict] = {
    "egypt": {"display_name": "Egypt", "region": "Middle East-North Africa", "country_code": "818"},
    "turkey": {"display_name": "Turkey", "region": "Middle East-North Africa", "country_code": "792"},
    "israel": {"display_name": "Israel", "region": "Middle East-North Africa", "country_code": "376"},
    "lebanon": {"display_name": "Lebanon", "region": "Middle East-North Africa", "country_code": "422"},
    "syria": {"display_name": "Syria", "region": "Middle East-North Africa", "country_code": "760"},
    "iraq": {"display_name": "Iraq", "region": "Middle East-North Africa", "country_code": "368"},
    "iran": {"display_name": "Iran", "region": "Middle East-North Africa", "country_code": "364"},
    "saudi_arabia": {"display_name": "Saudi Arabia", "region": "Middle East-North Africa", "country_code": "682"},
    "morocco": {"display_name": "Morocco", "region": "Middle East-North Africa", "country_code": "504"},
    "yemen": {"display_name": "Yemen", "region": "Middle East-North Africa", "country_code": "887"},
    "france": {"display_name": "France", "region": "Europe", "country_code": "250"},
    "united_states": {"display_name": "United States", "region": "North America", "country_code": "840"},
}


def _norm(shares: dict[str, float]) -> dict[str, float]:
    """Fill missing Pew keys with 0 and renormalize to sum 1."""
    full = {r.value: float(shares.get(r.value, 0.0)) for r in Religion}
    s = sum(full.values())
    if s <= 0:
        raise ValueError("empty shares")
    return {k: v / s for k, v in full.items()}


def _counts(pop: int, shares: dict[str, float]) -> dict[str, int]:
    raw = {k: int(round(pop * v)) for k, v in shares.items() if v > 0}
    # fix rounding drift on dominant
    drift = pop - sum(raw.values())
    if drift and raw:
        dom = max(shares, key=shares.get)  # type: ignore[arg-type]
        raw[dom] = raw.get(dom, 0) + drift
    return raw


def row(
    polity_id: str,
    year: int,
    pop: int,
    shares: dict[str, float],
    confidence: float,
    notes: str,
    *,
    year_precision: YearPrecision = YearPrecision.DECADE,
    regime: str | None = None,
    source_ids: list[str] | None = None,
) -> dict:
    meta = POLITIES[polity_id]
    sh = _norm(shares)
    dom = dominant_from_shares(sh)
    src = source_ids or [SOURCE]
    a = Anchor(
        anchor_id=f"{SOURCE}_{polity_id}_{year}",
        polity_id=polity_id,
        year=year,
        year_precision=year_precision,
        total_population=pop,
        shares=sh,
        dominant_religion=dom,
        regime=regime,
        confidence=confidence,
        source_ids=src,
        notes=notes,
        display_name=meta["display_name"],
        region=meta["region"],
        country_code=meta["country_code"],
        counts=_counts(pop, sh),
    )
    return a.model_dump(mode="json")


# --- Compiled estimates -------------------------------------------------
# Pops: Maddison/UN Historical / national censuses (rounded).
# Shares: Karpat/McCarthy (Ottoman), DellaPergola (Jews), Courbage & Fargues
# (MENA Christians), Pew-adjacent modern literature for 2000.
# Israel@1900 = geographic Ottoman Palestine (anachronistic polity_id).

SEEDS: list[dict] = [
    # Egypt
    row(
        "egypt",
        1900,
        10_000_000,
        {"muslim": 0.91, "christian": 0.08, "jewish": 0.005, "other": 0.005},
        0.45,
        "Khedivate/Ottoman Egypt; Coptic share uncertain (±2–3 pp). Pop ~9–11M.",
        regime="khedivate",
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914"],
    ),
    row(
        "egypt",
        1950,
        20_400_000,
        {"muslim": 0.915, "christian": 0.08, "jewish": 0.002, "other": 0.003},
        0.55,
        "Kingdom/early republic; Jewish community already shrinking post-1948.",
        regime="kingdom",
        source_ids=[SOURCE, "owid_population"],
    ),
    row(
        "egypt",
        2000,
        68_000_000,
        {"muslim": 0.94, "christian": 0.055, "jewish": 0.0, "unaffiliated": 0.002, "other": 0.003},
        0.72,
        "Pre-Pew national estimates; Christian share often under-counted in official stats.",
        regime="republic",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # Turkey (1900 = Anatolia / late Ottoman within rough modern borders)
    row(
        "turkey",
        1900,
        13_000_000,
        {"muslim": 0.80, "christian": 0.175, "jewish": 0.01, "other": 0.015},
        0.35,
        "Anachronistic modern borders on late Ottoman Anatolia; Armenian/Greek shares contested (McCarthy vs others).",
        regime="ottoman",
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914", "mccarthy_armenian_pop_ottoman"],
    ),
    row(
        "turkey",
        1950,
        20_800_000,
        {"muslim": 0.98, "christian": 0.012, "jewish": 0.003, "other": 0.005},
        0.60,
        "Post-exchange Republic; non-Muslim minorities sharply reduced vs 1900.",
        regime="republic",
        source_ids=[SOURCE, "owid_population"],
    ),
    row(
        "turkey",
        2000,
        66_500_000,
        {"muslim": 0.985, "christian": 0.002, "jewish": 0.0003, "unaffiliated": 0.008, "other": 0.0047},
        0.75,
        "Near-homogeneous Muslim majority; unaffiliated rising but hard to measure.",
        regime="republic",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # Israel / Palestine geography
    row(
        "israel",
        1900,
        700_000,
        {"muslim": 0.82, "christian": 0.10, "jewish": 0.07, "other": 0.01},
        0.40,
        "Geographic Ottoman Palestine (not a state); polity_id=israel for demo continuity. Shares ±5 pp.",
        regime="ottoman_palestine",
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population", "karpat_ottoman_population_1830_1914"],
    ),
    row(
        "israel",
        1950,
        1_370_000,
        {"jewish": 0.875, "muslim": 0.09, "christian": 0.025, "other": 0.01},
        0.65,
        "State of Israel after 1948 war + early aliyah; Arab share within Green Line.",
        regime="israel",
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population", "cbs_population_madaf"],
    ),
    row(
        "israel",
        2000,
        6_300_000,
        {"jewish": 0.775, "muslim": 0.15, "christian": 0.02, "unaffiliated": 0.035, "other": 0.02},
        0.80,
        "CBS-adjacent national composition; Druze/other folded partly into other.",
        regime="israel",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "cbs_population_madaf", "jewishdatabank_world_jewish_population"],
    ),
    # Lebanon
    row(
        "lebanon",
        1900,
        900_000,
        {"christian": 0.55, "muslim": 0.40, "other": 0.05},
        0.35,
        "Mount Lebanon + coastal vilayets rough; sectarian shares highly contested.",
        regime="ottoman",
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914"],
    ),
    row(
        "lebanon",
        1950,
        1_300_000,
        {"christian": 0.52, "muslim": 0.44, "other": 0.04},
        0.50,
        "Independence-era estimates; last full sectarian census was 1932.",
        regime="republic",
        source_ids=[SOURCE],
    ),
    row(
        "lebanon",
        2000,
        3_800_000,
        {"muslim": 0.58, "christian": 0.38, "other": 0.04},
        0.50,
        "No official sectarian census; Muslim plurality likely by late 20th c. Treat ±8 pp.",
        regime="republic",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE],
    ),
    # Syria
    row(
        "syria",
        1900,
        1_800_000,
        {"muslim": 0.75, "christian": 0.20, "jewish": 0.015, "other": 0.035},
        0.35,
        "Approximate Syrian provinces (not full Bilad al-Sham); border anachronism.",
        regime="ottoman",
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914"],
    ),
    row(
        "syria",
        1950,
        3_500_000,
        {"muslim": 0.86, "christian": 0.12, "jewish": 0.005, "other": 0.015},
        0.50,
        "Early independence; Alawite/Druze in muslim/other fold for Pew-7 schema.",
        regime="republic",
        source_ids=[SOURCE, "owid_population"],
    ),
    row(
        "syria",
        2000,
        16_500_000,
        {"muslim": 0.90, "christian": 0.08, "unaffiliated": 0.01, "other": 0.01},
        0.60,
        "Pre-war peak; Christian share declining via emigration.",
        regime="baath",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # Iraq
    row(
        "iraq",
        1900,
        2_500_000,
        {"muslim": 0.90, "christian": 0.05, "jewish": 0.035, "other": 0.015},
        0.35,
        "Ottoman Mesopotamia vilayets; Baghdad Jewish community large for region.",
        regime="ottoman",
        source_ids=[SOURCE, "karpat_ottoman_population_1830_1914", "jewishdatabank_world_jewish_population"],
    ),
    row(
        "iraq",
        1950,
        5_200_000,
        {"muslim": 0.93, "christian": 0.04, "jewish": 0.015, "other": 0.015},
        0.55,
        "Jewish share mid-exodus (Operation Ezra & Nehemiah 1950–51) — snapshot fuzzy.",
        regime="kingdom",
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population", "owid_population"],
    ),
    row(
        "iraq",
        2000,
        23_500_000,
        {"muslim": 0.97, "christian": 0.02, "other": 0.01},
        0.60,
        "Pre-2003; Christian communities still larger than post-war remnant.",
        regime="baath",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # Iran
    row(
        "iran",
        1900,
        10_000_000,
        {"muslim": 0.98, "christian": 0.005, "jewish": 0.005, "other": 0.01},
        0.40,
        "Qajar Iran; Bahá'í/Zoroastrian folded into other.",
        regime="qajar",
        source_ids=[SOURCE],
    ),
    row(
        "iran",
        1950,
        17_000_000,
        {"muslim": 0.985, "christian": 0.004, "jewish": 0.004, "other": 0.007},
        0.55,
        "Pahlavi era; minorities small but present.",
        regime="pahlavi",
        source_ids=[SOURCE, "owid_population"],
    ),
    row(
        "iran",
        2000,
        66_000_000,
        {"muslim": 0.99, "christian": 0.003, "jewish": 0.0003, "other": 0.0067},
        0.70,
        "Islamic Republic; official Muslim near-total; unaffiliated understated.",
        regime="islamic_republic",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # Saudi Arabia
    row(
        "saudi_arabia",
        1900,
        2_000_000,
        {"muslim": 0.995, "other": 0.005},
        0.30,
        "Najd + Hijaz rough union estimate; very sparse demography.",
        regime="pre_state",
        source_ids=[SOURCE],
    ),
    row(
        "saudi_arabia",
        1950,
        3_800_000,
        {"muslim": 0.99, "christian": 0.005, "other": 0.005},
        0.45,
        "Early kingdom; oil boom migration not yet large.",
        regime="kingdom",
        source_ids=[SOURCE, "owid_population"],
    ),
    row(
        "saudi_arabia",
        2000,
        20_800_000,
        {"muslim": 0.95, "christian": 0.035, "hindu": 0.005, "other": 0.01},
        0.65,
        "Includes large non-citizen workforce (Christian/Hindu shares mostly expatriate).",
        regime="kingdom",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # Morocco
    row(
        "morocco",
        1900,
        5_000_000,
        {"muslim": 0.93, "jewish": 0.055, "christian": 0.005, "other": 0.01},
        0.40,
        "Alaouite Morocco pre-protectorate; one of largest Maghrebi Jewish communities.",
        regime="alaouite",
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
    ),
    row(
        "morocco",
        1950,
        9_000_000,
        {"muslim": 0.955, "jewish": 0.03, "christian": 0.01, "other": 0.005},
        0.55,
        "Late protectorate / early independence; Jewish emigration accelerating.",
        regime="protectorate",
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population", "owid_population"],
    ),
    row(
        "morocco",
        2000,
        28_500_000,
        {"muslim": 0.99, "jewish": 0.0002, "christian": 0.001, "unaffiliated": 0.004, "other": 0.0048},
        0.72,
        "Near-total Muslim; Jewish remnant tiny vs 1900.",
        regime="kingdom",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # Yemen
    row(
        "yemen",
        1900,
        2_500_000,
        {"muslim": 0.98, "jewish": 0.015, "other": 0.005},
        0.35,
        "Imamate / Ottoman Yemen; Jewish community later airlifted (1949–50).",
        regime="imamate",
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population"],
    ),
    row(
        "yemen",
        1950,
        4_500_000,
        {"muslim": 0.995, "jewish": 0.001, "other": 0.004},
        0.50,
        "Post–Operation Magic Carpet; Jewish share collapsed.",
        regime="imamate",
        source_ids=[SOURCE, "jewishdatabank_world_jewish_population", "owid_population"],
    ),
    row(
        "yemen",
        2000,
        17_500_000,
        {"muslim": 0.995, "other": 0.005},
        0.65,
        "Republic of Yemen; Zaydi/Sunni distinction not in Pew-7 schema.",
        regime="republic",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population"],
    ),
    # France (diaspora host)
    row(
        "france",
        1900,
        39_000_000,
        {"christian": 0.975, "jewish": 0.003, "unaffiliated": 0.015, "other": 0.007},
        0.60,
        "Third Republic; Muslim population negligible; Jewish community post-Dreyfus.",
        regime="republic",
        source_ids=[SOURCE, "owid_population"],
    ),
    row(
        "france",
        1950,
        41_800_000,
        {"christian": 0.90, "unaffiliated": 0.07, "jewish": 0.005, "muslim": 0.01, "other": 0.015},
        0.65,
        "Postwar; Algerian/Maghrebi Muslim presence beginning; Holocaust reduced Jewish pop then recovery.",
        regime="republic",
        source_ids=[SOURCE, "owid_population", "jewishdatabank_world_jewish_population"],
    ),
    row(
        "france",
        2000,
        59_000_000,
        {"christian": 0.65, "unaffiliated": 0.26, "muslim": 0.06, "jewish": 0.01, "other": 0.02},
        0.75,
        "Laïcité + immigration; Muslim/Jewish shares from survey literature (±2 pp).",
        regime="republic",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population", "jewishdatabank_world_jewish_population"],
    ),
    # United States (diaspora host)
    row(
        "united_states",
        1900,
        76_000_000,
        {"christian": 0.96, "jewish": 0.015, "unaffiliated": 0.015, "other": 0.01},
        0.70,
        "Census-era Christian near-monopoly; Jewish immigration wave underway.",
        regime="federal_republic",
        source_ids=[SOURCE, "owid_population", "jewishdatabank_world_jewish_population"],
    ),
    row(
        "united_states",
        1950,
        152_000_000,
        {"christian": 0.90, "unaffiliated": 0.05, "jewish": 0.03, "other": 0.02},
        0.75,
        "Postwar peak Jewish share; Muslim negligible.",
        regime="federal_republic",
        source_ids=[SOURCE, "owid_population", "jewishdatabank_world_jewish_population"],
    ),
    row(
        "united_states",
        2000,
        282_000_000,
        {"christian": 0.78, "unaffiliated": 0.15, "jewish": 0.018, "muslim": 0.005, "buddhist": 0.007, "hindu": 0.004, "other": 0.036},
        0.80,
        "ARIS/GSS-adjacent; Muslim still small pre-Pew 2010.",
        regime="federal_republic",
        year_precision=YearPrecision.EXACT,
        source_ids=[SOURCE, "owid_population", "arda_national_profiles_2005"],
    ),
]


def main() -> None:
    assert len(SEEDS) == 36, len(SEEDS)
    assert len(POLITIES) == 12

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for rec in SEEDS:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(SEEDS)} anchors)")

    # Merge: drop old hand_seed_v0, keep Pew + anything else, append new seeds
    kept: list[str] = []
    if ANCHORS.exists():
        for line in ANCHORS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if SOURCE in rec.get("source_ids", []) or str(rec.get("anchor_id", "")).startswith(SOURCE):
                continue
            kept.append(line)
    with ANCHORS.open("w", encoding="utf-8") as f:
        for line in kept:
            f.write(line + "\n")
        for rec in SEEDS:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"merged → {ANCHORS} ({len(kept)} prior + {len(SEEDS)} seed = {len(kept) + len(SEEDS)})")


if __name__ == "__main__":
    main()
