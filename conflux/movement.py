"""Year/decade-scale place-hash and movement catalog (Phase 1).

Port-and-retune of ptv-embed-lab ``lab_movement.py``: discretize a node's
*place* in movement space, catalog where moves from that place led. Units
are Δshare per decade so sparse century gaps remain comparable to dense
Pew decades. No patient graph / connascence.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from .schema import Anchor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLACE_VECTOR_DIM = 32
_FLAT = 0.005  # share points / decade — under census noise → flat


# ---------------------------------------------------------------------------
# Bin functions (total)
# ---------------------------------------------------------------------------


def delta_bin(rate: float) -> str:
    """``rate`` = Δshare per decade."""
    r = float(rate)
    if r <= -0.05:
        return "big_down"
    if r <= -_FLAT:
        return "down"
    if r < _FLAT:
        return "flat"
    if r < 0.05:
        return "up"
    return "big_up"


def gap_bin(years: float) -> str:
    y = float(years)
    if y <= 5:
        return "close"
    if y <= 15:
        return "decade"
    if y <= 35:
        return "generation"
    return "era"


def level_bin(share: float) -> str:
    s = float(share)
    if s < 0.01:
        return "trace"
    if s < 0.10:
        return "minority"
    if s < 0.35:
        return "significant"
    if s < 0.65:
        return "plural"
    if s < 0.90:
        return "majority"
    return "dominant"


def vol_bin(vol: float | None) -> str:
    """``vol`` = mean |rate/decade| over *prior* transitions; ``None`` → na."""
    if vol is None:
        return "na"
    v = abs(float(vol))
    if v < _FLAT:
        return "calm"
    if v < 0.03:
        return "drift"
    return "turbulent"


def direction(rate: float) -> str:
    """Settlement label — same ±0.005 flat threshold as ``delta_bin``."""
    r = float(rate)
    if r >= _FLAT:
        return "up"
    if r <= -_FLAT:
        return "down"
    return "flat"


def place_hash(*, level: str, delta: str, gap: str, vol: str) -> str:
    """Deterministic place signature. No polity_id / group (metadata only)."""
    return f"{level}|{delta}|{gap}|{vol}"


# ---------------------------------------------------------------------------
# Events / catalog rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MovementEvent:
    polity_id: str
    group: str
    year_from: int
    year_to: int
    gap_years: int
    share_from: float
    share_to: float
    delta: float
    rate_per_decade: float
    confidence: float
    origin_hash: str
    # Causal priors used to stamp origin_hash / vectors (not identity).
    prior_rate: float | None = None
    prior_vol: float | None = None


@dataclass(frozen=True)
class CatalogRow:
    polity_id: str
    group: str
    year_from: int
    year_to: int
    origin_hash: str
    vector: np.ndarray
    outcome: str


@dataclass(frozen=True)
class HashEntry:
    n: int
    dist: dict[str, float]
    mode: str
    purity: float


def _share(anchor: Anchor, group: str) -> float:
    return float(anchor.shares.get(group, 0.0))


def _dedupe_same_year(rows: list[Anchor]) -> list[Anchor]:
    """Keep highest-confidence anchor per polity-year."""
    best: dict[tuple[str, int], Anchor] = {}
    for a in rows:
        key = (a.polity_id, a.year)
        prev = best.get(key)
        if prev is None or a.confidence > prev.confidence:
            best[key] = a
    return sorted(best.values(), key=lambda a: (a.polity_id, a.year))


def movement_events(anchors: Sequence[Anchor], group: str) -> list[MovementEvent]:
    """Consecutive-anchor transitions for one religion group. No interpolation."""
    rows = _dedupe_same_year(list(anchors))
    by_polity: dict[str, list[Anchor]] = defaultdict(list)
    for a in rows:
        by_polity[a.polity_id].append(a)

    events: list[MovementEvent] = []
    for pid in sorted(by_polity):
        series = by_polity[pid]
        prior_rates: list[float] = []
        for i in range(len(series) - 1):
            a0, a1 = series[i], series[i + 1]
            gap = a1.year - a0.year
            if gap <= 0:
                continue  # should not happen after dedupe
            s0, s1 = _share(a0, group), _share(a1, group)
            delta = s1 - s0
            rate = (delta / gap) * 10.0
            prior_vol = (
                float(sum(abs(r) for r in prior_rates) / len(prior_rates))
                if len(prior_rates) >= 2
                else None
            )
            prior_rate = prior_rates[-1] if prior_rates else None
            # Predictive origin place: prior move direction (or "na"), not
            # this transition's delta — otherwise hash_mode trivially encodes
            # the outcome it is asked to predict (see PHASE1_TEST_SPEC note).
            delta_label = delta_bin(prior_rate) if prior_rate is not None else "na"
            oh = place_hash(
                level=level_bin(s0),
                delta=delta_label,
                gap=gap_bin(gap),
                vol=vol_bin(prior_vol),
            )
            events.append(
                MovementEvent(
                    polity_id=pid,
                    group=group,
                    year_from=a0.year,
                    year_to=a1.year,
                    gap_years=gap,
                    share_from=s0,
                    share_to=s1,
                    delta=delta,
                    rate_per_decade=rate,
                    confidence=min(a0.confidence, a1.confidence),
                    origin_hash=oh,
                    prior_rate=prior_rate,
                    prior_vol=prior_vol,
                )
            )
            prior_rates.append(rate)
    return events


def _one_hot(label: str, vocabulary: Sequence[str]) -> list[float]:
    return [1.0 if label == v else 0.0 for v in vocabulary]


def place_vector(event: MovementEvent, *, weighted: bool = False) -> np.ndarray:
    """Fixed-length L2-normalized float32 place vector."""
    level_vocab = ("trace", "minority", "significant", "plural", "majority", "dominant")
    delta_vocab = ("big_down", "down", "flat", "up", "big_up", "na")
    gap_vocab = ("close", "decade", "generation", "era")
    vol_vocab = ("na", "calm", "drift", "turbulent")

    prior_label = (
        delta_bin(event.prior_rate) if event.prior_rate is not None else "na"
    )
    feats: list[float] = [
        float(event.share_from),
        float(event.rate_per_decade),
        math.log1p(float(event.gap_years)) / math.log1p(100.0),
        0.0 if event.prior_vol is None else float(event.prior_vol),
        0.0 if event.prior_rate is None else float(event.prior_rate),
    ]
    feats.extend(_one_hot(level_bin(event.share_from), level_vocab))
    feats.extend(_one_hot(delta_bin(event.rate_per_decade), delta_vocab))
    feats.extend(_one_hot(prior_label, delta_vocab))
    feats.extend(_one_hot(gap_bin(event.gap_years), gap_vocab))
    feats.extend(_one_hot(vol_bin(event.prior_vol), vol_vocab))

    # Pad / trim to fixed dim.
    if len(feats) < PLACE_VECTOR_DIM:
        feats.extend([0.0] * (PLACE_VECTOR_DIM - len(feats)))
    else:
        feats = feats[:PLACE_VECTOR_DIM]

    v = np.asarray(feats, dtype=np.float32)
    if weighted:
        # Confidence must change vector *direction*, not only scale
        # (L2-normalization would cancel a pure scale factor).
        v = v.copy()
        v[-1] = np.float32(float(event.confidence))
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        v = np.zeros(PLACE_VECTOR_DIM, dtype=np.float32)
        v[0] = 1.0
        return v
    return (v / np.float32(n)).astype(np.float32)


def build_catalog(
    anchors: Sequence[Anchor], groups: Iterable[str], *, weighted: bool = False
) -> list[CatalogRow]:
    rows: list[CatalogRow] = []
    for g in groups:
        for ev in movement_events(anchors, group=g):
            rows.append(
                CatalogRow(
                    polity_id=ev.polity_id,
                    group=ev.group,
                    year_from=ev.year_from,
                    year_to=ev.year_to,
                    origin_hash=ev.origin_hash,
                    vector=place_vector(ev, weighted=weighted),
                    outcome=direction(ev.rate_per_decade),
                )
            )
    return rows


def cosine_topk(
    query: np.ndarray, matrix: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Cosine top-k assuming ``query`` and rows of ``matrix`` are L2-normalized."""
    q = np.asarray(query, dtype=np.float32).reshape(-1)
    mat = np.asarray(matrix, dtype=np.float32)
    if mat.ndim != 2 or mat.shape[0] == 0:
        return np.asarray([], dtype=np.int64), np.asarray([], dtype=np.float32)
    scores = mat @ q
    k_eff = min(int(k), mat.shape[0])
    # argpartition then sort the top slice descending
    if k_eff < mat.shape[0]:
        part = np.argpartition(-scores, k_eff - 1)[:k_eff]
        order = part[np.argsort(-scores[part])]
    else:
        order = np.argsort(-scores)
    return order.astype(np.int64), scores[order].astype(np.float32)


def hash_outcome_table(
    catalog: Sequence[CatalogRow], min_n: int
) -> dict[str, HashEntry]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for row in catalog:
        buckets[row.origin_hash].append(row.outcome)
    table: dict[str, HashEntry] = {}
    for h, outcomes in buckets.items():
        n = len(outcomes)
        if n < int(min_n):
            continue
        counts = Counter(outcomes)
        dist = {k: counts[k] / n for k in ("up", "down", "flat") if counts[k]}
        # include only observed; renormalize if needed
        s = sum(dist.values())
        dist = {k: v / s for k, v in dist.items()}
        mode, purity = max(dist.items(), key=lambda kv: kv[1])
        table[h] = HashEntry(n=n, dist=dist, mode=mode, purity=float(purity))
    return table
