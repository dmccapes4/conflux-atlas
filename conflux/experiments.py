"""Phase 3 expanded experimentation (PHASE3_EXPERIMENT_PLAN.md).

E1 cut sweep · E2 desk-augmented series · E3 width-model ablation ·
E4 candidate policies · E5 polity-aware shock split (via connascence) ·
E6 bridge curves · E7 statistical hygiene.

Everything here is *exploratory* machinery except the two labeled
confirmatory runs; `PREREGISTRATION` in `backtest.py` is never modified,
only copied with a different cut for exploratory tapes.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .backtest import PREREGISTRATION, interval_score
from .bridge import Dynamics, backfill_series
from .connascence import split_calm_shock, tag_shock_claims_contact
from .forecast import _Z80, _clip01, _point, _std
from .learning import Claim, TrustStore
from .movement import delta_bin, gap_bin, level_bin, vol_bin
from .observations import load_observation_desk

BASELINE_POLICIES = ("persistence", "reversion", "ar1")
WIDTH_MODELS = ("w0", "w1", "w2", "w3")

# Targets that must never validate a band: contested sources (pre-registered)
# plus in-house seeds (settling against our own guesses proves nothing).
TARGET_EXCLUDE_DEFAULT = frozenset(PREREGISTRATION["contested_validation_excluded"]) | {
    "hand_seed_v0",
}


# ---------------------------------------------------------------------------
# E7 — statistical hygiene
# ---------------------------------------------------------------------------


def wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% score interval for a binomial proportion."""
    if n <= 0:
        return (0.0, 1.0)
    p = hits / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def permutation_control(
    settled: Sequence[Claim],
    *,
    n_perm: int = 200,
    alpha: float = 0.20,
    seed: int = 0,
) -> dict[str, Any]:
    """Permute realized shares within (group, level-bin) strata.

    If a policy's mean interval score under permutation is not much worse
    than its actual score, its bands are wide enough to 'cover' anything —
    the score carries no information about the series it claims to predict.
    """
    rows = [
        (
            c.group,
            level_bin(float(c.meta["realized_share"])),
            float(c.meta["realized_share"]),
            float(c.meta["lo"]),
            float(c.meta["hi"]),
        )
        for c in settled
    ]
    if not rows:
        return {"n": 0}
    actual = sum(interval_score(y, lo, hi, alpha=alpha) for _, _, y, lo, hi in rows) / len(rows)

    strata: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, (g, lb, *_rest) in enumerate(rows):
        strata[(g, lb)].append(i)

    rng = random.Random(seed)
    perm_scores: list[float] = []
    realized = [r[2] for r in rows]
    for _ in range(n_perm):
        shuffled = list(realized)
        for idxs in strata.values():
            vals = [shuffled[i] for i in idxs]
            rng.shuffle(vals)
            for i, v in zip(idxs, vals):
                shuffled[i] = v
        s = sum(
            interval_score(shuffled[i], rows[i][3], rows[i][4], alpha=alpha)
            for i in range(len(rows))
        ) / len(rows)
        perm_scores.append(s)
    perm_scores.sort()
    return {
        "n": len(rows),
        "n_perm": n_perm,
        "actual_mean_is": actual,
        "perm_mean_is": sum(perm_scores) / n_perm,
        "perm_is_q05": perm_scores[int(0.05 * n_perm)],
        "perm_is_q95": perm_scores[int(0.95 * n_perm)],
        # >1 means the actual tape scores better than shuffled outcomes.
        "perm_over_actual_ratio": (sum(perm_scores) / n_perm) / actual if actual > 0 else None,
    }


# ---------------------------------------------------------------------------
# E2 — series construction (anchors-only and desk-augmented)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeriesPoint:
    year: int
    share: float
    confidence: float
    source: str


Series = dict[tuple[str, str], list[SeriesPoint]]  # (polity_id, group) → points


def _add_point(
    acc: dict[tuple[str, str], dict[int, SeriesPoint]],
    pid: str,
    group: str,
    p: SeriesPoint,
) -> None:
    cur = acc[(pid, group)].get(p.year)
    if cur is None or p.confidence > cur.confidence:
        acc[(pid, group)][p.year] = p


