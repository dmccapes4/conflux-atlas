"""Banded share forecasts for Phase 3 (Paper B baselines).

Predicts a share *value with a central interval*, not only a direction.
Temporal hygiene: only train points with ``year <= cut_year`` may influence
point, band, or abstention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

FORECAST_POLICIES = ("persistence", "reversion", "ar1")

# Approx. normal z for central 80% coverage.
_Z80 = 1.2815515655446004


@dataclass(frozen=True)
class BandForecast:
    polity_id: str
    group: str
    cut_year: int
    target_year: int
    point: float
    lo: float
    hi: float
    coverage: float
    policy: str
    train_n: int
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.lo <= self.point <= self.hi <= 1.0):
            raise ValueError(
                f"band invariant violated: lo={self.lo} point={self.point} hi={self.hi}"
            )
        if not (self.target_year > self.cut_year):
            raise ValueError(
                f"target_year ({self.target_year}) must be > cut_year ({self.cut_year})"
            )
        if not (0.0 < self.coverage < 1.0):
            raise ValueError(f"coverage must be in (0,1): {self.coverage}")


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _train(points: Sequence[tuple[int, float]], cut_year: int) -> list[tuple[int, float]]:
    by_year: dict[int, float] = {}
    for y, s in points:
        yi = int(y)
        if yi <= int(cut_year):
            by_year[yi] = float(s)
    return sorted(by_year.items())


def _std(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def _min_train(policy: str) -> int:
    if policy == "persistence":
        return 1
    if policy == "reversion":
        return 2
    if policy == "ar1":
        return 3
    raise ValueError(f"unknown policy: {policy}")


def _point(train: list[tuple[int, float]], policy: str, target_year: int) -> float:
    shares = [s for _, s in train]
    last_y, last_s = train[-1]
    mean_s = sum(shares) / len(shares)

    if policy == "persistence":
        return last_s
    if policy == "reversion":
        return 0.5 * last_s + 0.5 * mean_s
    if policy == "ar1":
        deltas: list[float] = []
        for i in range(1, len(train)):
            dy = train[i][0] - train[i - 1][0]
            if dy <= 0:
                continue
            deltas.append((train[i][1] - train[i - 1][1]) / dy)
        drift = sum(deltas) / len(deltas) if deltas else 0.0
        return last_s + drift * (target_year - last_y)
    raise ValueError(f"unknown policy: {policy}")


def forecast_series(
    points: Sequence[tuple[int, float]],
    *,
    cut_year: int,
    target_years: Sequence[int],
    policy: str,
    coverage: float = 0.80,
    polity_id: str = "",
    group: str = "",
) -> list[BandForecast]:
    """Forecast banded shares for ``target_years`` using only train ≤ cut."""
    if policy not in FORECAST_POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    train = _train(points, cut_year)
    if len(train) < _min_train(policy):
        return []

    shares = [s for _, s in train]
    share_std = _std(shares)
    last_y = train[-1][0]
    z = _Z80

    out: list[BandForecast] = []
    for ty in sorted(int(t) for t in target_years):
        if ty <= cut_year:
            continue
        point = _clip01(_point(train, policy, ty))
        horizon = max(float(ty - last_y), 0.0)
        # Width grows with horizon (sqrt decades). Zero when train is flat.
        half = z * share_std * math.sqrt(max(horizon, 1.0) / 10.0)
        # Place a fixed-width window, then shift into [0,1] so clipping
        # cannot shrink width as the point drifts toward a boundary
        # (needed for monotone widening under ar1 trends).
        width = min(2.0 * half, 1.0)
        lo = point - width / 2.0
        hi = point + width / 2.0
        if lo < 0.0:
            lo = 0.0
            hi = width
        elif hi > 1.0:
            hi = 1.0
            lo = 1.0 - width
        lo = min(lo, point)
        hi = max(hi, point)
        out.append(
            BandForecast(
                polity_id=polity_id,
                group=group,
                cut_year=int(cut_year),
                target_year=ty,
                point=point,
                lo=lo,
                hi=hi,
                coverage=float(coverage),
                policy=policy,
                train_n=len(train),
                meta={"last_train_year": last_y},
            )
        )
    return out
