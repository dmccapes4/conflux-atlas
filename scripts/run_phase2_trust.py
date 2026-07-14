#!/usr/bin/env python3
"""Run Phase 2 1975-cut + source corroboration → PHASE2_TRUST.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.learning import TrustStore  # noqa: E402
from conflux.model import DEMO_POLITIES, ConfluxModel  # noqa: E402
from conflux.movement import build_catalog  # noqa: E402
from conflux.schema import Anchor  # noqa: E402
from conflux.settlement import (  # noqa: E402
    brier_score,
    make_corroboration_claims,
    make_policy_claims,
    settle_corroboration_claims,
    settle_policy_claims,
    write_trust_report,
)

DEFAULT_OUT = ROOT / "data-validation-reports" / "PHASE2_TRUST.json"
DEFAULT_ANCHORS = ROOT / "data" / "processed" / "anchors.jsonl"


def _load_all_anchors(path: Path) -> list[Anchor]:
    rows: list[Anchor] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(Anchor.model_validate(json.loads(line)))
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--cut-year", type=int, default=1975)
    p.add_argument("--min-bucket-n", type=int, default=2)
    p.add_argument("--tolerance-pp", type=float, default=0.05)
    p.add_argument("--max-gap-years", type=int, default=30)
    p.add_argument("--groups", nargs="+", default=["muslim", "christian", "jewish"])
    args = p.parse_args()

    model = ConfluxModel()
    demo_anchors = [
        a for pid in DEMO_POLITIES for a in model.anchors_by_polity.get(pid, [])
    ]
    catalog = build_catalog(demo_anchors, groups=args.groups)

    store = TrustStore()
    pol_claims = make_policy_claims(
        catalog, cut_year=args.cut_year, min_bucket_n=args.min_bucket_n
    )
    n_pol = settle_policy_claims(pol_claims, catalog, store)

    all_anchors = _load_all_anchors(DEFAULT_ANCHORS)
    corr_claims: list = []
    for g in args.groups:
        corr_claims.extend(
            make_corroboration_claims(
                all_anchors,
                group=g,
                tolerance_pp=args.tolerance_pp,
                max_gap_years=args.max_gap_years,
            )
        )
    n_corr = settle_corroboration_claims(corr_claims, store)

    all_claims = list(pol_claims) + list(corr_claims)
    write_trust_report(store, all_claims, args.out)

    print(f"cut_year={args.cut_year}  policy_settled={n_pol}  corr_settled={n_corr}")
    print(f"brier={brier_score(all_claims):.4f}")
    print(f"wrote {args.out}")
    for row in store.summary():
        print(
            f"  {row['hypothesis_id']:40} mean={row['mean']:.3f} "
            f"trials={row['trials']}  α={row['alpha']:.0f} β={row['beta']:.0f}"
        )


if __name__ == "__main__":
    main()
