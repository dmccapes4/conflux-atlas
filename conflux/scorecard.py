"""Phase 1 hash-catalog scorecard vs baselines (leave-one-polity-out)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .movement import CatalogRow, hash_outcome_table


@dataclass(frozen=True)
class Prediction:
    polity_id: str
    policy: str
    predicted: str | None
    actual: str
    group: str = ""
    year_from: int = 0
    year_to: int = 0


@dataclass(frozen=True)
class PolicyScore:
    accuracy: float
    n_scored: int
    coverage: float


@dataclass
class ScorecardResult:
    n_transitions: int
    policies: dict[str, PolicyScore]
    predictions: list[Prediction] = field(default_factory=list)
    protocol: str = "leave_one_polity_out"


def _opposite(direction: str) -> str:
    if direction == "up":
        return "down"
    if direction == "down":
        return "up"
    return "flat"


def _mode(outcomes: Sequence[str]) -> str | None:
    if not outcomes:
        return None
    counts = Counter(outcomes)
    # stable tie-break: highest count, then name
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def run_scorecard(
    catalog: Sequence[CatalogRow], *, min_bucket_n: int = 2
) -> ScorecardResult:
    """Leave-one-polity-out evaluation of hash_mode vs baselines.

    Fair tape: accuracy / n_scored use only transitions where *all* policies
    produced a non-null prediction. Coverage for each policy is
    (that policy's non-abstentions) / n_transitions — so hash_mode can report
    coverage 0 under a strict ``min_bucket_n`` while still exposing abstentions.
    """
    rows = list(catalog)
    n_transitions = len(rows)
    policies = ("hash_mode", "reversion", "persistence", "majority")

    # Index previous outcome per (polity, group) in chronological order.
    by_pg: dict[tuple[str, str], list[CatalogRow]] = defaultdict(list)
    for r in sorted(rows, key=lambda x: (x.polity_id, x.group, x.year_from)):
        by_pg[(r.polity_id, r.group)].append(r)
    prev_outcome: dict[tuple[str, str, int, int], str | None] = {}
    for key, series in by_pg.items():
        prev: str | None = None
        for r in series:
            prev_outcome[(r.polity_id, r.group, r.year_from, r.year_to)] = prev
            prev = r.outcome

    polities = sorted({r.polity_id for r in rows})
    # Collect raw predictions keyed by transition id.
    # transition key → {policy: predicted}
    raw: dict[tuple, dict[str, str | None]] = {}
    actuals: dict[tuple, str] = {}
    meta: dict[tuple, CatalogRow] = {}

    for holdout in polities:
        train = [r for r in rows if r.polity_id != holdout]
        test = [r for r in rows if r.polity_id == holdout]
        table = hash_outcome_table(train, min_n=min_bucket_n)
        maj = _mode([r.outcome for r in train])

        for r in test:
            key = (r.polity_id, r.group, r.year_from, r.year_to)
            meta[key] = r
            actuals[key] = r.outcome
            preds: dict[str, str | None] = {}

            entry = table.get(r.origin_hash)
            preds["hash_mode"] = entry.mode if entry is not None else None

            prev = prev_outcome.get(key)
            if prev is None:
                preds["reversion"] = None
                preds["persistence"] = None
            else:
                preds["reversion"] = _opposite(prev)
                preds["persistence"] = prev

            preds["majority"] = maj
            raw[key] = preds

    # Per-policy coverage over all transitions (honest abstention surfacing).
    coverage_num = {p: 0 for p in policies}
    for key, preds in raw.items():
        for p in policies:
            if preds[p] is not None:
                coverage_num[p] += 1

    # Fair tape: all policies non-null.
    fair_keys = [
        key
        for key, preds in raw.items()
        if all(preds[p] is not None for p in policies)
    ]

    scores: dict[str, PolicyScore] = {}
    predictions: list[Prediction] = []

    for p in policies:
        correct = 0
        for key in fair_keys:
            pred = raw[key][p]
            act = actuals[key]
            if pred == act:
                correct += 1
        n_scored = len(fair_keys)
        acc = (correct / n_scored) if n_scored else 0.0
        cov = (coverage_num[p] / n_transitions) if n_transitions else 0.0
        scores[p] = PolicyScore(accuracy=acc, n_scored=n_scored, coverage=cov)

    # Flatten predictions (all transitions × policies) for leakage audits.
    for key, preds in sorted(raw.items()):
        r = meta[key]
        for p in policies:
            predictions.append(
                Prediction(
                    polity_id=r.polity_id,
                    policy=p,
                    predicted=preds[p],
                    actual=actuals[key],
                    group=r.group,
                    year_from=r.year_from,
                    year_to=r.year_to,
                )
            )

    return ScorecardResult(
        n_transitions=n_transitions,
        policies=scores,
        predictions=predictions,
    )


def write_report(result: ScorecardResult, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "n_transitions": result.n_transitions,
        "protocol": result.protocol,
        "policies": {
            name: {
                "accuracy": pol.accuracy,
                "n_scored": pol.n_scored,
                "coverage": pol.coverage,
            }
            for name, pol in result.policies.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
