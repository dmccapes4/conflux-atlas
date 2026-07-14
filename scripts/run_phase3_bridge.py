#!/usr/bin/env python3
"""Fit 1920+ dynamics, backfill sparse eras, settle historical holdouts → PHASE3_BRIDGE.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.bridge import backfill_series, fit_dynamics, settle_backfill  # noqa: E402
from conflux.learning import TrustStore  # noqa: E402
from conflux.schema import Anchor, dominant_from_shares  # noqa: E402
from conflux.settlement import calibration_table  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
DEFAULT_OUT = ROOT / "data-validation-reports" / "PHASE3_BRIDGE.json"
DEFAULT_ANCHORS = PROCESSED / "anchors.jsonl"

HOLDOUT_SOURCES = (
    "ottoman_demographics_wiki",
    "karpat_ottoman_population_1830_1914",
    "seda_basihos_ottoman_population_2016",
    "mccarthy_armenian_pop_ottoman",
)


def _load_anchors(path: Path) -> list[Anchor]:
    rows: list[Anchor] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(Anchor.model_validate(json.loads(line)))
    return rows


def _shares_muslim(share: float) -> dict[str, float]:
    s = max(0.0, min(1.0, float(share)))
    return {
        "muslim": s,
        "christian": max(0.0, 1.0 - s - 0.01),
        "jewish": 0.0,
        "other": 0.01 if s < 0.99 else 0.0,
        "unaffiliated": 0.0,
        "buddhist": 0.0,
        "hindu": 0.0,
    }


def _anchor(
    *,
    aid: str,
    polity_id: str,
    year: int,
    muslim: float,
    confidence: float,
    source: str,
    pop: int = 1_000_000,
) -> Anchor:
    shares = _shares_muslim(muslim)
    # renormalize tiny float drift
    total = sum(shares.values())
    shares = {k: v / total for k, v in shares.items()}
    return Anchor(
        anchor_id=aid,
        polity_id=polity_id,
        year=year,
        total_population=pop,
        shares=shares,
        dominant_religion=dominant_from_shares(shares),
        confidence=confidence,
        source_ids=[source],
    )


def _karpat_holdouts() -> list[Anchor]:
    path = PROCESSED / "karpat_religious_structure_summary.jsonl"
    out: list[Anchor] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            share = rec.get("total_pct_muslim")
            if share is None:
                continue
            out.append(
                _anchor(
                    aid=str(rec.get("series_id", f"karpat_{rec['year']}")),
                    polity_id=str(rec["polity_id"]),
                    year=int(rec["year"]),
                    muslim=float(share),
                    confidence=float(rec.get("confidence", 0.5)),
                    source="karpat_ottoman_population_1830_1914",
                    pop=int(rec["total_population"] or 20_000_000),
                )
            )
    return out


def _mccarthy_holdouts() -> list[Anchor]:
    path = PROCESSED / "mccarthy_six_vilayets_religion.jsonl"
    out: list[Anchor] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            out.append(Anchor.model_validate(json.loads(line)))
    return out


def _ottoman_province_holdouts() -> list[Anchor]:
    path = PROCESSED / "ottoman_1914_provinces.jsonl"
    out: list[Anchor] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            share = rec.get("muslim_share")
            prov = rec.get("province")
            year = rec.get("year")
            if share is None or not prov or year is None:
                continue
            pid = "ottoman_province_" + str(prov).strip().lower().replace(" ", "_")
            out.append(
                _anchor(
                    aid=f"ottoman_prov_{pid}_{year}",
                    polity_id=pid,
                    year=int(year),
                    muslim=float(share),
                    confidence=float(rec.get("confidence", 0.4)),
                    source="ottoman_demographics_wiki",
                    pop=int(rec.get("total_population") or 1_000_000),
                )
            )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    p.add_argument("--fit-start", type=int, default=1920)
    p.add_argument("--groups", nargs="+", default=["muslim", "christian", "jewish"])
    args = p.parse_args()

    modern = _load_anchors(args.anchors)
    dynamics = fit_dynamics(modern, groups=args.groups, fit_start=args.fit_start)

    karpat = _karpat_holdouts()
    mccarthy = _mccarthy_holdouts()
    provinces = _ottoman_province_holdouts()

    # Basihos is population-only (no religion shares) — cannot settle share bands.
    basihos_path = PROCESSED / "basihos_turkey_borders_population.jsonl"
    n_basihos = 0
    if basihos_path.exists():
        n_basihos = sum(1 for line in basihos_path.open() if line.strip())

    store = TrustStore()
    n_settled = n_hits = n_excluded = 0
    protocol_notes: list[str] = []

    # Karpat LOO: each year estimated from the other Karpat anchors.
    if len(karpat) >= 2:
        for hold in karpat:
            support = [(a.year, float(a.shares["muslim"])) for a in karpat if a.year != hold.year]
            estimates = backfill_series(
                support, dynamics, years=[hold.year], coverage=0.80
            )
            res = settle_backfill(estimates, [hold], store, group="muslim")
            n_settled += res["n_settled"]
            n_hits += res["n_hits"]
            n_excluded += res["n_excluded_contested"]
        protocol_notes.append(
            f"karpat_loo: {len(karpat)} holdouts settled against sibling Karpat anchors"
        )
    else:
        protocol_notes.append("karpat_loo: skipped (need ≥2 share rows)")

    # McCarthy: must be counted as contested exclusions, never settled.
    if mccarthy:
        # Need some estimate years present so exclusion path is exercised.
        years = sorted({a.year for a in mccarthy})
        # Dummy support from Karpat empire series if available, else self-gap.
        support = [(a.year, float(a.shares["muslim"])) for a in karpat] or [
            (1900, 0.7),
            (1920, 0.75),
        ]
        estimates = backfill_series(support, dynamics, years=years, coverage=0.80)
        res = settle_backfill(estimates, mccarthy, store, group="muslim")
        n_settled += res["n_settled"]
        n_hits += res["n_hits"]
        n_excluded += res["n_excluded_contested"]
        protocol_notes.append(
            f"mccarthy: {res['n_excluded_contested']} excluded (contested_validation)"
        )

    # Ottoman 1914 provinces: extrapolate from Karpat empire anchors (nearest era).
    if provinces and karpat:
        support = [(a.year, float(a.shares["muslim"])) for a in karpat]
        years = sorted({a.year for a in provinces})
        estimates = backfill_series(support, dynamics, years=years, coverage=0.80)
        res = settle_backfill(estimates, provinces, store, group="muslim")
        n_settled += res["n_settled"]
        n_hits += res["n_hits"]
        n_excluded += res["n_excluded_contested"]
        protocol_notes.append(
            f"ottoman_1914_provinces: {res['n_settled']} settled vs Karpat-era prior"
        )
    elif provinces:
        protocol_notes.append("ottoman_1914_provinces: skipped (no Karpat support anchors)")

    protocol_notes.append(
        f"basihos: {n_basihos} population rows, 0 religion shares — not settleable"
    )

    ledger = [c for c in store.ledger if c.settled]
    cal = (
        [r.to_dict() for r in calibration_table(ledger, bins=(0.0, 0.5, 0.8, 0.9, 1.0))]
        if ledger
        else []
    )
    cov = (n_hits / n_settled) if n_settled else None

    report = {
        "fit_start": dynamics.fit_start,
        "n_transitions": dynamics.n_transitions,
        "rate_mean": dynamics.rate_mean,
        "rate_std": dynamics.rate_std,
        "hypothesis": "dynamics:modern_fit",
        "n_settled": n_settled,
        "n_hits": n_hits,
        "n_excluded_contested": n_excluded,
        "coverage_observed": cov,
        "coverage_stated": 0.80,
        "calibration": cal,
        "posterior": store.get("dynamics:modern_fit").to_dict(),
        "holdout_inventory": {
            "karpat_share_rows": len(karpat),
            "mccarthy_rows": len(mccarthy),
            "ottoman_province_rows": len(provinces),
            "basihos_population_rows": n_basihos,
            "holdout_sources": list(HOLDOUT_SOURCES),
        },
        "protocol_notes": protocol_notes,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(
        f"fit_start={dynamics.fit_start}  transitions={dynamics.n_transitions}  "
        f"settled={n_settled}  hits={n_hits}  excluded={n_excluded}"
    )
    if cov is not None:
        print(f"coverage_observed={cov:.3f}  (stated=0.80)")
    print(f"wrote {args.out}")
    for note in protocol_notes:
        print(f"  · {note}")


if __name__ == "__main__":
    main()
