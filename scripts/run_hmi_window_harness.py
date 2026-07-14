#!/usr/bin/env python3
"""Run the HMI window harness (HYPOTHESIS_HMI_WINDOWS.md).

Sweeps window size x model over two deterministic-gold tasks:

  Task A — production coupling classification (verifier gold);
  Task B — typed extraction from synthetic report pages (planted gold).

Local models run against ollama (``--url`` to point at the 4090 box);
``--openai-models gpt-4.1`` adds API cells (OPENAI_API_KEY from the
environment or ``--env-file``).

Usage:
  python scripts/run_hmi_window_harness.py \
      [--ollama-models llama3.2:3b,qwen3:8b] [--openai-models gpt-4.1] \
      [--windows 1,3,6,12] [--limit-pairs 96] [--pages 36] \
      [--url http://localhost:11434]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.hmi_harness import (  # noqa: E402
    OllamaHarnessClient,
    OpenAIHarnessClient,
    build_pages,
    run_task_a,
    run_task_b,
    sample_pairs,
    select_best,
)
from conflux.observations import load_observation_desk  # noqa: E402
from conflux.schema import MigrationEdge  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data-validation-reports"
OD_PATH = PROCESSED / "unhcr_syria_refugee_stock_od.jsonl"


def _load_jsonl(path: Path, model):
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(model.model_validate(json.loads(line)))
    return out


def _pair_candidates_full(obs, mig_edges):
    """Reuse the production candidate builder from run_llm_enrichment.py."""
    spec = importlib.util.spec_from_file_location(
        "run_llm_enrichment", ROOT / "scripts" / "run_llm_enrichment.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._pair_candidates(obs, mig_edges, max_complement=None, max_definition=None)


def _read_env_key(env_file: str | None) -> str | None:
    import os

    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    if env_file:
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _fmt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ollama-models", default="llama3.2:3b,qwen3:8b")
    ap.add_argument("--openai-models", default="")
    ap.add_argument("--windows", default="1,3,6,12")
    ap.add_argument("--limit-pairs", type=int, default=96)
    ap.add_argument("--pages", type=int, default=36)
    ap.add_argument("--facts-per-page", type=int, default=3)
    ap.add_argument("--url", default="http://localhost:11434")
    ap.add_argument("--env-file", default=None, help="fallback .env for OPENAI_API_KEY")
    ap.add_argument("--out", default=str(OUT / "HMI_WINDOW_HARNESS.json"))
    args = ap.parse_args()

    windows = [int(w) for w in args.windows.split(",") if w.strip()]

    # --- population (identical across every cell) ---
    obs = load_observation_desk(PROCESSED)
    mig_edges = _load_jsonl(PROCESSED / "edges.jsonl", MigrationEdge)
    all_pairs = _pair_candidates_full(obs, mig_edges)
    pairs = sample_pairs(all_pairs, args.limit_pairs)
    od_rows = [
        json.loads(l)
        for l in OD_PATH.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    pages = build_pages(od_rows, n_pages=args.pages, facts_per_page=args.facts_per_page)
    n_gold = sum(len(p.gold) for p in pages)
    print(
        f"📥 population: {len(pairs)}/{len(all_pairs)} pair candidates, "
        f"{len(pages)} pages ({n_gold} planted facts), windows {windows}",
        flush=True,
    )

    # --- clients ---
    clients = []
    for name in [m.strip() for m in args.ollama_models.split(",") if m.strip()]:
        c = OllamaHarnessClient(model=name, base_url=args.url)
        if not c.available():
            print(f"⚠️  skipping {name}: not available at {args.url}", flush=True)
            continue
        clients.append(("ollama", c))
    for name in [m.strip() for m in args.openai_models.split(",") if m.strip()]:
        key = _read_env_key(args.env_file)
        if not key:
            print(f"⚠️  skipping {name}: no OPENAI_API_KEY", flush=True)
            continue
        clients.append(("openai", OpenAIHarnessClient(model=name, api_key=key)))
    if not clients:
        sys.exit("no models available")

    run_t0 = time.monotonic()
    cells: list[dict] = []
    total_cells = len(clients) * len(windows) * 2
    done_cells = 0

    def make_progress(label: str):
        """Per-window line: call time, cell average, cell ETA."""
        times: list[float] = []

        def progress(done: int, total: int, dt: float) -> None:
            times.append(dt)
            avg = sum(times) / len(times)
            print(
                f"⏱️  {label} window {done}/{total}  {dt:.1f}s  "
                f"(avg {avg:.1f}s · cell ETA {_fmt(avg * (total - done))} · "
                f"elapsed {_fmt(time.monotonic() - run_t0)})",
                flush=True,
            )

        return progress

    for provider, client in clients:
        for w in windows:
            for task_name, n_items, runner in (
                (
                    "A",
                    len(pairs),
                    lambda label: run_task_a(
                        client, pairs, mig_edges, obs,
                        window_size=w, progress=make_progress(label),
                    ),
                ),
                (
                    "B",
                    len(pages),
                    lambda label: run_task_b(
                        client, pages,
                        window_size=w, progress=make_progress(label),
                    ),
                ),
            ):
                label = f"[{client.model} {task_name} w={w}]"
                print(
                    f"▶️  {label} starting: {-(-n_items // w)} windows "
                    f"({n_items} items)",
                    flush=True,
                )
                t0 = time.monotonic()
                cell = runner(label)
                cell["model"] = client.model
                cell["provider"] = provider
                done_cells += 1
                primary = (
                    f"post={cell['posterior_mean']} yield={cell['yield']}"
                    if task_name == "A"
                    else f"f1={cell['f1']} recall={cell['recall']}"
                )
                tel = cell["telemetry"]
                print(
                    f"🧪 [{done_cells}/{total_cells}] {client.model} task {task_name} "
                    f"w={w}: {primary}  "
                    f"({tel['n_calls']} calls · {tel['total_tokens']} tok · "
                    f"{_fmt(time.monotonic() - t0)} · elapsed "
                    f"{_fmt(time.monotonic() - run_t0)})",
                    flush=True,
                )
                cells.append(cell)

    best = {
        "A_coupling": select_best(cells, "A_coupling"),
        "B_extraction": select_best(cells, "B_extraction"),
    }
    per_model_best = {}
    for _, client in clients:
        mcells = [c for c in cells if c["model"] == client.model]
        per_model_best[client.model] = {
            "A_coupling": select_best(mcells, "A_coupling"),
            "B_extraction": select_best(mcells, "B_extraction"),
        }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "hypothesis": "HYPOTHESIS_HMI_WINDOWS.md",
                "host": platform.node(),
                "ollama_url": args.url,
                "population": {
                    "pair_candidates": len(pairs),
                    "pair_candidates_full": len(all_pairs),
                    "pages": len(pages),
                    "gold_facts": n_gold,
                },
                "windows": windows,
                "cells": cells,
                "best_overall": best,
                "best_per_model": per_model_best,
                "total_run_seconds": round(time.monotonic() - run_t0, 1),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"💾 wrote {out_path}")

    for task, label, pk in (
        ("A_coupling", "Task A (coupling)", "posterior_mean"),
        ("B_extraction", "Task B (extraction)", "f1"),
    ):
        print(f"\n🏆 {label} best cells:")
        b = best[task]
        if b:
            print(
                f"   overall: {b['model']} w={b['window_size']} "
                f"{pk}={b[pk]} tokens={b['telemetry']['total_tokens']}"
            )
        for m, pb in per_model_best.items():
            c = pb[task]
            if c:
                print(f"   {m}: w={c['window_size']} {pk}={c[pk]}")


if __name__ == "__main__":
    main()
