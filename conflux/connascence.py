"""Connascence layer (Phase 2b) — deterministic edges + ledger consumers.

Implements docs/STRATEGY_CONNASCENCE.md:

  §2.1 STRUCTURAL   — method-family registry → corroboration independence
                      discount (graded settlement weight, never topology).
  §2.2 CONCEPTUAL   — complement / conservation / definition edges +
                      definitional routing away from source_trust:* +
                      conservation claims over migration edges.
  §2.3 CO_VARIANCE  — series co-movement discovery with complement
                      exclusion, bucket-stratified null, cosine shortlist;
                      one-hop partial settlement.
  §2.4 TEMPORAL     — event-window shock tagging + calm/shock calibration.
  §6.4              — repr_version provenance stamp on derived artifacts.

Every function here is arithmetic. The LLM proposer lives in
``conflux/llm_enrich.py`` and may only *propose*; promotion to an edge
happens through the verifiers that call back into this module.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .learning import Claim, TrustStore
from .movement import (
    MovementEvent,
    cosine_topk,
    delta_bin,
    direction,
    gap_bin,
    level_bin,
    place_hash,
    place_vector,
    vol_bin,
)
from .observations import ShareObservation
from .schema import Event, MigrationEdge

# Stamp for artifacts derived from the place-hash/vector pipeline (§6.4).
# Bump deliberately when bin edges / vector features change; settled claims
# keep the version they settled under.
REPR_VERSION = "place_hash_v1"

# ---------------------------------------------------------------------------
# §2.1 STRUCTURAL — method-family registry + independence discount
# ---------------------------------------------------------------------------

# Hand-curated; reviewed like a schema change. Every ingested source_id gets
# exactly one family. Unregistered sources fall back to a per-source family,
# so they are never same-family with anything but themselves (and
# self-corroboration is already banned upstream).
METHOD_REGISTRY: dict[str, str] = {
    "cbs_population_madaf": "census_registry",
    "ottoman_demographics_wiki": "census_registry",
    "arab_barometer": "survey_self_id",
    "pew_global_religious_composition_2010_2020": "demographic_synthesis",
    "jewishdatabank_world_jewish_population": "demographic_synthesis",
    "arda_national_profiles_2005": "wcd_derived",
    "mccarthy_armenian_pop_ottoman": "scholarly_estimate",
    "karpat_ottoman_population_1830_1914": "scholarly_estimate",
}

SAME_FAMILY_WEIGHT = 0.5


def method_family(source_id: str) -> str:
    return METHOD_REGISTRY.get(source_id, f"unregistered:{source_id}")


def independence_weight(source_a: str, source_b: str) -> float:
    """Settlement weight for a corroboration between two sources (§2.1).

    Same method family → sources share error modes → their agreement is
    partially self-agreement → discounted evidence. Never zero: same-family
    corroboration is weaker, not worthless.
    """
    if method_family(source_a) == method_family(source_b):
        return SAME_FAMILY_WEIGHT
    return 1.0


# ---------------------------------------------------------------------------
# §2.2 CONCEPTUAL — definitional coupling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnascenceEdge:
    src: str
    dst: str
    kind: str  # concept:complement | concept:conservation | concept:definition | co_variance
    strength: float
    meta: dict[str, Any] = field(default_factory=dict)
    repr_version: str = REPR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "kind": self.kind,
            "strength": self.strength,
            "meta": self.meta,
            "repr_version": self.repr_version,
        }


# Known definitional overlaps: (frozenset of the two source_ids, group)
# → label. WJP counts the Core Jewish Population (deliberately narrower
# than Pew's jewish bucket); CBS's Arab column is a muslim *proxy* that
# folds in Arab Christians and Druze (deliberately broader).
DEFINITION_OVERLAPS: dict[tuple[frozenset[str], str], str] = {
    (
        frozenset(
            {
                "jewishdatabank_world_jewish_population",
                "pew_global_religious_composition_2010_2020",
            }
        ),
        "jewish",
    ): "cjp_vs_pew_jewish",
    (
        frozenset({"cbs_population_madaf", "pew_global_religious_composition_2010_2020"}),
        "muslim",
    ): "cbs_arab_proxy_vs_pew_muslim",
    (
        frozenset({"cbs_population_madaf", "arda_national_profiles_2005"}),
        "muslim",
    ): "cbs_arab_proxy_vs_wcd_muslim",
    (
        frozenset(
            {
                "jewishdatabank_world_jewish_population",
                "cbs_population_madaf",
            }
        ),
        "jewish",
    ): "cjp_vs_cbs_jewish_registry",
}


def definition_overlap(source_a: str, source_b: str, group: str) -> str | None:
    return DEFINITION_OVERLAPS.get((frozenset({source_a, source_b}), group))


def complement_edges(observations: Sequence[ShareObservation]) -> list[ConnascenceEdge]:
    """Same source, same polity-year, different group → accounting bond.

    Complement binding lives *within one measurement*: a single source's
    snapshot sums to ~1, so its groups move against each other by
    arithmetic. Cross-source same-polity pairs are excluded here but still
    excluded from co-variance discovery (same-polity rule, §2.3).
    """
    by_spy: dict[tuple[str, str, int], list[ShareObservation]] = defaultdict(list)
    for o in observations:
        by_spy[(o.source_id, o.polity_id, o.year)].append(o)
    edges: list[ConnascenceEdge] = []
    for key in sorted(by_spy):
        rows = sorted(by_spy[key], key=lambda o: o.group)
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                edges.append(
                    ConnascenceEdge(
                        src=a.obs_id,
                        dst=b.obs_id,
                        kind="concept:complement",
                        strength=1.0,
                        meta={"polity_id": a.polity_id, "year": a.year},
                    )
                )
    return edges


def conservation_edges(migration_edges: Sequence[MigrationEdge]) -> list[ConnascenceEdge]:
    """Same group across the two ends of a migration edge (§2.2)."""
    out: list[ConnascenceEdge] = []
    for e in migration_edges:
        out.append(
            ConnascenceEdge(
                src=f"series|{e.from_polity}|{e.group.value}",
                dst=f"series|{e.to_polity}|{e.group.value}",
                kind="concept:conservation",
                strength=float(e.confidence),
                meta={
                    "edge_id": e.edge_id,
                    "year_start": e.year_start,
                    "year_end": e.year_end,
                    "volume_est": e.volume_est,
                },
            )
        )
    return out


def route_definitional_claims(claims: Sequence[Claim]) -> int:
    """Reroute definition-overlap corroborations away from ``source_trust:*``.

    A CJP-vs-Pew disagreement is a *definition gap*, not a source failure —
    settling it against source trust would unfairly drain (or pad) the
    ledger. Rerouted claims settle under ``definition_gap:<label>`` so the
    offset is tracked but quarantined. Returns the number rerouted.
    """
    n = 0
    for c in claims:
        a = str(c.meta.get("claiming_source", ""))
        b = str(c.meta.get("settling_source", ""))
        label = definition_overlap(a, b, c.group)
        if label is None:
            continue
        c.meta["routed_from"] = c.hypothesis_id
        c.meta["definition_overlap"] = label
        c.hypothesis_id = f"definition_gap:{label}"
        n += 1
    return n


def settle_corroboration_claims_weighted(
    claims: Sequence[Claim], store: TrustStore
) -> int:
    """Phase 2 corroboration settlement + §2.1 independence discount.

    Same success rule as ``settlement.settle_corroboration_claims`` (level
    tolerance from claim meta); the Beta bump is scaled by
    ``independence_weight`` of the claiming/settling source pair.
    """
    n = 0
    for c in claims:
        claimed = float(c.meta["claimed_share"])
        observed = float(c.meta["observed_share"])
        tol = float(c.meta["tolerance_pp"])
        success = abs(claimed - observed) <= tol
        w = independence_weight(
            str(c.meta.get("claiming_source", "")),
            str(c.meta.get("settling_source", "")),
        )
        c.meta["independence_weight"] = w
        c.meta["method_families"] = [
            method_family(str(c.meta.get("claiming_source", ""))),
            method_family(str(c.meta.get("settling_source", ""))),
        ]
        store.record(c)
        store.settle(c, success=success, weight=w)
        n += 1
    return n


# ---------------------------------------------------------------------------
# §2.2 conservation claims (accounting between polities)
# ---------------------------------------------------------------------------


def _claim_id(prefix: str, *parts: Any) -> str:
    raw = prefix + "|" + "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _bracket(
    series: Sequence[tuple[int, float]], year: int, slack: int
) -> tuple[int, float] | None:
    """Latest (year, count) at or before ``year``, within ``slack`` years."""
    best = None
    for y, v in series:
        if y <= year and year - y <= slack:
            if best is None or y > best[0]:
                best = (y, v)
    return best


def _bracket_after(
    series: Sequence[tuple[int, float]], year: int, slack: int
) -> tuple[int, float] | None:
    best = None
    for y, v in series:
        if y >= year and y - year <= slack:
            if best is None or y < best[0]:
                best = (y, v)
    return best


def make_conservation_claims(
    anchors: Sequence[Any],  # schema.Anchor
    migration_edges: Sequence[MigrationEdge],
    *,
    slack_years: int = 15,
    loss_floor: float = 0.5,
    loss_ceiling: float = 4.0,
) -> list[Claim]:
    """v0 accounting claims: a migration edge's origin loss should show up.

    For each edge, bracket both polities' absolute group counts
    (share × total_population) around [year_start, year_end]. Claim
    ``conserve``: origin count falls by at least ``loss_floor × volume_low``
    and at most ``loss_ceiling × volume_high`` (parallel flows + natural
    growth make exact equality wrong on purpose), and the destination count
    rises. Abstains (no claim) when bracketing anchors are missing —
    abstention is first-class.
    """
    counts: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    for a in anchors:
        for g, s in a.shares.items():
            counts[(a.polity_id, g)].append((a.year, float(s) * a.total_population))
    for v in counts.values():
        v.sort()

    claims: list[Claim] = []
    for e in migration_edges:
        g = e.group.value
        o_before = _bracket(counts.get((e.from_polity, g), []), e.year_start, slack_years)
        o_after = _bracket_after(counts.get((e.from_polity, g), []), e.year_end, slack_years)
        d_before = _bracket(counts.get((e.to_polity, g), []), e.year_start, slack_years)
        d_after = _bracket_after(counts.get((e.to_polity, g), []), e.year_end, slack_years)
        if not (o_before and o_after and d_before and d_after):
            continue  # abstain
        vol_low = e.volume_low if e.volume_low is not None else e.volume_est
        vol_high = e.volume_high if e.volume_high is not None else e.volume_est
        claims.append(
            Claim(
                claim_id=_claim_id("conservation", e.edge_id),
                hypothesis_id=f"conservation:{e.edge_id}",
                polity_id=e.from_polity,
                group=g,
                cut_year=e.year_start,
                predicted="conserve",
                stated_p=float(e.confidence),
                train_n=1,
                year_from=e.year_start,
                year_to=e.year_end,
                meta={
                    "edge_id": e.edge_id,
                    "to_polity": e.to_polity,
                    "volume_low": vol_low,
                    "volume_high": vol_high,
                    "origin_before": o_before,
                    "origin_after": o_after,
                    "dest_before": d_before,
                    "dest_after": d_after,
                    "loss_floor": loss_floor,
                    "loss_ceiling": loss_ceiling,
                },
            )
        )
    return claims


def settle_conservation_claims(claims: Sequence[Claim], store: TrustStore) -> int:
    n = 0
    for c in claims:
        origin_loss = float(c.meta["origin_before"][1]) - float(c.meta["origin_after"][1])
        dest_gain = float(c.meta["dest_after"][1]) - float(c.meta["dest_before"][1])
        lo = float(c.meta["loss_floor"]) * float(c.meta["volume_low"])
        hi = float(c.meta["loss_ceiling"]) * float(c.meta["volume_high"])
        success = (lo <= origin_loss <= hi) and dest_gain > 0
        c.meta["origin_loss"] = origin_loss
        c.meta["dest_gain"] = dest_gain
        store.record(c)
        store.settle(c, success=success)
        n += 1
    return n


# ---------------------------------------------------------------------------
# §2.3 CO_VARIANCE — co-movement discovery
# ---------------------------------------------------------------------------


def desk_movement_events(
    anchors: Sequence[Any],  # schema.Anchor
    observations: Sequence[ShareObservation],
    *,
    groups: Sequence[str] = ("muslim", "christian", "jewish"),
) -> list[MovementEvent]:
    """Movement events over the *merged* timeline (anchors + desk).

    Anchor-only series are 5 aligned points per polity, which caps
    cross-polity transition pairs at n=2 — below any honest admission
    floor. The desk (CBS annual, WJP yearly, AB waves, ARDA 2005) densifies
    the curve. Same transition math as ``movement.movement_events``:
    per-year dedupe by confidence, no interpolation, predictive origin
    hash from the *prior* move.
    """
    points: dict[tuple[str, str], dict[int, tuple[float, float]]] = defaultdict(dict)

    def add(pid: str, group: str, year: int, share: float, conf: float) -> None:
        cur = points[(pid, group)].get(year)
        if cur is None or conf > cur[1]:
            points[(pid, group)][year] = (share, conf)

    for a in anchors:
        for g in groups:
            add(a.polity_id, g, a.year, float(a.shares.get(g, 0.0)), a.confidence)
    for o in observations:
        if o.group in groups:
            add(o.polity_id, o.group, o.year, o.share, o.confidence)

    events: list[MovementEvent] = []
    for (pid, group) in sorted(points):
        series = sorted(points[(pid, group)].items())
        prior_rates: list[float] = []
        for i in range(len(series) - 1):
            (y0, (s0, c0)), (y1, (s1, c1)) = series[i], series[i + 1]
            gap = y1 - y0
            if gap <= 0:
                continue
            delta = s1 - s0
            rate = (delta / gap) * 10.0
            prior_vol = (
                sum(abs(r) for r in prior_rates) / len(prior_rates)
                if len(prior_rates) >= 2
                else None
            )
            prior_rate = prior_rates[-1] if prior_rates else None
            delta_label = delta_bin(prior_rate) if prior_rate is not None else "na"
            events.append(
                MovementEvent(
                    polity_id=pid,
                    group=group,
                    year_from=y0,
                    year_to=y1,
                    gap_years=gap,
                    share_from=s0,
                    share_to=s1,
                    delta=delta,
                    rate_per_decade=rate,
                    confidence=min(c0, c1),
                    origin_hash=place_hash(
                        level=level_bin(s0),
                        delta=delta_label,
                        gap=gap_bin(gap),
                        vol=vol_bin(prior_vol),
                    ),
                    prior_rate=prior_rate,
                    prior_vol=prior_vol,
                )
            )
            prior_rates.append(rate)
    return events


def _binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), exact."""
    p = min(1.0 - 1e-12, max(1e-12, p))
    return sum(
        math.comb(n, i) * p**i * (1.0 - p) ** (n - i) for i in range(k, n + 1)
    )