def build_anchor_series(anchors: Sequence[Any], groups: Iterable[str]) -> Series:
    """Per-(polity, group) share series from Anchor rows (best conf per year)."""
    acc: dict[tuple[str, str], dict[int, SeriesPoint]] = defaultdict(dict)
    for a in anchors:
        src = str(a.source_ids[0]) if a.source_ids else "unknown"
        for g in groups:
            _add_point(
                acc,
                a.polity_id,
                g,
                SeriesPoint(int(a.year), float(a.shares.get(g, 0.0)), float(a.confidence), src),
            )
    return {k: [v[y] for y in sorted(v)] for k, v in acc.items()}


def build_desk_series(
    processed_dir: str | Path,
    anchors: Sequence[Any],
    groups: Iterable[str],
) -> Series:
    """Merged timeline: full observation desk + hand-seed anchors.

    The desk excludes hand seeds by design (Phase 2.5); for forecasting they
    re-enter as *train* material — `TARGET_EXCLUDE_DEFAULT` keeps them (and
    contested sources) out of validation targets. Definitional caveat: WJP
    core-Jewish and Pew affiliation shares live in one series here; claims
    carry `target_source` so lanes can be split post hoc.
    """
    acc: dict[tuple[str, str], dict[int, SeriesPoint]] = defaultdict(dict)
    groups = tuple(groups)
    for o in load_observation_desk(processed_dir, groups=groups):
        _add_point(
            acc,
            o.polity_id,
            o.group,
            SeriesPoint(o.year, o.share, o.confidence, o.source_id),
        )
    for a in anchors:
        src = str(a.source_ids[0]) if a.source_ids else "unknown"
        if src != "hand_seed_v0":
            continue  # non-seed anchors are already on the desk
        for g in groups:
            _add_point(
                acc,
                a.polity_id,
                g,
                SeriesPoint(int(a.year), float(a.shares.get(g, 0.0)), float(a.confidence), src),
            )
    return {k: [v[y] for y in sorted(v)] for k, v in acc.items()}


# ---------------------------------------------------------------------------
# E3 — width models
# ---------------------------------------------------------------------------


def _train_points(points: Sequence[SeriesPoint], cut_year: int) -> list[tuple[int, float]]:
    return [(p.year, p.share) for p in points if p.year <= cut_year]


def _min_train(policy: str) -> int:
    return {"persistence": 1, "reversion": 2, "ar1": 3}[policy]


def _place_band(point: float, width: float) -> tuple[float, float]:
    """Fixed-width window shifted into [0,1] (forecast.py semantics)."""
    width = min(float(width), 1.0)
    lo = point - width / 2.0
    hi = point + width / 2.0
    if lo < 0.0:
        lo, hi = 0.0, width
    elif hi > 1.0:
        lo, hi = 1.0 - width, 1.0
    return (min(lo, point), max(hi, point))


def fit_series_dynamics(series: Series, *, cut_year: int, fit_start: int = 1920) -> Dynamics:
    """Rate/decade stats from train-window transitions (for width model w2)."""
    rates: list[float] = []
    by_level: dict[str, list[float]] = defaultdict(list)
    for pts in series.values():
        train = _train_points(pts, cut_year)
        for (y0, s0), (y1, s1) in zip(train, train[1:]):
            if y0 < fit_start or y1 <= y0:
                continue
            r = (s1 - s0) / (y1 - y0) * 10.0
            rates.append(r)
            by_level[level_bin(s0)].append(r)
    if len(rates) < 10:
        # Fall back to the whole train window when the modern slice is thin
        # (e.g. cut 1950 leaves nothing with year_from >= 1920).
        for pts in series.values():
            train = _train_points(pts, cut_year)
            for (y0, s0), (y1, s1) in zip(train, train[1:]):
                if y1 <= y0 or y0 >= fit_start:
                    continue
                r = (s1 - s0) / (y1 - y0) * 10.0
                rates.append(r)
                by_level[level_bin(s0)].append(r)
        fit_start = 0
    if not rates:
        raise ValueError("no train transitions available for dynamics fit")
    return Dynamics(
        fit_start=fit_start,
        n_transitions=len(rates),
        rate_mean=sum(rates) / len(rates),
        rate_std=_std(rates) if len(rates) >= 2 else 0.01,
        by_level={
            k: (sum(v) / len(v), _std(v) if len(v) >= 2 else 0.0) for k, v in by_level.items()
        },
    )


