#!/usr/bin/env python3
"""Sparsity→simulation bridge v2: nugget + shock widening, run end to end.

1. Estimate the per-group measurement-noise nugget from cross-source
   same-polity-year spreads on the observation desk.
2. Re-measure the anchor-drop calibration curves (linear/sqrt × nugget
   on/off) — the Phase 3 curve was inverted; the nugget should flatten it.
3. Score the historical lanes (Karpat LOO same-polity; Ottoman provinces
   cross-polity stress test) with nugget + shock windows.
4. Emit the bridge *product*: banded backfilled series on a 5-year grid for
   every desk+seed series, with per-polity shock widening.

Writes PHASE3_BRIDGE_V2.json + BRIDGE_V2_BACKFILL.jsonl.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.bridge import (  # noqa: E402
    backfill_series,
    estimate_nugget,
    fit_dynamics,
    settle_backfill,
    shock_windows_for_polity,
)
from conflux.connascence import load_events  # noqa: E402
from conflux.experiments import (  # noqa: E402
    anchor_drop_curves,
    bridge_block,
    build_desk_series,
)
from conflux.learning import TrustStore  # noqa: E402
from conflux.observations import load_observation_desk  # noqa: E402
from conflux.schema import Anchor, MigrationEdge  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data-validation-reports"
GROUPS = ("muslim", "christian", "jewish")

GRID_START, GRID_END, GRID_STEP = 1850, 2025, 5
SHOCK_SIGMA_MULTIPLIER = 2.0  # pre-declared, not tuned


def _load_jsonl(path: Path, model):
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(model.model_validate(json.loads(line)))
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    anchors = _load_jsonl(PROCESSED / "anchors.jsonl", Anchor)
    events = load_events(PROCESSED / "events.jsonl")
    edges = _load_jsonl(PROCESSED / "edges.jsonl", MigrationEdge)
    obs = load_observation_desk(PROCESSED, groups=GROUPS)
    desk = build_desk_series(PROCESSED, anchors, GROUPS)

    # ------------------------------------------------------------------
    # 1. Nugget estimation
    # ------------------------------------------------------------------
    nug = estimate_nugget(obs, groups=GROUPS)
    nuggets = nug["per_group"]
    print(f"🧂 nugget (share-points sd): pooled={nug['pooled']:.4f}")
    for g in GROUPS:
        print(f"     {g:10} σ_m={nuggets[g]:.4f}  (n_pairs={nug['n_pairs'][g]})")

    dynamics = fit_dynamics(anchors, groups=GROUPS, fit_start=1920)
    print(
        f"⚙️  dynamics: {dynamics.n_transitions} transitions, "
        f"rate_std={dynamics.rate_std:.4f}/decade"
    )

    # ------------------------------------------------------------------
    # 2. Anchor-drop curves, nugget on/off
    # ------------------------------------------------------------------
    curves = {
        "no_nugget": anchor_drop_curves(desk, dynamics, min_points=4),
        "nugget": anchor_drop_curves(desk, dynamics, min_points=4, nuggets=nuggets),
    }
    scoreboard = []
    for variant, by_shape in curves.items():
        for shape, blk in by_shape.items():
            covs = [
                b["coverage_observed"]
                for b in blk["by_gap"].values()
                if b.get("n", 0) >= 5
            ]
            miscal = sum(abs(c - 0.80) for c in covs) / len(covs) if covs else 9.9
            scoreboard.append((variant, shape, miscal, blk["coverage_overall"]))
            print(
                f"📈 curves {variant}/{shape}: overall cov={blk['coverage_overall']:.3f} "
                f"mean bucket |cov-0.80|={miscal:.3f}"
            )
            for label, b in blk["by_gap"].items():
                if b.get("n"):
                    print(
                        f"     gap {label:>6}: n={b['n']:4} cov={b['coverage_observed']:.3f} "
                        f"wilson={b['coverage_wilson95']} IS={b['mean_interval_score']:.3f}"
                    )
    scoreboard.sort(key=lambda t: t[2])
    best_variant, best_shape, best_miscal, _ = scoreboard[0]
    print(f"🏆 best curve config: {best_variant}/{best_shape} (|cov-0.80|={best_miscal:.3f})")

    # ------------------------------------------------------------------
    # 3. Historical lanes with nugget + shock windows
    # ------------------------------------------------------------------
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_phase3_bridge import (  # noqa: E402
        _karpat_holdouts,
        _ottoman_province_holdouts,
    )

    karpat = _karpat_holdouts()
    provinces = _ottoman_province_holdouts()
    karpat_support = [(a.year, float(a.shares["muslim"])) for a in karpat]
    empire_shocks = shock_windows_for_polity("ottoman_empire", events, edges)
    print(f"⚡ ottoman_empire shock windows on the event tape: {empire_shocks or 'none'}")

    lanes: dict = {}
    for variant, nugv in (("no_nugget", 0.0), ("nugget", nuggets["muslim"])):
        lanes[f"karpat_loo_{variant}"] = bridge_block(
            karpat, karpat_support, dynamics, loo=True, width_shape=best_shape,
            nugget=nugv, shock_windows=empire_shocks,
        ) | {"lane": "same_polity"}
        lanes[f"ottoman_provinces_{variant}"] = bridge_block(
            provinces, karpat_support, dynamics, loo=False, width_shape=best_shape,
            nugget=nugv, shock_windows=empire_shocks,
        ) | {"lane": "cross_polity_stress_test"}
    for name, blk in lanes.items():
        if blk.get("n"):
            print(
                f"🌉 {name}: n={blk['n']} cov={blk['coverage_observed']:.3f} "
                f"wilson={blk['coverage_wilson95']} IS={blk['mean_interval_score']:.3f}"
            )

    # Trust-ledger settlement for the v2 hypothesis (Karpat LOO, best config).
    store = TrustStore()
    for hold in karpat:
        support = [(y, s) for y, s in karpat_support if y != hold.year]
        est = backfill_series(
            support, dynamics, years=[hold.year], width_shape=best_shape,
            nugget=nuggets["muslim"], shock_windows=empire_shocks,
        )
        settle_backfill(est, [hold], store, hypothesis="dynamics:modern_fit_v2")
    post = store.get("dynamics:modern_fit_v2")
    print(f"📊 dynamics:modern_fit_v2 posterior: mean={post.mean:.3f} trials={post.trials}")

    # ------------------------------------------------------------------
    # 4. The product: banded backfill on a 5-year grid
    # ------------------------------------------------------------------
    grid = list(range(GRID_START, GRID_END + 1, GRID_STEP))
    n_rows = 0
    widths_by_era: dict[str, list[float]] = {"pre1920": [], "1920_1999": [], "2000plus": []}
    product_path = OUT / "BRIDGE_V2_BACKFILL.jsonl"
    with product_path.open("w", encoding="utf-8") as f:
        for (pid, group), pts in sorted(desk.items()):
            if len(pts) < 2:
                continue
            support = [(p.year, p.share) for p in pts]
            lo_year = max(GRID_START, (min(p.year for p in pts) // GRID_STEP) * GRID_STEP - 30)
            years = [y for y in grid if y >= lo_year]
            shocks = shock_windows_for_polity(pid, events, edges)
            ests = backfill_series(
                support, dynamics, years=years, width_shape=best_shape,
                nugget=nuggets.get(group, nug["pooled"]), shock_windows=shocks,
                shock_sigma_multiplier=SHOCK_SIGMA_MULTIPLIER,
            )
            for e in ests:
                f.write(
                    json.dumps(
                        {
                            "polity_id": pid,
                            "group": group,
                            "year": e.year,
                            "point": round(e.point, 5),
                            "lo": round(e.lo, 5),
                            "hi": round(e.hi, 5),
                            "coverage": e.coverage,
                            "nearest_anchor_gap": e.nearest_anchor_gap,
                            "n_anchors": len(support),
                            "shock_widened": bool(shocks),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                n_rows += 1
                w = e.hi - e.lo
                if e.year < 1920:
                    widths_by_era["pre1920"].append(w)
                elif e.year < 2000:
                    widths_by_era["1920_1999"].append(w)
                else:
                    widths_by_era["2000plus"].append(w)
    era_summary = {
        k: {"n": len(v), "mean_width": round(sum(v) / len(v), 4) if v else None}
        for k, v in widths_by_era.items()
    }
    print(f"📦 backfill product: {n_rows} banded rows → {product_path.name}")
    for era, s in era_summary.items():
        print(f"     {era:10} n={s['n']:6} mean width={s['mean_width']}")

    report = {
        "preregistered_params": {
            "shock_sigma_multiplier": SHOCK_SIGMA_MULTIPLIER,
            "grid": [GRID_START, GRID_END, GRID_STEP],
            "nugget_year_tolerance": 3,
        },
        "nugget": nug,
        "dynamics": {
            "fit_start": dynamics.fit_start,
            "n_transitions": dynamics.n_transitions,
            "rate_mean": dynamics.rate_mean,
            "rate_std": dynamics.rate_std,
        },
        "anchor_drop_curves": curves,
        "best_curve_config": {"variant": best_variant, "shape": best_shape, "mean_bucket_miscal": best_miscal},
        "historical_lanes": lanes,
        "shock_windows_ottoman_empire": empire_shocks,
        "posterior_v2": post.to_dict(),
        "product": {"path": product_path.name, "n_rows": n_rows, "width_by_era": era_summary},
    }
    (OUT / "PHASE3_BRIDGE_V2.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"💾 wrote {OUT / 'PHASE3_BRIDGE_V2.json'}")


if __name__ == "__main__":
    main()
