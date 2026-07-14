#!/usr/bin/env python3
"""Phase 2b — deterministic connascence layer over the evidence desk.

Implements STRATEGY_CONNASCENCE.md §5 steps 1–6:

  1. method registry + graded corroboration (independence discount),
     with a posterior diff against the unweighted Phase 2.5 ledger;
  2. definitional routing (definition_gap:* instead of source_trust:*);
  3. complement edges + co-variance discovery (complement exclusion,
     bucket-stratified null) + shuffle control;
  4. event-window shock tagging + calm/shock calibration split;
  5. conservation claims over migration edges;
  6. partial settlement demo (one-hop, coefficient-capped).

Outputs:
  data-validation-reports/PHASE2B_CONNASCENCE.json
  data-validation-reports/PHASE2B_EDGES.jsonl
  data-validation-reports/PHASE2B_CLUSTERS.json
"""

from __future__ import annotations

import copy
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux import movement, settlement  # noqa: E402
from conflux.connascence import (  # noqa: E402
    REPR_VERSION,
    bucket_up_rates,
    complement_edges,
    conservation_edges,
    covariance_clusters,
    covariance_edges,
    desk_movement_events,
    load_events,
    make_conservation_claims,
    route_definitional_claims,
    settle_conservation_claims,
    settle_corroboration_claims_weighted,
    split_calm_shock,
    tag_shock_claims,
    write_edges_jsonl,
)
from conflux.learning import TrustStore  # noqa: E402
from conflux.observations import (  # noqa: E402
    load_observation_desk,
    make_observation_claims,
)
from conflux.schema import Anchor, MigrationEdge  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data-validation-reports"


