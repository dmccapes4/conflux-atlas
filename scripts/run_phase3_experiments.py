#!/usr/bin/env python3
"""Phase 3 expanded experimentation runner (PHASE3_EXPERIMENT_PLAN.md).

Writes:
  PHASE3_CUT_SWEEP.json       E1/E2/E5/E7 — cuts × {anchor, desk} tapes
  PHASE3_WIDTH_ABLATION.json  E3 — selection on even-hash series, one
                              confirmatory shot on odd-hash series @1975
  PHASE3_CANDIDATES.json      E4 — analog + ensemble vs frozen success rule
  PHASE3_BRIDGE_CURVES.json   E6 — disaggregated bridge + anchor-drop curves

Selection/confirmation amendment (recorded in the plan changelog): the plan
proposed selecting on cut-1950/1990 tapes, but their target years overlap the
1975 tape's targets (same realized 2005–2020 rows) — cross-cut selection
would leak outcomes into the confirmatory set. Instead we split by *series*:
sha1(polity|group) even → selection, odd → confirmatory. Outcome rows are
disjoint by construction.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.backtest import PREREGISTRATION  # noqa: E402
from conflux.bridge import fit_dynamics  # noqa: E402
from conflux.connascence import load_events  # noqa: E402
from conflux.experiments import (  # noqa: E402
    BASELINE_POLICIES,
    analog_claims,
    anchor_drop_curves,
    bridge_block,
    build_anchor_series,
    build_desk_series,
    climatology_claims,
    ensemble_claims,
    fit_conformal_lambda,
    fit_ensemble_weights,
    fit_series_dynamics,
    make_series_claims,
    paired_comparison,
    permutation_control,
    settle_band_claims,
    tape_report,
)
from conflux.learning import TrustStore  # noqa: E402
from conflux.schema import Anchor, MigrationEdge  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data-validation-reports"

SWEEP_CUTS = (1950, 1975, 1990, 2000, 2010)
GROUPS = ("muslim", "christian", "jewish")
CONFIRMATORY_CUT = int(PREREGISTRATION["cut_year"])  # 1975 — untouched


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


def _series_half(series, parity: int):
    """Deterministic series split: sha1(polity|group) % 2 == parity."""
    out = {}
    for key, pts in series.items():
        h = int(hashlib.sha1(f"{key[0]}|{key[1]}".encode()).hexdigest(), 16)
        if h % 2 == parity:
            out[key] = pts
    return out


def _run_tape(series, *, cut, width_model="w0", tape="", events=(), edges=(),
              conformal_lambdas=None, with_climatology=True):
    claims = make_series_claims(
        series, cut_year=cut, width_model=width_model, tape=tape,
        conformal_lambdas=conformal_lambdas,
    )
    if with_climatology:
        claims += climatology_claims(series, cut_year=cut, tape=tape)
    store = TrustStore()
    settle_band_claims(claims, store)
    policies = list(BASELINE_POLICIES) + (["climatology"] if with_climatology else [])
    rep = tape_report(claims, policies=policies, events=events, migration_edges=edges)
    rep["cut_year"] = cut
    rep["width_model"] = width_model
    rep["tape"] = tape
    return rep, claims


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"💾 wrote {path}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    anchors = _load_jsonl(PROCESSED / "anchors.jsonl", Anchor)
    events = load_events(PROCESSED / "events.jsonl")
    edges = _load_jsonl(PROCESSED / "edges.jsonl", MigrationEdge)

    anchor_series = build_anchor_series(anchors, GROUPS)
    desk_series = build_desk_series(PROCESSED, anchors, GROUPS)
    print(f"📥 series: {len(anchor_series)} anchor-only, {len(desk_series)} desk-augmented")

    # ------------------------------------------------------------------
    # E1 + E2 + E5 + E7 — cut sweep on both tapes
    # ------------------------------------------------------------------
    sweep: dict = {"label": "exploratory (1975 tape previously seen)", "tapes": {}}
    for name, series in (("anchors", anchor_series), ("desk", desk_series)):
        for cut in SWEEP_CUTS:
            rep, claims = _run_tape(
                series, cut=cut, tape=f"{name}@{cut}", events=events, edges=edges
            )
            settled = [c for c in claims if c.settled and c.meta.get("policy") == "persistence"]
            rep["permutation_control_persistence"] = permutation_control(settled)
            sweep["tapes"][f"{name}@{cut}"] = rep
            pers = rep["policies"]["persistence"]
            ar1 = rep["policies"]["ar1"]
            print(
                f"🧮 E1 {name}@{cut}: persistence n={pers.get('n', 0)} "
                f"cov={pers.get('coverage_observed', 0):.3f} "
                f"IS={pers.get('mean_interval_score', 0):.3f} | ar1 n={ar1.get('n', 0)} | "
                f"calm/shock={pers.get('calm', {}).get('n', 0)}/{pers.get('shock', {}).get('n', 0)}"
            )
    _write(OUT / "PHASE3_CUT_SWEEP.json", sweep)

    # ------------------------------------------------------------------
    # E3 — width ablation: selection on even half, confirm on odd half @1975
    # ------------------------------------------------------------------
    sel_series = _series_half(desk_series, 0)
    conf_series = _series_half(desk_series, 1)
    print(f"🧪 E3 split: {len(sel_series)} selection series, {len(conf_series)} confirmatory")

    dyn_sel = fit_series_dynamics(sel_series, cut_year=CONFIRMATORY_CUT)
    lambdas_sel = {
        p: fit_conformal_lambda(sel_series, cut_year=CONFIRMATORY_CUT, policy=p)
        for p in BASELINE_POLICIES
    }
    ablation: dict = {
        "design": "series-split selection (even sha1 half); confirmatory = odd half @1975",
        "conformal_lambdas_selection": lambdas_sel,
        "selection": {},
    }
    scoreboard = []
    for wm in ("w0", "w1", "w2", "w3"):
        per_cut = {}
        for cut in (CONFIRMATORY_CUT, 1990):
            dyn = fit_series_dynamics(sel_series, cut_year=cut) if wm == "w2" else dyn_sel
            rep, _ = _run_tape(
                sel_series, cut=cut, width_model=wm, tape=f"sel-{wm}@{cut}",
                events=events, edges=edges,
                conformal_lambdas=lambdas_sel, with_climatology=False,
            )
            per_cut[str(cut)] = rep["policies"]["persistence"]
        ablation["selection"][wm] = per_cut
        covs = [b.get("coverage_observed", 0.0) for b in per_cut.values() if b.get("n")]
        iss = [b.get("mean_interval_score", 9.9) for b in per_cut.values() if b.get("n")]
        if covs:
            miscal = sum(abs(c - 0.80) for c in covs) / len(covs)
            scoreboard.append((wm, miscal, sum(iss) / len(iss)))
            print(f"🧪 E3 selection {wm}: mean|cov-0.80|={miscal:.3f}  mean IS={sum(iss)/len(iss):.3f}")
    scoreboard.sort(key=lambda t: (round(t[1], 3), t[2]))
    winner = scoreboard[0][0]
    ablation["frozen_winner"] = winner
    ablation["selection_rule"] = "min mean |coverage-0.80| across cuts {1975, 1990}, tie-break mean IS"

    # One confirmatory shot: frozen winner on the odd half at 1975.
    dyn_conf = fit_series_dynamics(conf_series, cut_year=CONFIRMATORY_CUT) if winner == "w2" else None
    rep_conf, conf_claims = _run_tape(
        conf_series, cut=CONFIRMATORY_CUT, width_model=winner,
        tape=f"confirmatory-{winner}@1975", events=events, edges=edges,
        conformal_lambdas=lambdas_sel, with_climatology=True,
    )
    ablation["confirmatory"] = rep_conf
    # w0 reference on the same confirmatory half (context, labeled as such).
    rep_w0, _ = _run_tape(
        conf_series, cut=CONFIRMATORY_CUT, width_model="w0",
        tape="confirmatory-ref-w0@1975", events=events, edges=edges,
        with_climatology=False,
    )
    ablation["confirmatory_reference_w0"] = rep_w0["policies"]
    pers = rep_conf["policies"]["persistence"]
    print(
        f"🎯 E3 confirmatory ({winner}) persistence: n={pers.get('n', 0)} "
        f"cov={pers.get('coverage_observed', 0):.3f} wilson={pers.get('coverage_wilson95')} "
        f"IS={pers.get('mean_interval_score', 0):.3f}"
    )
    _write(OUT / "PHASE3_WIDTH_ABLATION.json", ablation)

    # ------------------------------------------------------------------
    # E4 — candidates: fit on even half, confirm on odd half @1975
    # ------------------------------------------------------------------
    sel_claims = make_series_claims(
        sel_series, cut_year=CONFIRMATORY_CUT, width_model=winner,
        conformal_lambdas=lambdas_sel, dynamics=dyn_sel, tape="e4-sel",
    )
    store = TrustStore()
    settle_band_claims(sel_claims, store)
    weights = fit_ensemble_weights(sel_claims)
    print(f"🧪 E4 ensemble weights (persistence, reversion, ar1) = {weights}")

    cand_claims = []
    cand_claims += analog_claims(conf_series, cut_year=CONFIRMATORY_CUT, tape="e4-conf")
    cand_claims += ensemble_claims(
        conf_series, cut_year=CONFIRMATORY_CUT, weights=weights, width_model=winner,
        conformal_lambdas=lambdas_sel, dynamics=dyn_conf, tape="e4-conf",
    )
    base_claims = make_series_claims(
        conf_series, cut_year=CONFIRMATORY_CUT, width_model=winner,
        conformal_lambdas=lambdas_sel, dynamics=dyn_conf, tape="e4-conf",
    )
    clim = climatology_claims(conf_series, cut_year=CONFIRMATORY_CUT, tape="e4-conf")
    all_claims = cand_claims + base_claims + clim
    store2 = TrustStore()
    settle_band_claims(all_claims, store2)
    rep4 = tape_report(
        all_claims,
        policies=list(BASELINE_POLICIES) + ["climatology", "analog", "ensemble"],
        events=events, migration_edges=edges,
    )

    baseline_is = {
        p: rep4["policies"][p]["mean_interval_score"]
        for p in BASELINE_POLICIES
        if rep4["policies"][p].get("n")
    }
    verdicts = {}
    for cand in ("analog", "ensemble"):
        block = rep4["policies"][cand]
        if not block.get("n"):
            verdicts[cand] = {"entered": False}
            continue
        beats = {p: block["mean_interval_score"] < s for p, s in baseline_is.items()}
        verdicts[cand] = {
            "entered": True,
            "mean_interval_score": block["mean_interval_score"],
            "beats": beats,
            "beats_all_baselines": all(beats.values()),
        }
        print(
            f"🎯 E4 {cand}: n={block['n']} cov={block['coverage_observed']:.3f} "
            f"IS={block['mean_interval_score']:.3f} beats_all={all(beats.values())}"
        )

    # Paired comparison on shared targets — abstention-honest head-to-head.
    pers_rows = [c for c in base_claims if c.meta["policy"] == "persistence"]
    analog_rows = [c for c in cand_claims if c.meta["policy"] == "analog"]
    paired = paired_comparison(pers_rows, analog_rows)
    verdicts["analog_vs_persistence_paired"] = paired
    if paired.get("n_paired"):
        print(
            f"⚖️  paired (persistence − analog): n={paired['n_paired']} "
            f"diff={paired['mean_diff_a_minus_b']:.4f} "
            f"boot95={[round(x, 4) for x in paired['diff_bootstrap95']]}"
        )
    _write(
        OUT / "PHASE3_CANDIDATES.json",
        {
            "design": "candidates fit on even half (weights, width), one shot on odd half @1975",
            "success_rule": PREREGISTRATION["success_rule"],
            "ensemble_weights": list(weights),
            "width_model": winner,
            "report": rep4,
            "verdicts": verdicts,
            "best_baseline": min(baseline_is, key=baseline_is.get) if baseline_is else None,
        },
    )

    # ------------------------------------------------------------------
    # E6 — bridge disaggregation + anchor-drop curves
    # ------------------------------------------------------------------
    dynamics = fit_dynamics(anchors, groups=GROUPS, fit_start=1920)

    # Reuse the phase-3 holdout loaders (same-polity Karpat vs cross-polity provinces).
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_phase3_bridge import (  # noqa: E402
        _karpat_holdouts,
        _ottoman_province_holdouts,
    )

    karpat = _karpat_holdouts()
    provinces = _ottoman_province_holdouts()
    karpat_support = [(a.year, float(a.shares["muslim"])) for a in karpat]

    bridge: dict = {"experiments": {}}
    for shape in ("linear", "sqrt"):
        bridge["experiments"][f"karpat_loo_{shape}"] = bridge_block(
            karpat, karpat_support, dynamics, loo=True, width_shape=shape
        ) | {"lane": "same_polity"}
        bridge["experiments"][f"ottoman_provinces_{shape}"] = bridge_block(
            provinces, karpat_support, dynamics, loo=False, width_shape=shape
        ) | {"lane": "cross_polity_stress_test"}

    curves = anchor_drop_curves(desk_series, dynamics, min_points=4)
    bridge["anchor_drop_curves"] = curves
    for shape, blk in curves.items():
        print(
            f"📈 E6b {shape}: {blk['n_holdouts']} holdouts across {blk['n_series']} series, "
            f"overall cov={blk['coverage_overall']:.3f}"
        )
        for label, b in blk["by_gap"].items():
            if b.get("n"):
                print(
                    f"     gap {label:>6}: n={b['n']:4} cov={b['coverage_observed']:.3f} "
                    f"wilson={b['coverage_wilson95']}"
                )
    for name, blk in bridge["experiments"].items():
        if blk.get("n"):
            print(
                f"🌉 E6a {name}: n={blk['n']} cov={blk['coverage_observed']:.3f} "
                f"wilson={blk['coverage_wilson95']} IS={blk['mean_interval_score']:.3f}"
            )
    _write(OUT / "PHASE3_BRIDGE_CURVES.json", bridge)

    print("🏁 all experiment suites complete")


if __name__ == "__main__":
    main()
