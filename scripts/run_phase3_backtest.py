#!/usr/bin/env python3
"""Run pre-registered 1975 banded-forecast backtest → PHASE3_BACKTEST.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.backtest import (  # noqa: E402
    PREREGISTRATION,
    backtest_report,
    make_forecast_claims,
    settle_forecast_claims,
)
from conflux.learning import TrustStore  # noqa: E402
from conflux.schema import Anchor, Event  # noqa: E402
from conflux.settlement import brier_score, calibration_table  # noqa: E402

DEFAULT_OUT = ROOT / "data-validation-reports" / "PHASE3_BACKTEST.json"
DEFAULT_ANCHORS = ROOT / "data" / "processed" / "anchors.jsonl"
DEFAULT_EVENTS = ROOT / "data" / "processed" / "events.jsonl"


def _load_jsonl(path: Path, model):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(model.model_validate(json.loads(line)))
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    p.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    p.add_argument(
        "--groups",
        nargs="+",
        default=["muslim", "christian", "jewish"],
    )
    args = p.parse_args()

    anchors = _load_jsonl(args.anchors, Anchor)
    events = _load_jsonl(args.events, Event) if args.events.exists() else []

    claims = make_forecast_claims(
        anchors, groups=args.groups, prereg=PREREGISTRATION, events=events
    )
    store = TrustStore()
    n = settle_forecast_claims(claims, anchors, store)
    report = backtest_report(claims, prereg=PREREGISTRATION)
    report["calibration"] = [
        r.to_dict()
        for r in calibration_table(
            [c for c in claims if c.settled], bins=(0.0, 0.5, 0.8, 0.9, 1.0)
        )
    ]
    report["brier"] = brier_score([c for c in claims if c.settled])
    report["posteriors"] = store.summary()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(
        f"cut={PREREGISTRATION['cut_year']}  claims={len(claims)}  "
        f"settled={n}  brier={report['brier']:.4f}"
    )
    print(f"wrote {args.out}")
    for policy, row in report["policies"].items():
        print(
            f"  {policy:12} n={row['n']:4}  cov={row['coverage_observed']:.3f}  "
            f"IS={row['mean_interval_score']:.4f}  width={row['mean_width']:.4f}"
        )
    v = report["verdict"]
    print(
        f"verdict: best_baseline={v['best_baseline']}  "
        f"candidate={v['candidate']}  "
        f"(primary={v['primary_metric']})"
    )


if __name__ == "__main__":
    main()