def _load_jsonl(path: Path, model):
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(model.model_validate(json.loads(line)))
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    obs = load_observation_desk(PROCESSED)
    anchors = _load_jsonl(PROCESSED / "anchors.jsonl", Anchor)
    mig_edges = _load_jsonl(PROCESSED / "edges.jsonl", MigrationEdge)
    events = load_events(PROCESSED / "events.jsonl")
    groups = ["muslim", "christian", "jewish"]

    # ---- 1+2. weighted corroboration ledger with definitional routing ------
    baseline = TrustStore()
    settlement.settle_corroboration_claims(
        make_observation_claims(obs, max_gap_years=30), baseline
    )

    store = TrustStore()
    corr_claims = make_observation_claims(obs, max_gap_years=30)
    n_routed = route_definitional_claims(corr_claims)
    n_corr = settle_corroboration_claims_weighted(corr_claims, store)
    print(f"corroboration: {n_corr} settled ({n_routed} rerouted to definition_gap:*)")

    posterior_diff = {}
    for hid in sorted(set(baseline.posteriors) | set(store.posteriors)):
        b, w = baseline.get(hid), store.get(hid)
        posterior_diff[hid] = {
            "unweighted_mean": round(b.mean, 4),
            "weighted_mean": round(w.mean, 4),
            "delta": round(w.mean - b.mean, 4),
            "trials_unweighted": b.trials,
            "trials_weighted": w.trials,
        }
        if b.trials or w.trials:
            print(
                f"  {hid:<60} {b.mean:.3f} -> {w.mean:.3f} "
                f"(Δ{w.mean - b.mean:+.3f})"
            )

    # ---- 3. movement events, complement + co-variance edges ----------------
    # Merged anchor+desk timeline: anchor-only series are 5 aligned points,
    # which caps overlap pairs below the admission floor (see
    # desk_movement_events docstring).
    all_events = desk_movement_events(anchors, obs, groups=groups)
    comp_edges = complement_edges(obs)
    cons_edges = conservation_edges(mig_edges)
    # Strict tier: BH-FDR survivors — the only tier partial settlement may use.
    cov_edges = covariance_edges(all_events, min_overlap_pairs=3, alpha=0.05)
    # Hypothesis tier: raw-α edges (fdr_pass flag in meta) — clusters/REVIEW/LLM.
    cov_hypo = covariance_edges(
        all_events, min_overlap_pairs=3, alpha=0.05, require_fdr=False
    )
    _, global_up = bucket_up_rates(all_events)
    print(
        f"edges: {len(comp_edges)} complement, {len(cons_edges)} conservation, "
        f"{len(cov_edges)} co-variance strict + {len(cov_hypo)} hypothesis-tier "
        f"(global P(up|moving)={global_up:.3f})"
    )

    # Shuffle control (§5 null-model floor): permuting outcomes within series
    # should collapse discovery to ~0 edges.
    rng = random.Random(42)
    shuffled = []
    by_series = defaultdict(list)
    for e in all_events:
        by_series[(e.polity_id, e.group)].append(e)
    for series in by_series.values():
        rates = [e.rate_per_decade for e in series]
        rng.shuffle(rates)
        for e, r in zip(series, rates):
            shuffled.append(
                movement.MovementEvent(
                    polity_id=e.polity_id, group=e.group,
                    year_from=e.year_from, year_to=e.year_to,
                    gap_years=e.gap_years, share_from=e.share_from,
                    share_to=e.share_to, delta=e.delta,
                    rate_per_decade=r, confidence=e.confidence,
                    origin_hash=e.origin_hash,
                    prior_rate=e.prior_rate, prior_vol=e.prior_vol,
                )
            )
    cov_shuffled = covariance_edges(shuffled, min_overlap_pairs=3, alpha=0.05)
    print(
        f"shuffle control (strict tier): {len(cov_shuffled)} edges "
        f"(vs {len(cov_edges)} real)"
    )

    # Clusters come from the hypothesis tier — they feed the REVIEW queue and
    # the LLM event-attribution job, never the ledger.
    clusters = covariance_clusters(cov_hypo, all_events)
    print(f"clusters: {len(clusters)}")
    for c in clusters[:8]:
        print(
            f"  [{c.year_min}-{c.year_max}] {c.dominant_direction:<5} "
            f"n={len(c.series)}: {', '.join(s.split('|',1)[1] for s in c.series[:6])}"
            + (" …" if len(c.series) > 6 else "")
        )

    # ---- 4. policy tape with shock tagging + calm/shock calibration --------
    catalog = movement.build_catalog(anchors, groups=groups)
    pol_claims = settlement.make_policy_claims(catalog, cut_year=1975, min_bucket_n=2)
    n_shock = tag_shock_claims(pol_claims, events)
    settlement.settle_policy_claims(pol_claims, catalog, store)
    halves = split_calm_shock(pol_claims)
    calm_shock = {}
    for label, cl in halves.items():
        by_policy = defaultdict(list)
        for c in cl:
            by_policy[c.meta.get("policy")].append(c)
        calm_shock[label] = {
            pol: {
                "n": len(cs),
                "hit_rate": round(sum(1 for c in cs if c.success) / len(cs), 4),
                "brier": round(settlement.brier_score(cs), 4),
            }
            for pol, cs in sorted(by_policy.items())
        }
    print(f"policy tape: {len(pol_claims)} claims, {n_shock} in shock windows")
    for label in ("calm", "shock"):
        for pol, row in calm_shock[label].items():
            print(f"  {label:<6} {pol:<12} n={row['n']:<4} hit={row['hit_rate']:.3f}")

    # ---- 5. conservation claims ---------------------------------------------
    cons_claims = make_conservation_claims(anchors, mig_edges)
    n_cons = settle_conservation_claims(cons_claims, store)
    n_abstained = len(mig_edges) - len(cons_claims)
    print(f"conservation: {n_cons} settled, {n_abstained} abstained (missing brackets)")
    for c in cons_claims:
        print(
            f"  {c.meta['edge_id']:<38} loss={c.meta['origin_loss']:>12,.0f} "
            f"gain={c.meta['dest_gain']:>12,.0f} "
            f"{'OK' if c.success else 'VIOLATED'}"
        )

    # ---- 6. partial settlement demo -----------------------------------------
    # Post-1975 tape replay: settle pre-1990 outcomes fully, treat the rest as
    # pending, and measure how much one-hop partial evidence they receive.
    demo_store = TrustStore()
    demo_claims = settlement.make_policy_claims(catalog, cut_year=1975, min_bucket_n=2)
    early = [c for c in demo_claims if c.year_to <= 1990]
    pending = [c for c in demo_claims if c.year_to > 1990]
    settlement.settle_policy_claims(early, catalog, demo_store)
    from conflux.connascence import apply_partial_settlement  # noqa: E402

    n_bumps = apply_partial_settlement(pending, early, cov_edges, demo_store)
    print(
        f"partial settlement demo: {len(early)} settled, {len(pending)} pending, "
        f"{n_bumps} fractional bumps"
    )

    # ---- outputs -------------------------------------------------------------
    # cov_hypo ⊇ cov_edges; fdr_pass distinguishes the tiers in the file.
    edges_all = comp_edges + cons_edges + cov_hypo
    write_edges_jsonl(edges_all, OUT / "PHASE2B_EDGES.jsonl")
    (OUT / "PHASE2B_CLUSTERS.json").write_text(
        json.dumps(
            {
                "repr_version": REPR_VERSION,
                "clusters": [
                    {
                        "cluster_id": c.cluster_id,
                        "series": c.series,
                        "year_min": c.year_min,
                        "year_max": c.year_max,
                        "dominant_direction": c.dominant_direction,
                        "n_edges": c.n_edges,
                    }
                    for c in clusters
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    all_claims = corr_claims + pol_claims + cons_claims
    payload = {
        "repr_version": REPR_VERSION,
        "n_observations": len(obs),
        "corroboration": {
            "n_claims": n_corr,
            "n_definitional_rerouted": n_routed,
            "posterior_diff": posterior_diff,
        },
        "edges": {
            "complement": len(comp_edges),
            "conservation": len(cons_edges),
            "co_variance_strict_fdr": len(cov_edges),
            "co_variance_hypothesis_tier": len(cov_hypo),
            "co_variance_shuffle_control": len(cov_shuffled),
        },
        "clusters": len(clusters),
        "policy": {"n_claims": len(pol_claims), "n_shock": n_shock, "calm_shock": calm_shock},
        "conservation_claims": [
            {
                "edge_id": c.meta["edge_id"],
                "success": c.success,
                "origin_loss": c.meta["origin_loss"],
                "dest_gain": c.meta["dest_gain"],
            }
            for c in cons_claims
        ],
        "partial_settlement_demo": {
            "n_settled": len(early),
            "n_pending": len(pending),
            "n_bumps": n_bumps,
        },
        "brier_all": settlement.brier_score(all_claims),
    }
    (OUT / "PHASE2B_CONNASCENCE.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    settlement.write_trust_report(store, all_claims, OUT / "PHASE2B_TRUST.json")
    print(f"wrote {OUT / 'PHASE2B_CONNASCENCE.json'}")
    print(f"wrote {OUT / 'PHASE2B_EDGES.jsonl'} ({len(edges_all)} edges)")
    print(f"wrote {OUT / 'PHASE2B_CLUSTERS.json'}")
    print(f"wrote {OUT / 'PHASE2B_TRUST.json'}")


if __name__ == "__main__":
    main()
