#!/usr/bin/env python3
"""Phase 2b — LLM windowed enrichment (STRATEGY_CONNASCENCE.md §3).

Runs the two constrained proposer jobs over the Phase 2b artifacts:

  job 1: attribute co-variance clusters to documented events;
  job 2: classify candidate series pairs into conceptual couplings.

Every proposal is recorded and settled as a claim under
``llm_proposer:<model>`` against a deterministic verifier — the model
earns a trust posterior like any other source. Only verifier-passed
proposals materialize as edges (PHASE2B_LLM_EDGES.jsonl).

Both jobs share one loaded base model (qwen3:8b by default): the persona
and hard rules travel as a per-request system-prompt preamble and the
deterministic decoding parameters (temperature 0, top_k 1, fixed seed) as
per-request options — no Modelfile, so the two agents never trigger a
tensor re-load for identical parameters.

Prereqs:
  ollama pull qwen3:8b
  scripts/run_phase2b_connascence.py                   # cluster inputs

Usage:
  python scripts/run_llm_enrichment.py [--model NAME] [--window 12]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux import movement  # noqa: E402
from conflux.connascence import (  # noqa: E402
    CovarianceCluster,
    load_events,
    write_edges_jsonl,
)
from conflux.learning import TrustStore  # noqa: E402
from conflux.llm_enrich import (  # noqa: E402
    DEFAULT_MODEL,
    EnrichmentResult,
    OllamaClient,
    PairCandidate,
    enrich_conceptual_couplings,
    enrich_event_attribution,
)
from conflux.observations import load_observation_desk  # noqa: E402
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


def _load_clusters() -> list[CovarianceCluster]:
    path = OUT / "PHASE2B_CLUSTERS.json"
    if not path.exists():
        sys.exit("run scripts/run_phase2b_connascence.py first (no clusters file)")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        CovarianceCluster(
            cluster_id=c["cluster_id"],
            series=c["series"],
            year_min=c["year_min"],
            year_max=c["year_max"],
            dominant_direction=c["dominant_direction"],
            n_edges=c["n_edges"],
        )
        for c in data["clusters"]
    ]


def _pair_candidates(
    obs, mig_edges, *, max_complement: int | None = 40, max_definition: int | None = 30
) -> list[PairCandidate]:
    """Candidate windows for job 2: real couplings mixed with decoys.

    The mix is deliberate — the proposer must separate true couplings
    from lookalikes, otherwise its posterior is free. ``max_*=None``
    (--full) uncaps for the comprehensive Phase 3 population: all
    group-combinations per measurement and all source-combinations per
    polity-year-group.
    """
    import itertools
    from collections import defaultdict

    pairs: list[PairCandidate] = []
    seen: set[str] = set()

    def add(pid, hint, **kw):
        if pid in seen:
            return
        seen.add(pid)
        pairs.append(PairCandidate(pair_id=pid, kind_hint=hint, **kw))

    # (a) same source, polity, year, different groups → complement candidates
    by_spy = defaultdict(list)
    for o in obs:
        by_spy[(o.source_id, o.polity_id, o.year)].append(o)
    n_comp = 0
    for (src, pid, year), rows in sorted(by_spy.items()):
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda o: o.group)
        combos = itertools.combinations(rows, 2) if max_complement is None else [rows[:2]]
        for a, b in combos:
            add(
                f"cand|{src}|{pid}|{year}|{a.group}|{b.group}",
                {
                    "series_a": {"source": src, "polity": pid, "group": a.group, "year": year},
                    "series_b": {"source": src, "polity": pid, "group": b.group, "year": year},
                },
                polity_a=pid, polity_b=pid, group_a=a.group, group_b=b.group,
                source_a=src, source_b=src, year_a=year, year_b=year,
            )
            n_comp += 1
        if max_complement is not None and n_comp >= max_complement:
            break

    # (b) same group across migration-edge polity pairs → conservation
    # candidates, plus decoys with no documented flow.
    edge_pairs = {(e.from_polity, e.to_polity, e.group.value) for e in mig_edges}
    for fp, tp, g in sorted(edge_pairs):
        add(
            f"cand|series|{fp}|{tp}|{g}",
            {
                "series_a": {"polity": fp, "group": g},
                "series_b": {"polity": tp, "group": g},
                "note": "national share series pair",
            },
            polity_a=fp, polity_b=tp, group_a=g, group_b=g,
            source_a="*series*", source_b="*series*",
        )
    for fp, tp, g in [
        ("egypt", "turkey", "jewish"),      # no documented edge
        ("morocco", "iraq", "christian"),   # no documented edge
        ("iran", "yemen", "muslim"),        # no documented edge
    ]:
        add(
            f"cand|series|{fp}|{tp}|{g}",
            {
                "series_a": {"polity": fp, "group": g},
                "series_b": {"polity": tp, "group": g},
                "note": "national share series pair",
            },
            polity_a=fp, polity_b=tp, group_a=g, group_b=g,
            source_a="*series*", source_b="*series*",
        )

    # (c) cross-source same polity-year-group → definition candidates.
    by_pgy = defaultdict(list)
    for o in obs:
        by_pgy[(o.polity_id, o.group, o.year)].append(o)
    n_def = 0
    for (pid, g, year), rows in sorted(by_pgy.items()):
        srcs = sorted({o.source_id for o in rows})
        if len(srcs) < 2:
            continue
        combos = (
            itertools.combinations(srcs, 2) if max_definition is None else [srcs[:2]]
        )
        for a, b in combos:
            add(
                f"cand|{a}|{b}|{pid}|{g}|{year}",
                {
                    "series_a": {"source": a, "polity": pid, "group": g, "year": year},
                    "series_b": {"source": b, "polity": pid, "group": g, "year": year},
                },
                polity_a=pid, polity_b=pid, group_a=g, group_b=g,
                source_a=a, source_b=b, year_a=year, year_b=year,
            )
            n_def += 1
        if max_definition is not None and n_def >= max_definition:
            break

    return pairs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="ollama model name")
    ap.add_argument("--window", type=int, default=12)
    ap.add_argument("--url", default="http://localhost:11434")
    ap.add_argument(
        "--full",
        action="store_true",
        help="uncap pair candidates — the comprehensive Phase 3 population",
    )
    args = ap.parse_args()

    client = OllamaClient(model=args.model or DEFAULT_MODEL, base_url=args.url)
    if not client.available():
        sys.exit(
            f"model {client.model} not available at {args.url}. "
            f"Pull it with: ollama pull {client.model}"
        )
    print(f"🤖 proposer: {client.model}")

    obs = load_observation_desk(PROCESSED)
    mig_edges = _load_jsonl(PROCESSED / "edges.jsonl", MigrationEdge)
    events = load_events(PROCESSED / "events.jsonl")
    clusters = _load_clusters()
    if args.full:
        pairs = _pair_candidates(obs, mig_edges, max_complement=None, max_definition=None)
    else:
        pairs = _pair_candidates(obs, mig_edges)
    n_windows = -(-len(pairs) // args.window) + -(-len(clusters) // args.window)
    print(
        f"📥 inputs: {len(clusters)} clusters, {len(pairs)} pair candidates "
        f"({'FULL' if args.full else 'pilot caps'}), {n_windows} windows total",
        flush=True,
    )

    run_t0 = time.monotonic()
    call_times: list[float] = []

    def _fmt(seconds: float) -> str:
        seconds = max(0.0, seconds)
        m, s = divmod(int(round(seconds)), 60)
        return f"{m}m{s:02d}s" if m else f"{s}s"

    def make_progress(job: str, windows_before: int):
        """Per-window line with call time, run elapsed, and whole-run ETA."""

        def progress(done: int, total: int, dt: float) -> None:
            call_times.append(dt)
            avg = sum(call_times) / len(call_times)
            done_overall = windows_before + done
            eta = avg * (n_windows - done_overall)
            print(
                f"⏱️  [{job}] window {done}/{total}  {dt:.1f}s  "
                f"(avg {avg:.1f}s · elapsed {_fmt(time.monotonic() - run_t0)} · "
                f"ETA {_fmt(eta)})",
                flush=True,
            )

        return progress

    store = TrustStore()
    result = EnrichmentResult(model=client.model)

    n_cluster_windows = -(-len(clusters) // args.window)
    enrich_event_attribution(
        client, clusters, events, mig_edges, store, result,
        window_size=args.window, progress=make_progress("events", 0),
    )
    print(
        f"🗓️  event attribution: {result.proposals} proposals, "
        f"{result.verified} verified, {result.rejected} rejected, "
        f"{result.abstained} abstained",
        flush=True,
    )
    p0, v0, a0 = result.proposals, result.verified, result.abstained

    enrich_conceptual_couplings(
        client, pairs, mig_edges, obs, store, result,
        window_size=args.window, progress=make_progress("couplings", n_cluster_windows),
    )
    print(
        f"🔗 conceptual coupling: {result.proposals - p0} proposals, "
        f"{result.verified - v0} verified, {result.abstained - a0} abstained",
        flush=True,
    )
    print(
        f"🏁 llm total: {len(call_times)} calls, "
        f"avg {sum(call_times) / len(call_times):.1f}s/call, "
        f"run time {_fmt(time.monotonic() - run_t0)}"
        if call_times
        else "🏁 no llm calls made",
        flush=True,
    )

    hyp = f"llm_proposer:{client.model}"
    post = store.get(hyp)
    print(
        f"📊 {hyp}: mean={post.mean:.3f} trials={post.trials} "
        f"({result.windows_failed}/{result.windows_run} windows failed)"
    )

    write_edges_jsonl(
        result.verified_coupling_edges, OUT / "PHASE2B_LLM_EDGES.jsonl"
    )
    store.save(OUT / "PHASE2B_LLM_LEDGER.json")
    (OUT / "PHASE2B_LLM_ENRICHMENT.json").write_text(
        json.dumps(
            {
                "model": client.model,
                "windows_run": result.windows_run,
                "windows_failed": result.windows_failed,
                "proposals": result.proposals,
                "verified": result.verified,
                "rejected": result.rejected,
                "abstained": result.abstained,
                "proposer_posterior": store.get(hyp).to_dict(),
                "verified_event_attributions": result.verified_event_edges,
                "n_verified_coupling_edges": len(result.verified_coupling_edges),
                "timing": {
                    "n_calls": len(call_times),
                    "avg_call_seconds": round(sum(call_times) / len(call_times), 2)
                    if call_times
                    else None,
                    "max_call_seconds": round(max(call_times), 2) if call_times else None,
                    "total_run_seconds": round(time.monotonic() - run_t0, 2),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"💾 wrote {OUT / 'PHASE2B_LLM_ENRICHMENT.json'}")
    print(f"💾 wrote {OUT / 'PHASE2B_LLM_EDGES.jsonl'}")
    print(f"💾 wrote {OUT / 'PHASE2B_LLM_LEDGER.json'}")


if __name__ == "__main__":
    main()
