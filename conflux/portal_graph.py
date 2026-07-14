"""PortalGC (provenance-engine) bridge — evidence-graph governance experiment.

Maps the observation desk + trust ledger onto a Portal graph and runs the
Lorenz KEEP / EVICT / REVIEW classification. STRATEGY v0.2 §8.C rules
apply: this is a *report-only governance experiment* beside the path —
classifications never feed back into confidence or trust math, and no
processed data is ever deleted.

Design notes (see docs/REPORT_PHASE2_5_SOURCES_PORTALGC.md):

  - Nodes = share observations + source hub nodes.
  - Edges: SOURCE (obs → its source hub), CO_OCCURRENCE (same
    polity-year), CO_VARIANCE (corroboration pairs; strength = settled
    agreement), TEMPORAL (consecutive obs on a polity×group timeline).
  - Temporal-vitality trap: PortalGC decays z₀ by calendar recency,
    which would auto-evict pre-1920 history for being old. We therefore
    synthesize ``updated_at`` from *evidential* status (corroborated →
    fresh, contradicted → stale, unsettled → old), never from the
    observation year.
  - load_bearing: sole-source timelines and trusted source hubs are
    never auto-evicted (escalated to REVIEW by the engine).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from .learning import Claim, TrustStore
from .observations import ShareObservation

# Synthetic vitality ages (hours) — evidential freshness, not calendar age.
_AGE_CORROBORATED_H = 24.0
_AGE_CONTRADICTED_H = 24.0 * 365
_AGE_UNSETTLED_H = 24.0 * 365 * 10


def _importance(confidence: float) -> str:
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.45:
        return "medium"
    return "low"


def _iso_age(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def build_portal_nodes(
    observations: Sequence[ShareObservation],
    claims: Sequence[Claim],
    store: TrustStore,
) -> list[dict[str, Any]]:
    """Assemble provenance-engine node dicts from the evidence desk."""
    obs_by_id = {o.obs_id: o for o in observations}

    # Corroboration status per obs_id (as claimer) — drives synthetic vitality.
    settled_status: dict[str, bool] = {}
    # CO_VARIANCE pairs: (claiming obs_id, settling obs_id, success)
    covariance: list[tuple[str, str, bool]] = []
    for c in claims:
        if not c.settled or c.success is None:
            continue
        src = str(c.meta.get("claiming_source", ""))
        settler = str(c.meta.get("settling_source", ""))
        a_id = f"{src}|{c.polity_id}|{c.group}|{c.year_from}"
        b_id = f"{settler}|{c.polity_id}|{c.group}|{c.year_to}"
        if a_id in obs_by_id:
            # a later success should not be erased by an earlier failure
            settled_status[a_id] = settled_status.get(a_id, False) or bool(c.success)
        if a_id in obs_by_id and b_id in obs_by_id:
            covariance.append((a_id, b_id, bool(c.success)))

    # Sole-source timelines are load-bearing.
    sources_per_pg: dict[tuple[str, str], set[str]] = defaultdict(set)
    for o in observations:
        sources_per_pg[(o.polity_id, o.group)].add(o.source_id)

    # Group observations for CO_OCCURRENCE / TEMPORAL edges.
    by_polity_year: dict[tuple[str, int], list[ShareObservation]] = defaultdict(list)
    by_pg: dict[tuple[str, str], list[ShareObservation]] = defaultdict(list)
    for o in observations:
        by_polity_year[(o.polity_id, o.year)].append(o)
        by_pg[(o.polity_id, o.group)].append(o)

    nodes: list[dict[str, Any]] = []
    for o in observations:
        edges: list[dict[str, Any]] = [
            {"target": f"source:{o.source_id}", "type": "SOURCE", "strength": float(o.confidence)}
        ]
        for peer in by_polity_year[(o.polity_id, o.year)]:
            if peer.obs_id != o.obs_id:
                edges.append(
                    {"target": peer.obs_id, "type": "CO_OCCURRENCE", "strength": 0.6}
                )
        series = sorted(by_pg[(o.polity_id, o.group)], key=lambda x: (x.year, x.source_id))
        idx = next(i for i, x in enumerate(series) if x.obs_id == o.obs_id)
        if idx + 1 < len(series):
            edges.append(
                {"target": series[idx + 1].obs_id, "type": "TEMPORAL", "strength": 0.5}
            )

        status = settled_status.get(o.obs_id)
        if status is True:
            age = _AGE_CORROBORATED_H
        elif status is False:
            age = _AGE_CONTRADICTED_H
        else:
            age = _AGE_UNSETTLED_H

        nodes.append(
            {
                "id": o.obs_id,
                "type": "observation",
                "edges": edges,
                "importance": _importance(o.confidence),
                "load_bearing": len(sources_per_pg[(o.polity_id, o.group)]) == 1,
                "updated_at": _iso_age(age),
                "metadata": {
                    "polity_id": o.polity_id,
                    "group": o.group,
                    "year": o.year,
                    "share": o.share,
                    "confidence": o.confidence,
                    "source_id": o.source_id,
                },
            }
        )

    for a_id, b_id, success in covariance:
        node = next(n for n in nodes if n["id"] == a_id)
        node["edges"].append(
            {
                "target": b_id,
                "type": "CO_VARIANCE",
                "strength": 1.0 if success else 0.2,
            }
        )

    # Source hub nodes: importance from trust posterior when settled trials
    # exist; trusted sources are load-bearing (governance may flag, not evict).
    for src in sorted({o.source_id for o in observations}):
        post = store.get(f"source_trust:{src}")
        conf = post.mean if post.trials > 0 else 0.5
        nodes.append(
            {
                "id": f"source:{src}",
                "type": "source",
                "edges": [],
                "importance": _importance(conf),
                "load_bearing": post.trials > 0 and post.mean >= 0.5,
                "updated_at": _iso_age(
                    _AGE_CORROBORATED_H if post.trials > 0 else _AGE_UNSETTLED_H
                ),
                "metadata": {
                    "source_id": src,
                    "trust_mean": post.mean,
                    "trust_trials": post.trials,
                },
            }
        )
    return nodes


def write_portal_jsonl(nodes: Sequence[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for n in nodes:
            f.write(json.dumps(n, ensure_ascii=False) + "\n")


def classify_portal(
    nodes: Sequence[dict[str, Any]], *, rho: float = 28.0, tau: float = 2.0
) -> dict[str, dict[str, Any]]:
    """Run the Portal pipeline; return obs_id → classification record."""
    from provenance_engine import (
        build_graph,
        classify_node,
        integrate_portal,
        normalize_and_scale,
    )

    graph = build_graph(list(nodes))
    scaled = normalize_and_scale(graph)
    out: dict[str, dict[str, Any]] = {}
    for rec in scaled:
        traj = integrate_portal(rec["x0"], rec["y0"], rec["z0"], rho=rho)
        result = classify_node(traj, tau=tau, load_bearing=bool(rec.get("load_bearing")))
        out[rec["id"]] = {
            "classification": result["classification"],
            "mean_x": result.get("mean_x"),
            "load_bearing": bool(rec.get("load_bearing")),
        }
    return out


def sweep_portal(
    nodes: Sequence[dict[str, Any]],
    *,
    rhos: Sequence[float] = (24.0, 28.0, 32.0),
    taus: Sequence[float] = (1.5, 2.0, 3.0),
) -> list[dict[str, Any]]:
    """ρ × τ grid; per combo report class counts + load-bearing evictions.

    Governance-stable per provenance-engine convention: eviction < 30%
    and zero load-bearing evictions.
    """
    results: list[dict[str, Any]] = []
    lb_ids = {n["id"] for n in nodes if n.get("load_bearing")}
    for rho in rhos:
        for tau in taus:
            cls = classify_portal(nodes, rho=rho, tau=tau)
            counts = {"KEEP": 0, "EVICT": 0, "REVIEW": 0}
            lb_evictions = 0
            for nid, rec in cls.items():
                counts[rec["classification"]] = counts.get(rec["classification"], 0) + 1
                if rec["classification"] == "EVICT" and nid in lb_ids:
                    lb_evictions += 1
            n = len(cls)
            evict_pct = counts.get("EVICT", 0) / n if n else 0.0
            results.append(
                {
                    "rho": rho,
                    "tau": tau,
                    "counts": counts,
                    "evict_pct": evict_pct,
                    "load_bearing_evictions": lb_evictions,
                    "stable": evict_pct < 0.30 and lb_evictions == 0,
                }
            )
    return results
