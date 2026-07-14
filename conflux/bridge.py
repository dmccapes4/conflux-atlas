"""Sparsity→simulation bridge: fit modern dynamics, backfill sparse eras.

v2 (bridge-nugget branch): the Phase 3 anchor-drop curves showed the
calibration-vs-sparsity curve is *inverted* — under-coverage at short gaps
(0.495 at 1–5y) where gap-proportional width collapses to zero and
cross-source definitional scatter is priced at nothing, honest coverage at
26–50y (0.922). Two additions, both opt-in (defaults preserve the Phase 3
contract behavior):

  - **nugget**: an additive measurement-noise floor (kriging sense),
    estimated per group from same-polity-year cross-source spreads
    (`estimate_nugget`). half = z·sqrt(nugget² + (σ·gap_term)²).
  - **shock widening**: σ is multiplied over spans that overlap documented
    event windows touching the polity (`shock_windows_for_polity`) —
    modern-fit volatility plausibly understates collapse-era movement.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

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
    width_shape: str = "linear",
    nugget: float = 0.0,
    shock_windows: Sequence[tuple[int, int]] = (),
    shock_sigma_multiplier: float = 2.0,
) -> list[BandEstimate]:
    """Estimate shares at ``years``; anchors dominate, bands widen with gap.

    ``width_shape``: "linear" (half ∝ gap, the Phase 3 default) or "sqrt"
    (half ∝ sqrt(gap decades) — random-walk scaling, E6c ablation).

    ``nugget``: per-observation measurement-noise sd (share points). Applied
    only off-anchor (gap > 0): reproducing an anchor's own statement stays
    exact by contract; *estimating between sources* pays the definitional
    floor. half = z·sqrt(nugget² + (σ_eff·gap_term)²).

    ``shock_windows``: (start, end) year spans (already filtered to this
    series' polity by the caller); when the span between the target year and
    its nearest anchor overlaps one, σ is multiplied by
    ``shock_sigma_multiplier`` — modern-fit rate volatility is a calm-era
    prior and must not price a collapse era.
    """
    if width_shape not in ("linear", "sqrt"):
        raise ValueError(f"unknown width_shape: {width_shape}")
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
            span = (min(year, nearest_y), max(year, nearest_y))
            sigma_eff = sigma
            if any(s0 <= span[1] and span[0] <= s1 for s0, s1 in shock_windows):
                sigma_eff = sigma * float(shock_sigma_multiplier)
            decades = gap / 10.0
            gap_term = math.sqrt(decades) if width_shape == "sqrt" else decades
            half = z * math.sqrt(float(nugget) ** 2 + (sigma_eff * gap_term) ** 2)

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


# ---------------------------------------------------------------------------
# v2 — nugget estimation + shock windows
# ---------------------------------------------------------------------------


def estimate_nugget(
    observations: Sequence[Any],  # observations.ShareObservation
    *,
    groups: Iterable[str] = ("muslim", "christian", "jewish"),
    year_tolerance: int = 3,
    min_pairs: int = 10,
) -> dict[str, Any]:
    """Per-group measurement-noise sd from cross-source same-polity spreads.

    Two independent sources stating the same polity-year(±tol) share differ
    by d with Var(d) = 2·σ_m² under iid noise → σ_m = std(d)/√2. Pairs are
    nearest-year within ``year_tolerance`` (definitional scatter dominates
    true drift at that horizon). Groups without ``min_pairs`` fall back to
    the pooled estimate. Returns {"per_group", "pooled", "n_pairs"}.
    """
    diffs_by_group: dict[str, list[float]] = defaultdict(list)
    by_key: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for o in observations:
        if o.group in set(groups):
            by_key[(o.polity_id, o.group)].append(o)

    for (_pid, group), rows in by_key.items():
        rows = sorted(rows, key=lambda o: o.year)
        for i, a in enumerate(rows):
            for b in rows[i + 1 :]:
                if b.year - a.year > year_tolerance:
                    break
                if a.source_id == b.source_id:
                    continue
                diffs_by_group[group].append(a.share - b.share)

    def _sd(xs: list[float]) -> float:
        if len(xs) < 2:
            return 0.0
        m = sum(xs) / len(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

    all_diffs = [d for ds in diffs_by_group.values() for d in ds]
    pooled = _sd(all_diffs) / math.sqrt(2.0) if len(all_diffs) >= 2 else 0.0
    per_group: dict[str, float] = {}
    for g in groups:
        ds = diffs_by_group.get(g, [])
        per_group[g] = _sd(ds) / math.sqrt(2.0) if len(ds) >= min_pairs else pooled
    return {
        "per_group": per_group,
        "pooled": pooled,
        "n_pairs": {g: len(diffs_by_group.get(g, [])) for g in groups},
    }


def shock_windows_for_polity(
    polity_id: str,
    events: Sequence[Any],  # schema.Event
    migration_edges: Sequence[Any] = (),  # schema.MigrationEdge
) -> list[tuple[int, int]]:
    """Event (start, end) spans touching this polity — same contact rule as
    the E5 shock tagging: ``affected_polities`` or a triggered migration edge."""
    windows: list[tuple[int, int]] = []
    for e in events:
        touches = polity_id in e.affected_polities or any(
            me.trigger_event_id == e.event_id
            and polity_id in (me.from_polity, me.to_polity)
            for me in migration_edges
        )
        if touches:
            windows.append((e.year, e.year_end if e.year_end is not None else e.year))
    return sorted(windows)


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