def bucket_up_rates(events: Sequence[MovementEvent]) -> tuple[dict[str, float], float]:
    """Per-bucket P(up | moving) + global fallback — the stratified null (§6.2)."""
    up: dict[str, int] = defaultdict(int)
    moving: dict[str, int] = defaultdict(int)
    g_up = g_moving = 0
    for e in events:
        d = direction(e.rate_per_decade)
        if d == "flat":
            continue
        moving[e.origin_hash] += 1
        g_moving += 1
        if d == "up":
            up[e.origin_hash] += 1
            g_up += 1
    global_rate = (g_up / g_moving) if g_moving else 0.5
    rates = {h: up[h] / moving[h] for h in moving}
    return rates, global_rate


def _overlap_years(a: MovementEvent, b: MovementEvent) -> int:
    return min(a.year_to, b.year_to) - max(a.year_from, b.year_from)


def _series_mean_vectors(
    by_series: dict[tuple[str, str], list[MovementEvent]]
) -> tuple[list[tuple[str, str]], np.ndarray]:
    keys = sorted(by_series)
    mat = np.zeros((len(keys), place_vector(by_series[keys[0]][0]).shape[0]), dtype=np.float32)
    for i, k in enumerate(keys):
        vecs = np.stack([place_vector(e) for e in by_series[k]])
        m = vecs.mean(axis=0)
        n = float(np.linalg.norm(m))
        mat[i] = m / n if n > 1e-12 else m
    return keys, mat


