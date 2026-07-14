#!/usr/bin/env python3
"""Run Phase 1 leave-one-polity-out scorecard on the demo cohort → JSON + stdout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.model import DEMO_POLITIES, ConfluxModel  # noqa: E402
from conflux.movement import build_catalog  # noqa: E402
from conflux.scorecard import run_scorecard, write_report  # noqa: E402

DEFAULT_OUT = ROOT / "data-validation-reports" / "PHASE1_SCORECARD.json"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--min-bucket-n", type=int, default=2)
    p.add_argument("--groups", nargs="+", default=["muslim", "christian", "jewish"])
    args = p.parse_args()

    model = ConfluxModel()
    anchors = [a for pid in DEMO_POLITIES for a in model.anchors_by_polity.get(pid, [])]
    catalog = build_catalog(anchors, groups=args.groups)
    result = run_scorecard(catalog, min_bucket_n=args.min_bucket_n)
    write_report(result, args.out)

    print(f"n_transitions={result.n_transitions}  protocol={result.protocol}")
    print(f"wrote {args.out}")
    for name, pol in sorted(result.policies.items()):
        print(
            f"  {name:12} accuracy={pol.accuracy:.3f}  "
            f"n_scored={pol.n_scored}  coverage={pol.coverage:.3f}"
        )


if __name__ == "__main__":
    main()
