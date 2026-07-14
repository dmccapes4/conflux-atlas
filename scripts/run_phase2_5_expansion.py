#!/usr/bin/env python3
"""Phase 2.5 — expanded source ledger + PortalGC governance experiment.

1. Assemble the multi-source observation desk (hand seeds excluded).
2. Corroboration claims with level-scaled tolerance → source_trust:* ledger.
3. Policy tape on ALL anchor polities (1975 cut) → policy:* posteriors.
4. Export the evidence graph and run the PortalGC ρ×τ sweep.
5. Cross-tab KEEP/EVICT/REVIEW against independently learned source trust.
6. Robustness: rerun the corroboration ledger on the KEEP-only subgraph.

Outputs:
  data-validation-reports/PHASE2_5_TRUST.json
  data-validation-reports/PHASE2_5_PORTAL_GRAPH.jsonl
  data-validation-reports/PHASE2_5_PORTALGC.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux import movement, settlement  # noqa: E402
from conflux.learning import TrustStore  # noqa: E402
from conflux.observations import (  # noqa: E402
    load_observation_desk,
    make_observation_claims,
)
from conflux.portal_graph import (  # noqa: E402
    build_portal_nodes,
    classify_portal,
    sweep_portal,
    write_portal_jsonl,
)
from conflux.schema import Anchor  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data-validation-reports"


def _load_all_anchors() -> list[Anchor]:
    anchors = []
    with (PROCESSED / "anchors.jsonl").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                anchors.append(Anchor.model_validate(json.loads(line)))
    return anchors


def main() -> None:
    OUT.mkdir(exist_ok=True)

    # --- 1. observation desk -------------------------------------------------
    obs = load_observation_desk(PROCESSED)
    sources = sorted({o.source_id for o in obs})
    print(f"observation desk: {len(obs)} observations from {len(sources)} sources")
    print(f"  sources: {sources}")

    # --- 2. corroboration ledger ---------------------------------------------
    store = TrustStore()
    corr_claims = make_observation_claims(obs, max_gap_years=30)
    n_corr = settlement.settle_corroboration_claims(corr_claims, store)
    print(f"corroboration: {n_corr} settled claims")

    # --- 3. policy tape on all polities --------------------------------------
    anchors = _load_all_anchors()
    all_polities = sorted({a.polity_id for a in anchors})
    catalog = movement.build_catalog(anchors, groups=["muslim", "christian", "jewish"])
    pol_claims = settlement.make_policy_claims(catalog, cut_year=1975, min_bucket_n=2)
    n_pol = settlement.settle_policy_claims(pol_claims, catalog, store)
    print(
        f"policy tape: {len(all_polities)} polities, {len(catalog)} transitions, "
        f"{n_pol} settled claims"
    )

    all_claims = corr_claims + pol_claims
    settlement.write_trust_report(store, all_claims, OUT / "PHASE2_5_TRUST.json")
    for row in store.summary():
        if row["trials"]:
            print(
                f"  {row['hypothesis_id']:<55} mean={row['mean']:.3f} "
                f"trials={row['trials']}"
            )

    # --- 4. PortalGC export + sweep -------------------------------------------
    nodes = build_portal_nodes(obs, corr_claims, store)
    write_portal_jsonl(nodes, OUT / "PHASE2_5_PORTAL_GRAPH.jsonl")
    print(f"portal graph: {len(nodes)} nodes")

    sweep = sweep_portal(nodes)
    stable = [s for s in sweep if s["stable"]]
    print("sweep (rho, tau, evict%, lb-evictions, stable):")
    for s in sweep:
        print(
            f"  rho={s['rho']:>5} tau={s['tau']:>4} evict={s['evict_pct']:.1%} "
            f"lb_evict={s['load_bearing_evictions']} "
            f"{'STABLE' if s['stable'] else ''}"
        )
    chosen = (stable or sweep)[len(stable or sweep) // 2]  # middle of stable band
    rho, tau = chosen["rho"], chosen["tau"]
    print(f"chosen config: rho={rho} tau={tau}")
    cls = classify_portal(nodes, rho=rho, tau=tau)

    # --- 5. cross-tab: classification vs source trust -------------------------
    # For each source, distribution of its observations' classifications.
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for n in nodes:
        if n["type"] != "observation":
            continue
        src = n["metadata"]["source_id"]
        by_source[src][cls[n["id"]]["classification"]] += 1
    crosstab = {}
    for src in sources:
        counts = dict(by_source[src])
        total = sum(counts.values())
        post = store.get(f"source_trust:{src}")
        crosstab[src] = {
            "counts": counts,
            "keep_pct": counts.get("KEEP", 0) / total if total else None,
            "trust_mean": post.mean if post.trials else None,
            "trust_trials": post.trials,
        }
        print(
            f"  {src:<40} keep={crosstab[src]['keep_pct'] if total else '—'} "
            f"trust={post.mean if post.trials else '—'}"
        )

    # --- 6. robustness: trust ledger on KEEP-only subgraph --------------------
    keep_ids = {
        nid for nid, rec in cls.items() if rec["classification"] == "KEEP"
    }
    keep_obs = [o for o in obs if o.obs_id in keep_ids]
    keep_store = TrustStore()
    keep_claims = make_observation_claims(keep_obs, max_gap_years=30)
    settlement.settle_corroboration_claims(keep_claims, keep_store)
    keep_posteriors = {
        row["hypothesis_id"]: {"mean": row["mean"], "trials": row["trials"]}
        for row in keep_store.summary()
        if row["trials"]
    }
    print(
        f"KEEP subgraph: {len(keep_obs)}/{len(obs)} observations, "
        f"{len(keep_claims)} claims"
    )

    payload = {
        "n_observations": len(obs),
        "n_sources": len(sources),
        "sources": sources,
        "n_corroboration_claims": n_corr,
        "n_policy_claims": n_pol,
        "sweep": sweep,
        "chosen": {"rho": rho, "tau": tau},
        "classification_counts": {
            c: sum(1 for r in cls.values() if r["classification"] == c)
            for c in ("KEEP", "EVICT", "REVIEW")
        },
        "source_crosstab": crosstab,
        "keep_subgraph": {
            "n_observations": len(keep_obs),
            "n_claims": len(keep_claims),
            "posteriors": keep_posteriors,
        },
        "classifications": {
            nid: rec["classification"] for nid, rec in sorted(cls.items())
        },
    }
    (OUT / "PHASE2_5_PORTALGC.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / 'PHASE2_5_TRUST.json'}")
    print(f"wrote {OUT / 'PHASE2_5_PORTALGC.json'}")


if __name__ == "__main__":
    main()