def _bh_fdr_pass(p_values: Sequence[float], alpha: float) -> list[bool]:
    """Benjamini–Hochberg: which p-values survive FDR control at ``alpha``."""
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    threshold = 0.0
    for rank, i in enumerate(order, start=1):
        if p_values[i] <= alpha * rank / m:
            threshold = p_values[i]
    return [p <= threshold if threshold > 0 else False for p in p_values]


def covariance_edges(
    events: Sequence[MovementEvent],
    *,
    min_overlap_pairs: int = 3,
    alpha: float = 0.05,
    shortlist_k: int | None = None,
    require_fdr: bool = True,
) -> list[ConnascenceEdge]:
    """Directional co-movement edges between (polity, group) series (§2.3).

    Rules from the strategy, in order:
      - complement exclusion: same-polity pairs never scored (they
        anti-covary by accounting — that's CONCEPTUAL, not dynamics);
      - only *moving* transition pairs with strictly positive window
        overlap count;
      - the null is bucket-stratified (§6.2): expected agreement for a
        pair is a function of each transition's origin-hash regime, so
        "both are declining series" cannot mint an edge on its own;
      - admission: ≥ ``min_overlap_pairs`` pairs, one-sided binomial
        p-value < ``alpha``, AND Benjamini–Hochberg FDR survival across
        all scored pairs (thousands of candidate pairs at raw α≈0.05
        would admit more noise than signal — the shuffle control proved
        it). ``require_fdr=False`` keeps raw-α edges as a *hypothesis
        tier*: flagged ``fdr_pass=False`` in meta, usable for cluster /
        REVIEW-queue generation, NEVER for partial settlement.
      - strength = observed agreement rate; q-value stored in meta.
      - ``shortlist_k``: optional cosine shortlist over mean place
        vectors (§6.3) — propose-only; the arithmetic above still decides.
    """
    by_series: dict[tuple[str, str], list[MovementEvent]] = defaultdict(list)
    for e in events:
        by_series[(e.polity_id, e.group)].append(e)
    if not by_series:
        return []

    bucket_rates, global_rate = bucket_up_rates(events)

    keys = sorted(by_series)
    candidate_pairs: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    if shortlist_k is None:
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                candidate_pairs.add((keys[i], keys[j]))
    else:
        skeys, mat = _series_mean_vectors(by_series)
        for i, k in enumerate(skeys):
            idx, _ = cosine_topk(mat[i], mat, shortlist_k + 1)
            for j in idx:
                j = int(j)
                if skeys[j] == k:
                    continue
                pair = tuple(sorted((k, skeys[j])))
                candidate_pairs.add(pair)  # type: ignore[arg-type]

    scored: list[tuple[tuple[str, str], tuple[str, str], int, int, float, float]] = []
    for ka, kb in sorted(candidate_pairs):
        if ka[0] == kb[0]:
            continue  # complement exclusion: same polity
        n = 0
        agree = 0
        null_ps: list[float] = []
        for ea in by_series[ka]:
            da = direction(ea.rate_per_decade)
            if da == "flat":
                continue
            for eb in by_series[kb]:
                db = direction(eb.rate_per_decade)
                if db == "flat":
                    continue
                if _overlap_years(ea, eb) <= 0:
                    continue
                n += 1
                if da == db:
                    agree += 1
                pa = bucket_rates.get(ea.origin_hash, global_rate)
                pb = bucket_rates.get(eb.origin_hash, global_rate)
                null_ps.append(pa * pb + (1.0 - pa) * (1.0 - pb))
        if n < min_overlap_pairs:
            continue
        p_null = sum(null_ps) / len(null_ps)
        p_value = _binom_sf(agree, n, p_null)
        scored.append((ka, kb, n, agree, p_null, p_value))

    fdr = _bh_fdr_pass([s[5] for s in scored], alpha)
    edges: list[ConnascenceEdge] = []
    for (ka, kb, n, agree, p_null, p_value), fdr_ok in zip(scored, fdr):
        if p_value >= alpha:
            continue
        if require_fdr and not fdr_ok:
            continue
        edges.append(
            ConnascenceEdge(
                src=f"series|{ka[0]}|{ka[1]}",
                dst=f"series|{kb[0]}|{kb[1]}",
                kind="co_variance",
                strength=agree / n,
                meta={
                    "n_pairs": n,
                    "n_agree": agree,
                    "p_null": round(p_null, 4),
                    "p_value": round(p_value, 6),
                    "fdr_pass": bool(fdr_ok),
                    "n_scored_pairs": len(scored),
                },
            )
        )
    return edges


