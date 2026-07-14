"""Temporal-cut policy claims + source corroboration + calibration.

Dress rehearsal for the North-Star 1975-cut protocol, plus the
``source_trust:*`` scorekeeper.

**Walk-forward discipline.** Learned tables (hash buckets, majority) are
frozen at ``cut_year`` using only transitions with ``year_to <= cut``.
``reversion`` / ``persistence`` may condition on the immediately preceding
*observed* transition even when it post-dates the cut — by ``year_from``
that outcome has settled. Parameters freeze; features walk forward.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .learning import Claim, TrustStore
from .movement import CatalogRow, hash_outcome_table
from .schema import Anchor

POLICIES = ("hash_mode", "reversion", "persistence", "majority")


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
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


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


def _prev_map(catalog: Sequence[CatalogRow]) -> dict[tuple, CatalogRow | None]:
    """Map each row key → immediately preceding row for same polity×group."""
    by_pg: dict[tuple[str, str], list[CatalogRow]] = defaultdict(list)
    for r in sorted(catalog, key=lambda x: (x.polity_id, x.group, x.year_from)):
        by_pg[(r.polity_id, r.group)].append(r)
    out: dict[tuple, CatalogRow | None] = {}
    for series in by_pg.values():
        prev: CatalogRow | None = None
        for r in series:
            key = (r.polity_id, r.group, r.year_from, r.year_to)
            out[key] = prev
            prev = r
    return out


def _pattern_hit_rate(
    train: Sequence[CatalogRow], prev_map: dict, kind: str
) -> float:
    """Among train rows with a prior, how often reversion/persistence held."""
    hits = 0
    n = 0
    for r in train:
        key = (r.polity_id, r.group, r.year_from, r.year_to)
        prev = prev_map.get(key)
        if prev is None:
            continue
        n += 1
        if kind == "reversion":
            if r.outcome == _opposite(prev.outcome):
                hits += 1
        elif kind == "persistence":
            if r.outcome == prev.outcome:
                hits += 1
    if n == 0:
        return 0.5
    return hits / n


def make_policy_claims(
    catalog: Sequence[CatalogRow],
    *,
    cut_year: int,
    min_bucket_n: int = 2,
) -> list[Claim]:
    """Emit post-cut policy claims from a frozen pre-cut training table."""
    train = [
        r
        for r in catalog
        if r.year_to <= cut_year and not (r.year_from < cut_year < r.year_to)
    ]
    # Straddlers excluded explicitly (redundant with year_to <= cut, but clear).
    claim_rows = [
        r
        for r in catalog
        if r.year_from >= cut_year and not (r.year_from < cut_year < r.year_to)
    ]

    table = hash_outcome_table(train, min_n=min_bucket_n)
    train_outcomes = [r.outcome for r in train]
    maj = _mode(train_outcomes)
    train_n = len(train)
    freq = Counter(train_outcomes)
    prev_map = _prev_map(catalog)  # full catalog for walk-forward features
    rev_p = _pattern_hit_rate(train, prev_map, "reversion")
    pers_p = _pattern_hit_rate(train, prev_map, "persistence")

    claims: list[Claim] = []
    for r in sorted(claim_rows, key=lambda x: (x.polity_id, x.group, x.year_from)):
        key = (r.polity_id, r.group, r.year_from, r.year_to)
        prev = prev_map.get(key)

        preds: dict[str, tuple[str | None, float]] = {}

        entry = table.get(r.origin_hash)
        if entry is not None:
            preds["hash_mode"] = (entry.mode, float(entry.purity))
        else:
            preds["hash_mode"] = (None, 0.0)

        if prev is None:
            preds["reversion"] = (None, 0.0)
            preds["persistence"] = (None, 0.0)
        else:
            preds["reversion"] = (_opposite(prev.outcome), float(rev_p))
            preds["persistence"] = (prev.outcome, float(pers_p))

        if maj is None:
            preds["majority"] = (None, 0.0)
        else:
            p_maj = (freq[maj] / train_n) if train_n else 0.5
            preds["majority"] = (maj, float(max(p_maj, 1e-6)))

        for policy in POLICIES:
            predicted, stated_p = preds[policy]
            if predicted is None:
                continue
            stated_p = min(1.0, max(1e-6, stated_p))
            hyp = f"policy:{policy}"
            claims.append(
                Claim(
                    claim_id=_claim_id(
                        hyp, r.polity_id, r.group, r.year_from, r.year_to, cut_year
                    ),
                    hypothesis_id=hyp,
                    polity_id=r.polity_id,
                    group=r.group,
                    cut_year=cut_year,
                    predicted=predicted,
                    stated_p=stated_p,
                    train_n=train_n,
                    year_from=r.year_from,
                    year_to=r.year_to,
                    meta={"origin_hash": r.origin_hash, "policy": policy},
                )
            )
    return claims


def settle_policy_claims(
    claims: Sequence[Claim],
    catalog: Sequence[CatalogRow],
    store: TrustStore,
) -> int:
    """Compare each claim to the catalog outcome; record + settle exactly once."""
    outcome_by_key = {
        (r.polity_id, r.group, r.year_from, r.year_to): r.outcome for r in catalog
    }
    n = 0
    for c in claims:
        key = (c.polity_id, c.group, c.year_from, c.year_to)
        actual = outcome_by_key[key]
        success = c.predicted == actual
        store.record(c)
        store.settle(c, success=success)
        n += 1
    return n


# ---------------------------------------------------------------------------
# Source corroboration
# ---------------------------------------------------------------------------


def _primary_source(anchor: Anchor) -> str:
    if not anchor.source_ids:
        return "unknown"
    return str(anchor.source_ids[0])


def make_corroboration_claims(
    anchors: Sequence[Anchor],
    *,
    group: str,
    tolerance_pp: float,
    max_gap_years: int,
) -> list[Claim]:
    """Claim that source S's share will be corroborated by the next independent source."""
    by_polity: dict[str, list[Anchor]] = defaultdict(list)
    for a in anchors:
        by_polity[a.polity_id].append(a)

    claims: list[Claim] = []
    for pid, rows in by_polity.items():
        series = sorted(rows, key=lambda a: (a.year, _primary_source(a)))
        for i, a in enumerate(series):
            src = _primary_source(a)
            nxt: Anchor | None = None
            for b in series[i + 1 :]:
                if b.year == a.year:
                    continue
                gap = b.year - a.year
                if gap > max_gap_years:
                    break
                if _primary_source(b) == src:
                    continue  # no self-corroboration; keep scanning
                nxt = b
                break
            if nxt is None:
                continue
            claimed = float(a.shares.get(group, 0.0))
            observed = float(nxt.shares.get(group, 0.0))
            hyp = f"source_trust:{src}"
            claims.append(
                Claim(
                    claim_id=_claim_id(
                        hyp, pid, group, a.year, nxt.year, a.year
                    ),
                    hypothesis_id=hyp,
                    polity_id=pid,
                    group=group,
                    cut_year=a.year,
                    predicted="agree",
                    stated_p=float(a.confidence) if 0.0 < a.confidence <= 1.0 else 0.5,
                    train_n=1,
                    year_from=a.year,
                    year_to=nxt.year,
                    meta={
                        "claimed_share": claimed,
                        "observed_share": observed,
                        "tolerance_pp": tolerance_pp,
                        "settling_source": _primary_source(nxt),
                        "claiming_source": src,
                    },
                )
            )
    return claims


