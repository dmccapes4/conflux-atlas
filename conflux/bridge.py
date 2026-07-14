"""Sparsity→simulation bridge: fit modern dynamics, backfill sparse eras."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .backtest import PREREGISTRATION
from .forecast import _clip01, _std

_Z80 = 1.2815515655446004
from .learning import Claim, TrustStore
from .movement import level_bin, movement_events
from .schema import Anchor


@dataclass(frozen=True)
class Dynamics:
    fit_start: int
    n_transitions: int
    rate_mean: float
    rate_std: float
    by_level: dict[str, tuple[float, float]] = field(default_factory=dict)
    # level → (mean rate/decade, std)


@dataclass(frozen=True)
class BandEstimate:
    year: int
    point: float
    lo: float
    hi: float
    coverage: float
    nearest_anchor_gap: int


def _primary_source(anchor: Anchor) -> str:
    if not anchor.source_ids:
        return "unknown"
    return str(anchor.source_ids[0])


def fit_dynamics(
    anchors: Sequence[Anchor],
    *,
    groups: Iterable[str],
    fit_start: int = 1920,
) -> Dynamics:
    """Fit rate/decade stats on transitions with year_from >= fit_start only."""
    rates: list[float] = []
    by_level: dict[str, list[float]] = defaultdict(list)
    for g in groups:
        for ev in movement_events(list(anchors), group=g):
            if ev.year_from < fit_start:
                continue
            rates.append(ev.rate_per_decade)
            by_level[level_bin(ev.share_from)].append(ev.rate_per_decade)
    if len(rates) < 10:
        raise ValueError(
            f"unusable dynamics fit: only {len(rates)} transitions with "
            f"year_from >= {fit_start} (need ≥ 10)"
        )
    level_stats = {
        k: (sum(v) / len(v), _std(v) if len(v) >= 2 else 0.0)
        for k, v in by_level.items()
        if v
    }
    return Dynamics(
        fit_start=int(fit_start),
        n_transitions=len(rates),
        rate_mean=sum(rates) / len(rates),
        rate_std=_std(rates),
        by_level=level_stats,
    )


def _lerp(y0: float, s0: float, y1: float, s1: float, year: int) -> float:
    if y1 == y0:
        return s0
    t = (year - y0) / (y1 - y0)
    return s0 + t * (s1 - s0)


def backfill_series(
    anchor_points: Sequence[tuple[int, float]],
    dynamics: Dynamics,
    *,
    years: Sequence[int],
    coverage: float = 0.80,
) -> list[BandEstimate]:
    """Estimate shares at ``years``; anchors dominate, bands widen with gap."""
    anchors = sorted((int(y), float(s)) for y, s in anchor_points)
    if not anchors:
        raise ValueError("anchor_points must be non-empty")
    z = _Z80
    sigma = max(dynamics.rate_std, 1e-4)

    out: list[BandEstimate] = []
    for year in years:
        year = int(year)
        nearest_y, nearest_s = min(anchors, key=lambda a: (abs(a[0] - year), a[0]))
        gap = abs(nearest_y - year)

        if gap == 0:
            point = nearest_s
            half = 0.0
        else:
            # Prefer linear interpolation between bracketing anchors.
            left = [a for a in anchors if a[0] <= year]
            right = [a for a in anchors if a[0] >= year]
            if left and right and left[-1][0] != right[0][0]:
                point = _lerp(left[-1][0], left[-1][1], right[0][0], right[0][1], year)
            else:
                # Extrapolate with modern mean rate/decade.
                decades = (year - nearest_y) / 10.0
                point = nearest_s + dynamics.rate_mean * decades
            # Width grows with gap (monotone in nearest_anchor_gap).
            # rate_std is already /decade; scale by decades of distance.
            half = z * sigma * (gap / 10.0)

        point = _clip01(point)
        lo = _clip01(point - half)
        hi = _clip01(point + half)
        lo = min(lo, point)
        hi = max(hi, point)
        out.append(
            BandEstimate(
                year=year,
                point=point,
                lo=lo,
                hi=hi,
                coverage=float(coverage),
                nearest_anchor_gap=int(gap),
            )
        )
    return out


def settle_backfill(
    estimates: Sequence[BandEstimate],
    holdout_anchors: Sequence[Anchor],
    store: TrustStore,
    *,
    hypothesis: str = "dynamics:modern_fit",
    group: str = "muslim",
) -> dict[str, int]:
    """Settle holdout anchors against backfill bands; skip contested sources."""
    contested = set(PREREGISTRATION["contested_validation_excluded"])
    by_year = {e.year: e for e in estimates}
    n_settled = 0
    n_hits = 0
    n_excluded = 0

    for a in holdout_anchors:
        if _primary_source(a) in contested:
            n_excluded += 1
            continue
        est = by_year.get(a.year)
        if est is None:
            continue
        share = float(a.shares.get(group, 0.0))
        success = est.lo <= share <= est.hi
        cid = hashlib.sha1(
            f"{hypothesis}|{a.polity_id}|{group}|{a.year}".encode()
        ).hexdigest()[:16]
        claim = Claim(
            claim_id=cid,
            hypothesis_id=hypothesis,
            polity_id=a.polity_id,
            group=group,
            cut_year=est.year,
            predicted="in_band",
            stated_p=est.coverage,
            train_n=1,
            year_from=est.year,
            year_to=est.year,
            meta={
                "point": est.point,
                "lo": est.lo,
                "hi": est.hi,
                "realized_share": share,
                "nearest_anchor_gap": est.nearest_anchor_gap,
            },
        )
        store.record(claim)
        store.settle(claim, success=success)
        n_settled += 1
        if success:
            n_hits += 1

    return {
        "n_settled": n_settled,
        "n_hits": n_hits,
        "n_excluded_contested": n_excluded,
    }
