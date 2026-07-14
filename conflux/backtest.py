"""Pre-registered 1975 banded-forecast backtest (Phase 3 / Paper B protocol)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from types import MappingProxyType
from typing import Any, Iterable, Sequence

from .connascence import split_calm_shock, tag_shock_claims
from .forecast import FORECAST_POLICIES, forecast_series
from .learning import Claim, TrustStore
from .schema import Anchor, Event

PREREGISTRATION = MappingProxyType(
    {
        "cut_year": 1975,
        "coverage": 0.80,
        "alpha": 0.20,
        "policies": ("persistence", "reversion", "ar1"),
        "primary_metric": "mean_interval_score",
        "success_rule": "candidate_beats_all_baselines_on_primary_metric",
        "contested_validation_excluded": ("mccarthy_armenian_pop_ottoman",),
    }
)


def interval_score(y: float, lo: float, hi: float, *, alpha: float = 0.20) -> float:
    """Winkler interval score for a central (1-α) interval. Lower is better."""
    y, lo, hi = float(y), float(lo), float(hi)
    a = float(alpha)
    s = hi - lo
    if y < lo:
        s += (2.0 / a) * (lo - y)
    elif y > hi:
        s += (2.0 / a) * (y - hi)
    return s


def _primary_source(anchor: Anchor) -> str:
    if not anchor.source_ids:
        return "unknown"
    return str(anchor.source_ids[0])


def _dedupe_year(rows: list[Anchor]) -> list[Anchor]:
    best: dict[int, Anchor] = {}
    for a in rows:
        prev = best.get(a.year)
        if prev is None or a.confidence > prev.confidence:
            best[a.year] = a
    return [best[y] for y in sorted(best)]


def _claim_id(
    hypothesis_id: str,
    polity_id: str,
    group: str,
    year_from: int,
    year_to: int,
    cut_year: int,
) -> str:
    raw = f"{hypothesis_id}|{polity_id}|{group}|{year_from}|{year_to}|{cut_year}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def make_forecast_claims(
    anchors: Sequence[Anchor],
    *,
    groups: Iterable[str],
    policies: Sequence[str] | None = None,
    prereg: Any = PREREGISTRATION,
    events: Sequence[Event] | None = None,
) -> list[Claim]:
    """Emit one claim per (series, post-cut realized year, policy)."""
    cut = int(prereg["cut_year"])
    coverage = float(prereg["coverage"])
    contested = set(prereg["contested_validation_excluded"])
    pols = tuple(policies) if policies is not None else tuple(prereg["policies"])

    by_polity: dict[str, list[Anchor]] = defaultdict(list)
    for a in anchors:
        by_polity[a.polity_id].append(a)

    claims: list[Claim] = []
    for pid, rows in sorted(by_polity.items()):
        series = _dedupe_year(rows)
        for group in groups:
            points = [(a.year, float(a.shares.get(group, 0.0))) for a in series]
            # Realized post-cut targets only; drop contested primary sources.
            targets: list[tuple[int, float]] = []
            for a in series:
                if a.year <= cut:
                    continue
                if _primary_source(a) in contested:
                    continue
                targets.append((a.year, float(a.shares.get(group, 0.0))))
            if not targets:
                continue
            target_years = [y for y, _ in targets]
            realized = {y: s for y, s in targets}

            for policy in pols:
                if policy not in FORECAST_POLICIES:
                    continue
                bands = forecast_series(
                    points,
                    cut_year=cut,
                    target_years=target_years,
                    policy=policy,
                    coverage=coverage,
                    polity_id=pid,
                    group=group,
                )
                for b in bands:
                    hyp = f"forecast:{policy}"
                    claims.append(
                        Claim(
                            claim_id=_claim_id(
                                hyp, pid, group, cut, b.target_year, cut
                            ),
                            hypothesis_id=hyp,
                            polity_id=pid,
                            group=group,
                            cut_year=cut,
                            predicted="in_band",
                            stated_p=coverage,
                            train_n=b.train_n,
                            year_from=cut,
                            year_to=b.target_year,
                            meta={
                                "point": b.point,
                                "lo": b.lo,
                                "hi": b.hi,
                                "coverage": b.coverage,
                                "policy": policy,
                                "realized_share": realized[b.target_year],
                            },
                        )
                    )

    if events:
        tag_shock_claims(claims, events)
    else:
        for c in claims:
            c.meta.setdefault("shock", False)
            c.meta.setdefault("shock_events", [])
    return claims


def settle_forecast_claims(
    claims: Sequence[Claim],
    anchors: Sequence[Anchor],
    store: TrustStore,
) -> int:
    """success = realized share inside [lo, hi]. Anchors unused if meta filled."""
    del anchors  # settlement uses meta["realized_share"] (filled at claim time)
    n = 0
    for c in claims:
        realized = float(c.meta["realized_share"])
        lo = float(c.meta["lo"])
        hi = float(c.meta["hi"])
        success = lo <= realized <= hi
        store.record(c)
        store.settle(c, success=success)
        n += 1
    return n


def backtest_report(
    claims: Sequence[Claim], *, prereg: Any = PREREGISTRATION
) -> dict[str, Any]:
    """JSON-serializable report. Never hides a miss."""
    alpha = float(prereg["alpha"])
    policies = tuple(prereg["policies"])
    settled = [c for c in claims if c.settled]

    def _policy_block(rows: list[Claim]) -> dict[str, Any]:
        n = len(rows)
        if n == 0:
            return {
                "n": 0,
                "coverage_observed": 0.0,
                "mean_interval_score": 0.0,
                "mean_width": 0.0,
            }
        hits = sum(1 for c in rows if c.success)
        scores = [
            interval_score(
                float(c.meta["realized_share"]),
                float(c.meta["lo"]),
                float(c.meta["hi"]),
                alpha=alpha,
            )
            for c in rows
        ]
        widths = [float(c.meta["hi"]) - float(c.meta["lo"]) for c in rows]
        return {
            "n": n,
            "coverage_observed": hits / n,
            "mean_interval_score": sum(scores) / n,
            "mean_width": sum(widths) / n,
        }

    # Ensure shock tags exist for split.
    for c in settled:
        c.meta.setdefault("shock", False)
    split = split_calm_shock(settled)

    policy_rows: dict[str, Any] = {}
    for policy in policies:
        rows = [c for c in settled if c.meta.get("policy") == policy]
        block = _policy_block(rows)
        calm = _policy_block([c for c in split["calm"] if c.meta.get("policy") == policy])
        shock = _policy_block([c for c in split["shock"] if c.meta.get("policy") == policy])
        block["calm"] = calm
        block["shock"] = shock
        policy_rows[policy] = block

    # Baselines-only verdict: name the best on primary metric; no candidate.
    scored = [
        (p, policy_rows[p]["mean_interval_score"], policy_rows[p]["n"])
        for p in policies
        if policy_rows[p]["n"] > 0
    ]
    best = min(scored, key=lambda t: t[1])[0] if scored else None
    verdict = {
        "candidate": None,
        "best_baseline": best,
        "primary_metric": prereg["primary_metric"],
        "success_rule": prereg["success_rule"],
        "candidate_beats_all_baselines": None,
    }

    return {
        "preregistration": dict(prereg),
        "policies": policy_rows,
        "verdict": verdict,
        "n_claims": len(claims),
        "n_settled": len(settled),
    }