def _walk_forward_rate_errors(
    train: list[tuple[int, float]], policy: str
) -> list[float]:
    """|prediction error| per sqrt-decade from internal one-step folds."""
    errs: list[float] = []
    lo = _min_train(policy)
    for i in range(lo, len(train)):
        sub = train[:i]
        ty, actual = train[i]
        pred = _clip01(_point(sub, policy, ty))
        gap_dec = max((ty - sub[-1][0]) / 10.0, 0.1)
        errs.append(abs(actual - pred) / math.sqrt(gap_dec))
    return errs


def _quantile(xs: Sequence[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = min(int(q * len(s)), len(s) - 1)
    return s[idx]


def fit_conformal_lambda(
    series: Series,
    *,
    cut_year: int,
    policy: str,
    coverage: float = 0.80,
    grid: Sequence[float] = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0),
) -> float:
    """Smallest w0 inflation reaching target coverage on pre-cut folds (w3)."""
    folds: list[tuple[float, float]] = []  # (|resid|, w0 half-width)
    for pts in series.values():
        train = _train_points(pts, cut_year)
        lo = max(_min_train(policy), 2)  # need >=2 for a std
        for i in range(lo, len(train)):
            sub = train[:i]
            ty, actual = train[i]
            pred = _clip01(_point(sub, policy, ty))
            std = _std([s for _, s in sub])
            horizon = max(float(ty - sub[-1][0]), 1.0)
            half = _Z80 * std * math.sqrt(horizon / 10.0)
            folds.append((abs(actual - pred), half))
    if not folds:
        return 1.0
    for lam in grid:
        hits = sum(1 for resid, half in folds if resid <= lam * half)
        if hits / len(folds) >= coverage:
            return float(lam)
    return float(grid[-1])


def compute_width(
    train: list[tuple[int, float]],
    *,
    target_year: int,
    policy: str,
    model: str,
    dynamics: Dynamics | None = None,
    conformal_lambda: float = 1.0,
) -> tuple[float, dict[str, Any]]:
    """Full band width for one target under a width model. Returns (width, meta)."""
    shares = [s for _, s in train]
    last_y, last_s = train[-1]
    horizon_dec = max(float(target_year - last_y), 1.0) / 10.0
    meta: dict[str, Any] = {"width_model": model}

    if model == "w0":
        half = _Z80 * _std(shares) * math.sqrt(horizon_dec)
    elif model == "w1":
        errs = _walk_forward_rate_errors(train, policy)
        if len(errs) < 2:
            half = _Z80 * _std(shares) * math.sqrt(horizon_dec)
            meta["width_fallback"] = "w0"
        else:
            half = _quantile(errs, 0.8) * math.sqrt(horizon_dec)
    elif model == "w2":
        if dynamics is None:
            raise ValueError("w2 requires dynamics")
        sigma = dynamics.by_level.get(level_bin(last_s), (0.0, dynamics.rate_std))[1]
        sigma = max(sigma, dynamics.rate_std * 0.25, 1e-4)
        half = _Z80 * sigma * math.sqrt(horizon_dec)
    elif model == "w3":
        half = conformal_lambda * _Z80 * _std(shares) * math.sqrt(horizon_dec)
        meta["conformal_lambda"] = conformal_lambda
    else:
        raise ValueError(f"unknown width model: {model}")
    return (2.0 * half, meta)


# ---------------------------------------------------------------------------
# Claims over generic series (E1/E2/E3 tapes)
# ---------------------------------------------------------------------------


def _cid(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def make_series_claims(
    series: Series,
    *,
    cut_year: int,
    policies: Sequence[str] = BASELINE_POLICIES,
    width_model: str = "w0",
    coverage: float = 0.80,
    target_exclude_sources: frozenset[str] = TARGET_EXCLUDE_DEFAULT,
    target_year_max: int | None = None,
    dynamics: Dynamics | None = None,
    conformal_lambdas: dict[str, float] | None = None,
    tape: str = "",
) -> list[Claim]:
    """Banded forecast claims over arbitrary series (desk or anchors).

    Mirrors `backtest.make_forecast_claims` semantics — temporal hygiene,
    realized targets only, abstention by train length — with source-aware
    target exclusion and pluggable width models.
    """
    if width_model == "w2" and dynamics is None:
        dynamics = fit_series_dynamics(series, cut_year=cut_year)
    claims: list[Claim] = []
    for (pid, group), pts in sorted(series.items()):
        train = _train_points(pts, cut_year)
        targets = [
            p
            for p in pts
            if p.year > cut_year
            and p.source not in target_exclude_sources
            and (target_year_max is None or p.year <= target_year_max)
        ]
        if not targets:
            continue
        for policy in policies:
            if len(train) < _min_train(policy):
                continue
            lam = (conformal_lambdas or {}).get(policy, 1.0)
            for t in targets:
                point = _clip01(_point(train, policy, t.year))
                width, wmeta = compute_width(
                    train,
                    target_year=t.year,
                    policy=policy,
                    model=width_model,
                    dynamics=dynamics,
                    conformal_lambda=lam,
                )
                lo, hi = _place_band(point, width)
                hyp = f"forecast:{policy}"
                claims.append(
                    Claim(
                        claim_id=_cid(tape, hyp, pid, group, cut_year, t.year, width_model),
                        hypothesis_id=hyp,
                        polity_id=pid,
                        group=group,
                        cut_year=cut_year,
                        predicted="in_band",
                        stated_p=coverage,
                        train_n=len(train),
                        year_from=cut_year,
                        year_to=t.year,
                        meta={
                            "point": point,
                            "lo": lo,
                            "hi": hi,
                            "coverage": coverage,
                            "policy": policy,
                            "realized_share": t.share,
                            "target_source": t.source,
                            "tape": tape,
                            **wmeta,
                        },
                    )
                )
    return claims


def climatology_claims(
    series: Series,
    *,
    cut_year: int,
    coverage: float = 0.80,
    target_exclude_sources: frozenset[str] = TARGET_EXCLUDE_DEFAULT,
    target_year_max: int | None = None,
    tape: str = "",
) -> list[Claim]:
    """No-skill floor: group-level train mean, width = 80% train dispersion.

    Every policy must beat this on interval score or it has no skill beyond
    'religion shares have a typical range'.
    """
    pool: dict[str, list[float]] = defaultdict(list)
    for (_pid, group), pts in series.items():
        pool[group].extend(p.share for p in pts if p.year <= cut_year)

    claims: list[Claim] = []
    for (pid, group), pts in sorted(series.items()):
        vals = pool.get(group) or []
        if len(vals) < 5:
            continue
        point = _clip01(sum(vals) / len(vals))
        lo_q, hi_q = _quantile(vals, 0.10), _quantile(vals, 0.90)
        lo, hi = min(lo_q, point), max(hi_q, point)
        for t in pts:
            if t.year <= cut_year or t.source in target_exclude_sources:
                continue
            if target_year_max is not None and t.year > target_year_max:
                continue
            claims.append(
                Claim(
                    claim_id=_cid(tape, "forecast:climatology", pid, group, cut_year, t.year),
                    hypothesis_id="forecast:climatology",
                    polity_id=pid,
                    group=group,
                    cut_year=cut_year,
                    predicted="in_band",
                    stated_p=coverage,
                    train_n=len(vals),
                    year_from=cut_year,
                    year_to=t.year,
                    meta={
                        "point": point,
                        "lo": lo,
                        "hi": hi,
                        "coverage": coverage,
                        "policy": "climatology",
                        "realized_share": t.share,
                        "target_source": t.source,
                        "tape": tape,
                    },
                )
            )
    return claims


def settle_band_claims(claims: Sequence[Claim], store: TrustStore) -> int:
    n = 0
    for c in claims:
        realized = float(c.meta["realized_share"])
        success = float(c.meta["lo"]) <= realized <= float(c.meta["hi"])
        store.record(c)
        store.settle(c, success=success)
        n += 1
    return n


def policy_block(rows: Sequence[Claim], *, alpha: float = 0.20) -> dict[str, Any]:
    """Coverage + Wilson interval + interval score for one policy's claims."""
    n = len(rows)
    if n == 0:
        return {"n": 0}
    hits = sum(1 for c in rows if c.success)
    scores = [
        interval_score(
            float(c.meta["realized_share"]), float(c.meta["lo"]), float(c.meta["hi"]), alpha=alpha
        )
        for c in rows
    ]
    widths = [float(c.meta["hi"]) - float(c.meta["lo"]) for c in rows]
    w_lo, w_hi = wilson_interval(hits, n)
    return {
        "n": n,
        "coverage_observed": hits / n,
        "coverage_wilson95": [round(w_lo, 3), round(w_hi, 3)],
        "mean_interval_score": sum(scores) / n,
        "mean_width": sum(widths) / n,
    }


def tape_report(
    claims: Sequence[Claim],
    *,
    policies: Sequence[str],
    alpha: float = 0.20,
    events: Sequence[Any] = (),
    migration_edges: Sequence[Any] = (),
) -> dict[str, Any]:
    """Per-policy blocks with polity-aware calm/shock split (E5) and
    per-target-source lanes."""
    settled = [c for c in claims if c.settled]
    if events:
        tag_shock_claims_contact(settled, events, migration_edges)
    split = split_calm_shock(settled)

    out: dict[str, Any] = {"policies": {}, "n_settled": len(settled)}
    for policy in policies:
        rows = [c for c in settled if c.meta.get("policy") == policy]
        block = policy_block(rows, alpha=alpha)
        block["calm"] = policy_block(
            [c for c in split["calm"] if c.meta.get("policy") == policy], alpha=alpha
        )
        block["shock"] = policy_block(
            [c for c in split["shock"] if c.meta.get("policy") == policy], alpha=alpha
        )
        by_src: dict[str, Any] = {}
        for src in sorted({c.meta.get("target_source", "?") for c in rows}):
            by_src[src] = policy_block(
                [c for c in rows if c.meta.get("target_source") == src], alpha=alpha
            )
        block["by_target_source"] = by_src
        out["policies"][policy] = block
    return out


# ---------------------------------------------------------------------------
# E4 — candidate policies
# ---------------------------------------------------------------------------

_LEVEL_VOCAB = ("trace", "minority", "significant", "plural", "majority", "dominant")
_DELTA_VOCAB = ("big_down", "down", "flat", "up", "big_up", "na")
_GAP_VOCAB = ("close", "decade", "generation", "era")
_VOL_VOCAB = ("na", "calm", "drift", "turbulent")


def _origin_vector(
    level: str, prior_delta: str, gap: str, vol: str, share: float, prior_rate: float | None
) -> np.ndarray:
    """Origin-only context vector — no outcome features, so a query cannot
    leak the rate it is asking the neighbors to predict."""
    feats: list[float] = [float(share), 0.0 if prior_rate is None else float(prior_rate)]
    for label, vocab in (
        (level, _LEVEL_VOCAB),
        (prior_delta, _DELTA_VOCAB),
        (gap, _GAP_VOCAB),
        (vol, _VOL_VOCAB),
    ):
        feats.extend(1.0 if label == v else 0.0 for v in vocab)
    v = np.asarray(feats, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _train_transitions(series: Series, cut_year: int) -> list[dict[str, Any]]:
    """All train-window transitions with origin context (cross-series catalog)."""
    rows: list[dict[str, Any]] = []
    for (pid, group), pts in sorted(series.items()):
        train = _train_points(pts, cut_year)
        prior_rates: list[float] = []
        for (y0, s0), (y1, s1) in zip(train, train[1:]):
            gap = y1 - y0
            if gap <= 0:
                continue
            rate = (s1 - s0) / gap * 10.0
            prior_rate = prior_rates[-1] if prior_rates else None
            prior_vol = (
                sum(abs(r) for r in prior_rates) / len(prior_rates)
                if len(prior_rates) >= 2
                else None
            )
            rows.append(
                {
                    "polity_id": pid,
                    "group": group,
                    "year_from": y0,
                    "rate": rate,
                    "vector": _origin_vector(
                        level_bin(s0),
                        delta_bin(prior_rate) if prior_rate is not None else "na",
                        gap_bin(gap),
                        vol_bin(prior_vol),
                        s0,
                        prior_rate,
                    ),
                }
            )
            prior_rates.append(rate)
    return rows


def analog_claims(
    series: Series,
    *,
    cut_year: int,
    coverage: float = 0.80,
    target_exclude_sources: frozenset[str] = TARGET_EXCLUDE_DEFAULT,
    target_year_max: int | None = None,
    k: int = 25,
    min_neighbors: int = 8,
    tape: str = "",
) -> list[Claim]:
    """Candidate 1: place-context analog retrieval (Phase 1 machinery enters
    the arena). Neighbors' rate/decade outcomes form the forecast
    distribution; band = 10th–90th neighbor-rate quantiles over the horizon.

    Fixed hyperparameters (k, min_neighbors, quantiles) — pre-declared, not
    tuned. Abstains without a query transition or enough neighbors.
    """
    catalog = _train_transitions(series, cut_year)
    if not catalog:
        return []
    matrix = np.stack([r["vector"] for r in catalog])

    claims: list[Claim] = []
    for (pid, group), pts in sorted(series.items()):
        train = _train_points(pts, cut_year)
        if len(train) < 2:
            continue  # no query context
        targets = [
            p
            for p in pts
            if p.year > cut_year
            and p.source not in target_exclude_sources
            and (target_year_max is None or p.year <= target_year_max)
        ]
        if not targets:
            continue

        # Query context: state at the last train point, prior move known.
        (y0, s0), (y1, s1) = train[-2], train[-1]
        last_rate = (s1 - s0) / (y1 - y0) * 10.0
        prior_rates = [
            (b[1] - a[1]) / (b[0] - a[0]) * 10.0 for a, b in zip(train, train[1:])
        ]
        prior_vol = (
            sum(abs(r) for r in prior_rates[:-1]) / len(prior_rates[:-1])
            if len(prior_rates) >= 3
            else None
        )
        for t in targets:
            horizon_dec = max(float(t.year - y1), 1.0) / 10.0
            q = _origin_vector(
                level_bin(s1),
                delta_bin(last_rate),
                gap_bin(t.year - y1),
                vol_bin(prior_vol),
                s1,
                last_rate,
            )
            # Exclude the query series' own transitions from its neighbors.
            mask = [
                i
                for i, r in enumerate(catalog)
                if not (r["polity_id"] == pid and r["group"] == group)
            ]
            if len(mask) < min_neighbors:
                continue
            sims = matrix[mask] @ q
            order = np.argsort(-sims)[: min(k, len(mask))]
            rates = [catalog[mask[i]]["rate"] for i in order]
            if len(rates) < min_neighbors:
                continue
            point = _clip01(s1 + _quantile(rates, 0.5) * horizon_dec)
            lo = _clip01(s1 + _quantile(rates, 0.10) * horizon_dec)
            hi = _clip01(s1 + _quantile(rates, 0.90) * horizon_dec)
            lo, hi = min(lo, point), max(hi, point)
            claims.append(
                Claim(
                    claim_id=_cid(tape, "forecast:analog", pid, group, cut_year, t.year),
                    hypothesis_id="forecast:analog",
                    polity_id=pid,
                    group=group,
                    cut_year=cut_year,
                    predicted="in_band",
                    stated_p=coverage,
                    train_n=len(train),
                    year_from=cut_year,
                    year_to=t.year,
                    meta={
                        "point": point,
                        "lo": lo,
                        "hi": hi,
                        "coverage": coverage,
                        "policy": "analog",
                        "realized_share": t.share,
                        "target_source": t.source,
                        "n_neighbors": len(rates),
                        "tape": tape,
                    },
                )
            )
    return claims


_SIMPLEX = [
    (wp / 4.0, wr / 4.0, wa / 4.0)
    for wp in range(5)
    for wr in range(5)
    for wa in range(5)
    if wp + wr + wa == 4
]


def fit_ensemble_weights(
    selection_claims: Sequence[Claim], *, alpha: float = 0.20
) -> tuple[float, float, float]:
    """Grid-search convex weights over (persistence, reversion, ar1) points
    minimizing mean interval score on the *selection* tape. The band around
    the blended point is borrowed from the claim rows themselves (same width
    model), recentered on the blend.
    """
    # index: (pid, group, target_year) → {policy: claim}
    keyed: dict[tuple[str, str, int], dict[str, Claim]] = defaultdict(dict)
    for c in selection_claims:
        keyed[(c.polity_id, c.group, c.year_to)][str(c.meta["policy"])] = c

    best, best_score = (1.0, 0.0, 0.0), float("inf")
    for wp, wr, wa in _SIMPLEX:
        scores: list[float] = []
        for _key, by_pol in keyed.items():
            avail = {p: by_pol[p] for p in ("persistence", "reversion", "ar1") if p in by_pol}
            if "persistence" not in avail:
                continue
            w = {"persistence": wp, "reversion": wr, "ar1": wa}
            tot = sum(w[p] for p in avail)
            if tot <= 0:
                continue
            point = sum(float(avail[p].meta["point"]) * w[p] for p in avail) / tot
            ref = avail["persistence"]
            width = float(ref.meta["hi"]) - float(ref.meta["lo"])
            lo, hi = _place_band(_clip01(point), width)
            scores.append(
                interval_score(float(ref.meta["realized_share"]), lo, hi, alpha=alpha)
            )
        if scores:
            s = sum(scores) / len(scores)
            if s < best_score:
                best, best_score = (wp, wr, wa), s
    return best


def ensemble_claims(
    series: Series,
    *,
    cut_year: int,
    weights: tuple[float, float, float],
    width_model: str = "w0",
    coverage: float = 0.80,
    target_exclude_sources: frozenset[str] = TARGET_EXCLUDE_DEFAULT,
    target_year_max: int | None = None,
    dynamics: Dynamics | None = None,
    conformal_lambdas: dict[str, float] | None = None,
    tape: str = "",
) -> list[Claim]:
    """Candidate 2: shrinkage blend of baseline points, frozen weights."""
    wp, wr, wa = weights
    if width_model == "w2" and dynamics is None:
        dynamics = fit_series_dynamics(series, cut_year=cut_year)
    claims: list[Claim] = []
    for (pid, group), pts in sorted(series.items()):
        train = _train_points(pts, cut_year)
        if len(train) < 1:
            continue
        targets = [
            p
            for p in pts
            if p.year > cut_year
            and p.source not in target_exclude_sources
            and (target_year_max is None or p.year <= target_year_max)
        ]
        for t in targets:
            w: dict[str, float] = {}
            pointset: dict[str, float] = {}
            for policy, wgt in (("persistence", wp), ("reversion", wr), ("ar1", wa)):
                if wgt > 0 and len(train) >= _min_train(policy):
                    pointset[policy] = _clip01(_point(train, policy, t.year))
                    w[policy] = wgt
            if not pointset:
                continue
            tot = sum(w.values())
            point = _clip01(sum(pointset[p] * w[p] for p in pointset) / tot)
            lam = (conformal_lambdas or {}).get("persistence", 1.0)
            width, wmeta = compute_width(
                train,
                target_year=t.year,
                policy="persistence",
                model=width_model,
                dynamics=dynamics,
                conformal_lambda=lam,
            )
            lo, hi = _place_band(point, width)
            claims.append(
                Claim(
                    claim_id=_cid(tape, "forecast:ensemble", pid, group, cut_year, t.year),
                    hypothesis_id="forecast:ensemble",
                    polity_id=pid,
                    group=group,
                    cut_year=cut_year,
                    predicted="in_band",
                    stated_p=coverage,
                    train_n=len(train),
                    year_from=cut_year,
                    year_to=t.year,
                    meta={
                        "point": point,
                        "lo": lo,
                        "hi": hi,
                        "coverage": coverage,
                        "policy": "ensemble",
                        "realized_share": t.share,
                        "target_source": t.source,
                        "weights": list(weights),
                        "tape": tape,
                        **wmeta,
                    },
                )
            )
    return claims


def paired_comparison(
    a_claims: Sequence[Claim],
    b_claims: Sequence[Claim],
    *,
    alpha: float = 0.20,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """Paired interval-score comparison on shared targets + bootstrap CI.

    The unpaired means in the verdict block hide abstention effects (a
    candidate that skips hard targets looks better than it is, and vice
    versa). Pairing on (polity, group, target_year) removes that.
    Positive diff = A worse than B.
    """
    key = lambda c: (c.polity_id, c.group, c.year_to)  # noqa: E731
    a_by, b_by = {key(c): c for c in a_claims}, {key(c): c for c in b_claims}
    common = sorted(set(a_by) & set(b_by))
    if not common:
        return {"n_paired": 0}

    def _is(c: Claim) -> float:
        return interval_score(
            float(c.meta["realized_share"]), float(c.meta["lo"]), float(c.meta["hi"]), alpha=alpha
        )

    diffs = [_is(a_by[k]) - _is(b_by[k]) for k in common]
    rng = random.Random(seed)
    boots = sorted(
        sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(n_boot)
    )
    a_only = set(a_by) - set(b_by)
    return {
        "n_paired": len(common),
        "mean_is_a": sum(_is(a_by[k]) for k in common) / len(common),
        "mean_is_b": sum(_is(b_by[k]) for k in common) / len(common),
        "mean_diff_a_minus_b": sum(diffs) / len(diffs),
        "diff_bootstrap95": [boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)]],
        "b_wins_on": sum(1 for d in diffs if d > 0),
        "a_abstained_extra": len(set(b_by) - set(a_by)),
        "b_abstained_extra": len(a_only),
    }


# ---------------------------------------------------------------------------
# E6 — bridge disaggregation + anchor-drop curves
# ---------------------------------------------------------------------------

GAP_BUCKETS = ((1, 5), (6, 10), (11, 25), (26, 50), (51, 10_000))


def _gap_bucket(gap: int) -> str:
    for lo, hi in GAP_BUCKETS:
        if lo <= gap <= hi:
            return f"{lo}-{hi}" if hi < 10_000 else f"{lo}+"
    return "0"


def anchor_drop_curves(
    series: Series,
    dynamics: Dynamics,
    *,
    min_points: int = 4,
    width_shapes: Sequence[str] = ("linear", "sqrt"),
    alpha: float = 0.20,
) -> dict[str, Any]:
    """E6b/E6c: leave-one-out over dense series → coverage vs anchor gap.

    For every series with >= min_points, hide each point, backfill from the
    survivors, score hit/miss + interval score. Aggregated by gap bucket —
    this is the calibration-vs-sparsity curve, measured on the modern desk
    where truth is plentiful.
    """
    out: dict[str, Any] = {}
    for shape in width_shapes:
        rows: list[tuple[int, bool, float, float]] = []  # gap, hit, IS, width
        n_series = 0
        for (_pid, _group), pts in sorted(series.items()):
            if len(pts) < min_points:
                continue
            n_series += 1
            for i, held in enumerate(pts):
                support = [(p.year, p.share) for j, p in enumerate(pts) if j != i]
                est = backfill_series(
                    support, dynamics, years=[held.year], coverage=0.80, width_shape=shape
                )[0]
                hit = est.lo <= held.share <= est.hi
                sc = interval_score(held.share, est.lo, est.hi, alpha=alpha)
                rows.append((est.nearest_anchor_gap, hit, sc, est.hi - est.lo))
        buckets: dict[str, Any] = {}
        for label in [f"{lo}-{hi}" if hi < 10_000 else f"{lo}+" for lo, hi in GAP_BUCKETS]:
            sub = [r for r in rows if _gap_bucket(r[0]) == label]
            if not sub:
                buckets[label] = {"n": 0}
                continue
            hits = sum(1 for r in sub if r[1])
            w_lo, w_hi = wilson_interval(hits, len(sub))
            buckets[label] = {
                "n": len(sub),
                "coverage_observed": hits / len(sub),
                "coverage_wilson95": [round(w_lo, 3), round(w_hi, 3)],
                "mean_interval_score": sum(r[2] for r in sub) / len(sub),
                "mean_width": sum(r[3] for r in sub) / len(sub),
            }
        n_total = len(rows)
        hits_total = sum(1 for r in rows if r[1])
        out[shape] = {
            "n_series": n_series,
            "n_holdouts": n_total,
            "coverage_overall": hits_total / n_total if n_total else None,
            "mean_interval_score": sum(r[2] for r in rows) / n_total if n_total else None,
            "by_gap": buckets,
        }
    return out


def bridge_block(
    holdouts: Sequence[Any],  # Anchors
    support: Sequence[tuple[int, float]],
    dynamics: Dynamics,
    *,
    group: str = "muslim",
    loo: bool = False,
    width_shape: str = "linear",
    alpha: float = 0.20,
) -> dict[str, Any]:
    """E6a: one disaggregated bridge experiment (same- or cross-polity),
    scored with coverage + Wilson + interval score."""
    contested = set(PREREGISTRATION["contested_validation_excluded"])
    n = hits = excluded = 0
    scores: list[float] = []
    for a in holdouts:
        src = str(a.source_ids[0]) if a.source_ids else "unknown"
        if src in contested:
            excluded += 1
            continue
        sup = [(y, s) for y, s in support if not loo or y != a.year]
        if not sup:
            continue
        est = backfill_series(
            sup, dynamics, years=[a.year], coverage=0.80, width_shape=width_shape
        )[0]
        share = float(a.shares.get(group, 0.0))
        n += 1
        if est.lo <= share <= est.hi:
            hits += 1
        scores.append(interval_score(share, est.lo, est.hi, alpha=alpha))
    w_lo, w_hi = wilson_interval(hits, n)
    return {
        "n": n,
        "n_excluded_contested": excluded,
        "coverage_observed": hits / n if n else None,
        "coverage_wilson95": [round(w_lo, 3), round(w_hi, 3)] if n else None,
        "mean_interval_score": sum(scores) / n if n else None,
        "width_shape": width_shape,
    }