@dataclass
class CovarianceCluster:
    cluster_id: str
    series: list[str]
    year_min: int
    year_max: int
    dominant_direction: str
    n_edges: int


def covariance_clusters(
    edges: Sequence[ConnascenceEdge],
    events: Sequence[MovementEvent],
) -> list[CovarianceCluster]:
    """Connected components over co-variance edges → shared-driver hypotheses."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    cov = [e for e in edges if e.kind == "co_variance"]
    for e in cov:
        ra, rb = find(e.src), find(e.dst)
        if ra != rb:
            parent[ra] = rb

    members: dict[str, list[str]] = defaultdict(list)
    for e in cov:
        for node in (e.src, e.dst):
            root = find(node)
            if node not in members[root]:
                members[root].append(node)

    by_series: dict[str, list[MovementEvent]] = defaultdict(list)
    for ev in events:
        by_series[f"series|{ev.polity_id}|{ev.group}"].append(ev)

    clusters: list[CovarianceCluster] = []
    for root in sorted(members):
        series = sorted(members[root])
        years: list[int] = []
        dirs: list[str] = []
        for s in series:
            for ev in by_series.get(s, []):
                d = direction(ev.rate_per_decade)
                if d == "flat":
                    continue
                years.extend((ev.year_from, ev.year_to))
                dirs.append(d)
        if not years:
            continue
        dom = max(("up", "down"), key=dirs.count) if dirs else "flat"
        cid = _claim_id("cluster", *series)
        clusters.append(
            CovarianceCluster(
                cluster_id=cid,
                series=series,
                year_min=min(years),
                year_max=max(years),
                dominant_direction=dom,
                n_edges=sum(1 for e in cov if find(e.src) == root),
            )
        )
    clusters.sort(key=lambda c: (-len(c.series), c.cluster_id))
    return clusters


# ---------------------------------------------------------------------------
# §2.3 partial settlement (one-hop, coefficient-capped)
# ---------------------------------------------------------------------------

PARTIAL_COEFFICIENT = 0.25


def apply_partial_settlement(
    pending: Sequence[Claim],
    settled: Sequence[Claim],
    edges: Sequence[ConnascenceEdge],
    store: TrustStore,
    *,
    coefficient: float = PARTIAL_COEFFICIENT,
) -> int:
    """Fractional bumps to pending claims' hypotheses from co-varying settlements.

    One-hop rule (§2.3): evidence flows only from *directly settled*
    claims (``settled=True``); pending claims are annotated, never marked
    settled, so partial evidence can never cascade. Weight per bump =
    edge strength × coefficient (≤ coefficient ≤ 0.25 by default), so
    partial evidence cannot outweigh direct settlement. Returns bump count.
    """
    if not 0.0 < coefficient <= 0.25:
        raise ValueError(f"coefficient must be in (0, 0.25]: {coefficient}")

    strength: dict[frozenset[str], float] = {}
    for e in edges:
        if e.kind == "co_variance":
            strength[frozenset({e.src, e.dst})] = e.strength

    settled_by_series: dict[str, list[Claim]] = defaultdict(list)
    for c in settled:
        if not c.settled or c.success is None:
            continue
        settled_by_series[f"series|{c.polity_id}|{c.group}"].append(c)

    n_bumps = 0
    for p in pending:
        if p.settled:
            continue  # only genuinely pending claims receive partial evidence
        p_series = f"series|{p.polity_id}|{p.group}"
        for other_series, sclaims in settled_by_series.items():
            s = strength.get(frozenset({p_series, other_series}))
            if s is None:
                continue
            for sc in sclaims:
                # Window relevance: the settled claim's transition overlaps.
                if min(p.year_to, sc.year_to) - max(p.year_from, sc.year_from) <= 0:
                    continue
                if sc.meta.get("policy") != p.meta.get("policy"):
                    continue
                # Positive co-movement: same predicted direction transfers.
                agree = sc.predicted == p.predicted
                partial_success = bool(sc.success) if agree else not bool(sc.success)
                w = s * coefficient
                store.bump(p.hypothesis_id, partial_success, weight=w)
                p.meta.setdefault("partial_bumps", []).append(
                    {
                        "from_claim": sc.claim_id,
                        "via": other_series,
                        "edge_strength": s,
                        "weight": round(w, 4),
                        "success": partial_success,
                    }
                )
                n_bumps += 1
    return n_bumps


# ---------------------------------------------------------------------------
# §2.4 TEMPORAL — event-window shock tagging + calm/shock calibration
# ---------------------------------------------------------------------------


def load_events(path: str | Path) -> list[Event]:
    out = []
    p = Path(path)
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(Event.model_validate(json.loads(line)))
    return out


def shock_events_for_window(
    year_from: int, year_to: int, events: Sequence[Event]
) -> list[str]:
    """Event ids whose window overlaps [year_from, year_to]."""
    hits = []
    for e in events:
        e_end = e.year_end if e.year_end is not None else e.year
        if year_from <= e_end and e.year <= year_to:
            hits.append(e.event_id)
    return hits


def tag_shock_claims(claims: Sequence[Claim], events: Sequence[Event]) -> int:
    """Stamp ``meta.shock`` / ``meta.shock_events`` on transition claims."""
    n = 0
    for c in claims:
        hits = shock_events_for_window(c.year_from, c.year_to, events)
        c.meta["shock"] = bool(hits)
        c.meta["shock_events"] = hits
        if hits:
            n += 1
    return n


def _event_touches_polity(
    event: Event, polity_id: str, migration_edges: Sequence[Any]
) -> bool:
    if polity_id in event.affected_polities:
        return True
    for me in migration_edges:
        if me.trigger_event_id == event.event_id and polity_id in (
            me.from_polity,
            me.to_polity,
        ):
            return True
    return False


def tag_shock_claims_contact(
    claims: Sequence[Claim],
    events: Sequence[Event],
    migration_edges: Sequence[Any] = (),
) -> int:
    """Polity-aware shock tagging (Phase 3 E5).

    Window-only tagging degenerates on forecast claims: a cut→target window
    spans decades, so *any* event anywhere tags *every* claim (calm n=0).
    Here an event tags a claim only if it also touches the claim's polity —
    via ``affected_polities`` or a migration edge it triggered (same contact
    rule as ``verify_event_attribution``).
    """
    n = 0
    for c in claims:
        hits = [
            eid
            for eid in shock_events_for_window(c.year_from, c.year_to, events)
            if _event_touches_polity(
                next(e for e in events if e.event_id == eid),
                c.polity_id,
                migration_edges,
            )
        ]
        c.meta["shock"] = bool(hits)
        c.meta["shock_events"] = hits
        if hits:
            n += 1
    return n


def split_calm_shock(claims: Sequence[Claim]) -> dict[str, list[Claim]]:
    out: dict[str, list[Claim]] = {"calm": [], "shock": []}
    for c in claims:
        out["shock" if c.meta.get("shock") else "calm"].append(c)
    return out


def write_edges_jsonl(edges: Sequence[ConnascenceEdge], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for e in edges:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")


def read_edges_jsonl(path: str | Path) -> list[ConnascenceEdge]:
    out = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(
                ConnascenceEdge(
                    src=d["src"],
                    dst=d["dst"],
                    kind=d["kind"],
                    strength=float(d["strength"]),
                    meta=d.get("meta") or {},
                    repr_version=d.get("repr_version", REPR_VERSION),
                )
            )
    return out