def settle_corroboration_claims(claims: Sequence[Claim], store: TrustStore) -> int:
    n = 0
    for c in claims:
        claimed = float(c.meta["claimed_share"])
        observed = float(c.meta["observed_share"])
        tol = float(c.meta["tolerance_pp"])
        success = abs(claimed - observed) <= tol
        store.record(c)
        store.settle(c, success=success)
        n += 1
    return n


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationRow:
    p_lo: float
    p_hi: float
    n: int
    stated_mean: float
    observed: float

    def to_dict(self) -> dict:
        return asdict(self)


def calibration_table(
    claims: Sequence[Claim], *, bins: Sequence[float]
) -> list[CalibrationRow]:
    """Bin settled claims by stated_p. Last bin is inclusive of 1.0."""
    edges = list(bins)
    if len(edges) < 2:
        return []
    settled = [c for c in claims if c.settled and c.success is not None]
    buckets: list[list[Claim]] = [[] for _ in range(len(edges) - 1)]
    for c in settled:
        p = float(c.stated_p)
        placed = False
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            last = i == len(edges) - 2
            if last:
                if lo <= p <= hi:
                    buckets[i].append(c)
                    placed = True
                    break
            elif lo <= p < hi:
                buckets[i].append(c)
                placed = True
                break
        if not placed:
            # clamp into last bin
            buckets[-1].append(c)

    rows: list[CalibrationRow] = []
    for i, group in enumerate(buckets):
        if not group:
            continue
        lo, hi = edges[i], edges[i + 1]
        stated_mean = sum(float(c.stated_p) for c in group) / len(group)
        observed = sum(1 for c in group if c.success) / len(group)
        rows.append(
            CalibrationRow(
                p_lo=lo,
                p_hi=hi,
                n=len(group),
                stated_mean=stated_mean,
                observed=observed,
            )
        )
    return rows


def brier_score(claims: Sequence[Claim]) -> float:
    settled = [c for c in claims if c.settled and c.success is not None]
    if not settled:
        return 0.0
    total = 0.0
    for c in settled:
        outcome = 1.0 if c.success else 0.0
        total += (float(c.stated_p) - outcome) ** 2
    return total / len(settled)


def write_trust_report(
    store: TrustStore,
    claims: Sequence[Claim],
    path: str | Path,
    *,
    bins: Sequence[float] = (0.0, 0.5, 0.6, 0.8, 1.0),
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    posteriors = {
        hid: {
            "alpha": post.alpha,
            "beta": post.beta,
            "trials": post.trials,
            "mean": post.mean,
        }
        for hid, post in store.posteriors.items()
    }
    calib = [r.to_dict() for r in calibration_table(claims, bins=bins)]
    payload = {
        "posteriors": posteriors,
        "calibration": calib,
        "brier": brier_score(claims),
        "n_claims": len(claims),
        "n_settled": sum(1 for c in claims if c.settled),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
