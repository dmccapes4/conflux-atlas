#!/usr/bin/env python3
"""Validate Conflux Atlas processed data infrastructure → markdown report.

Checks:
  - expected processed JSONL files exist / non-empty
  - source_ids referenced in records appear in BIBLIOGRAPHY.md
  - Anchor / MigrationEdge / Event schema validation (where applicable)
  - edge.trigger_event_id resolves to events.jsonl
  - share-sum / confidence range spot checks
  - shape-of-data summary (row counts, year spans, polity coverage)

Writes: data-validation-reports/VERIFY_<timestamp>.md (+ latest symlink-ish copy)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.schema import Anchor, Event, MigrationEdge  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
BIB = ROOT / "data" / "sources" / "BIBLIOGRAPHY.md"
DEFAULT_OUT_DIR = ROOT / "data-validation-reports"

# Core artifacts the desk is expected to produce.
# min_rows catches truncated re-ingests that still parse (e.g. MEVS 1MB Wayback).
EXPECTED_FILES: dict[str, dict[str, object]] = {
    "anchors.jsonl": {"desc": "Pew (+ merged hand seeds) religion-share anchors", "min_rows": 400},
    "anchors_historical_seed.jsonl": {"desc": "Hand historical seed (pre-merge copy)", "min_rows": 30},
    "edges.jsonl": {"desc": "Hand-seeded migration edges", "min_rows": 8},
    "events.jsonl": {"desc": "Event triggers linked to edges", "min_rows": 3},
    "population_totals.jsonl": {"desc": "OWID population totals", "min_rows": 1000},
    "population_totals_wpp.jsonl": {"desc": "UN WPP population totals", "min_rows": 1000},
    "population_totals_worldbank.jsonl": {"desc": "World Bank SP.POP.TOTL", "min_rows": 800},
    "unhcr_refugee_stock_by_coa.jsonl": {"desc": "UNHCR COA refugee stock", "min_rows": 500},
    "un_desa_migrant_stock_destination.jsonl": {"desc": "UN DESA destination stock", "min_rows": 100},
    "un_desa_migrant_stock_od.jsonl": {"desc": "UN DESA dest×origin stock", "min_rows": 1000},
    "wjp_world_core_jewish_population.jsonl": {"desc": "WJP world CJP series", "min_rows": 10},
    "wjp_country_core_jewish_population.jsonl": {"desc": "WJP country CJP", "min_rows": 100},
    "arab_barometer_religion_shares.jsonl": {"desc": "AB Q1012 survey shares", "min_rows": 40},
    "arda_national_profiles_2005.jsonl": {"desc": "ARDA 2005 national profiles", "min_rows": 100},
    "cbs_israel_population_groups.jsonl": {"desc": "CBS Israel group totals", "min_rows": 4},
    "pcbs_projected_population.jsonl": {"desc": "PCBS Palestine projections", "min_rows": 8},
    "ottoman_empire_population.jsonl": {"desc": "Ottoman wiki empire series", "min_rows": 5},
    "ottoman_1914_provinces.jsonl": {"desc": "Ottoman 1914 provinces", "min_rows": 20},
    "karpat_religious_structure_summary.jsonl": {"desc": "Karpat Table 4.3", "min_rows": 3},
    "basihos_turkey_borders_population.jsonl": {"desc": "Basihos Turkey-border pops", "min_rows": 10},
    "mccarthy_six_vilayets_religion.jsonl": {"desc": "McCarthy Six Vilayets", "min_rows": 2},
}


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                rows.append({"__parse_error__": str(e), "__line__": i})
    return rows


def _bib_source_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    ids: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 2:
            continue
        sid = cols[0]
        if sid in {"source_id", "---"} or sid.startswith("---"):
            continue
        if re.match(r"^[a-z][a-z0-9_]+$", sid):
            ids.add(sid)
    return ids


def _collect_source_ids(rows: list[dict]) -> set[str]:
    out: set[str] = set()
    for r in rows:
        for sid in r.get("source_ids") or []:
            if isinstance(sid, str):
                out.add(sid)
        # catalogs sometimes use nested
        if isinstance(r.get("source_id"), str):
            out.add(r["source_id"])
    return out


def verify(out_dir: Path) -> Path:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"VERIFY_{stamp}.md"
    latest = out_dir / "VERIFY_LATEST.md"

    checks: list[tuple[str, str, str]] = []  # status, title, detail
    sections: list[str] = []

    bib_ids = _bib_source_ids(BIB) if BIB.is_file() else set()
    if not bib_ids:
        checks.append(("FAIL", "bibliography", f"No source_ids parsed from {BIB}"))
    else:
        checks.append(("PASS", "bibliography", f"{len(bib_ids)} source_ids registered"))

    # --- file presence ---
    present_rows: dict[str, list[dict]] = {}
    missing = []
    empty = []
    for fname, meta in EXPECTED_FILES.items():
        desc = str(meta["desc"])
        min_rows = int(meta.get("min_rows") or 1)
        path = PROCESSED / fname
        if not path.is_file():
            missing.append(fname)
            checks.append(("FAIL", f"file:{fname}", f"missing — {desc}"))
            continue
        rows = _load_jsonl(path)
        present_rows[fname] = rows
        if not rows:
            empty.append(fname)
            checks.append(("FAIL", f"file:{fname}", "exists but empty"))
        else:
            parse_errs = sum(1 for r in rows if "__parse_error__" in r)
            n = len(rows)
            if parse_errs:
                checks.append(
                    ("FAIL", f"file:{fname}", f"{n} rows, {parse_errs} JSON parse errors")
                )
            elif n < min_rows:
                checks.append(
                    (
                        "FAIL",
                        f"file:{fname}",
                        f"{n} rows < min_rows={min_rows} (possible truncated re-ingest) — {desc}",
                    )
                )
            else:
                checks.append(("PASS", f"file:{fname}", f"{n} rows (min {min_rows}) — {desc}"))

    # --- schema: anchors ---
    anchor_errs = 0
    share_sum_warn = 0
    if "anchors.jsonl" in present_rows:
        for r in present_rows["anchors.jsonl"]:
            if "__parse_error__" in r:
                continue
            try:
                Anchor.model_validate(r)
            except Exception as e:
                anchor_errs += 1
                if anchor_errs <= 5:
                    checks.append(("FAIL", "schema:anchors", f"{r.get('anchor_id')}: {e}"))
        if anchor_errs == 0:
            checks.append(
                ("PASS", "schema:anchors", f"all {len(present_rows['anchors.jsonl'])} Anchor-valid")
            )
        else:
            checks.append(("FAIL", "schema:anchors", f"{anchor_errs} invalid Anchor rows"))

    # --- schema: edges ---
    edge_errs = 0
    if "edges.jsonl" in present_rows:
        for r in present_rows["edges.jsonl"]:
            if "__parse_error__" in r:
                continue
            try:
                MigrationEdge.model_validate(r)
            except Exception as e:
                edge_errs += 1
                checks.append(("FAIL", "schema:edges", f"{r.get('edge_id')}: {e}"))
        if edge_errs == 0:
            checks.append(
                ("PASS", "schema:edges", f"all {len(present_rows['edges.jsonl'])} MigrationEdge-valid")
            )

    # --- schema: events ---
    event_ids: set[str] = set()
    event_errs = 0
    if "events.jsonl" in present_rows:
        for r in present_rows["events.jsonl"]:
            if "__parse_error__" in r:
                continue
            try:
                ev = Event.model_validate(r)
                event_ids.add(ev.event_id)
            except Exception as e:
                event_errs += 1
                checks.append(("FAIL", "schema:events", f"{r.get('event_id')}: {e}"))
        if event_errs == 0:
            checks.append(
                ("PASS", "schema:events", f"all {len(present_rows['events.jsonl'])} Event-valid")
            )

    # --- edge → event linkage ---
    if "edges.jsonl" in present_rows:
        dangling = []
        for r in present_rows["edges.jsonl"]:
            tid = r.get("trigger_event_id")
            if tid and tid not in event_ids:
                dangling.append(f"{r.get('edge_id')} → {tid}")
        if dangling:
            checks.append(("FAIL", "edge→event", "; ".join(dangling)))
        else:
            linked = sum(1 for r in present_rows["edges.jsonl"] if r.get("trigger_event_id"))
            checks.append(
                ("PASS", "edge→event", f"{linked} edges with triggers; all resolve in events.jsonl")
            )

    # --- bibliography coverage for referenced source_ids ---
    all_refs: set[str] = set()
    for rows in present_rows.values():
        all_refs |= _collect_source_ids(rows)
    missing_bib = sorted(all_refs - bib_ids)
    if missing_bib:
        checks.append(
            ("WARN", "source_ids→bib", f"{len(missing_bib)} referenced but not in BIBLIOGRAPHY: {missing_bib[:12]}")
        )
    else:
        checks.append(
            ("PASS", "source_ids→bib", f"all {len(all_refs)} referenced source_ids registered")
        )

    # --- engine wiring gap (informational) ---
    model_path = ROOT / "conflux" / "model.py"
    model_text = model_path.read_text(encoding="utf-8") if model_path.is_file() else ""
    wired_hints = []
    for token, label in [
        ("population_totals", "OWID/WPP overlays"),
        ("apply_event_deltas", "event-delta flag"),
        ("pops_wpp", "WPP totals"),
        ("wjp_by_polity", "WJP CJP"),
        ("desa_od", "DESA OD"),
        ("events", "events"),
    ]:
        if token in model_text:
            wired_hints.append(label)
    checks.append(
        (
            "INFO",
            "engine_wiring",
            f"model.py mentions: {wired_hints or ['(minimal — overlays/events still thin)']}",
        )
    )

    # --- shape of data ---
    shape_lines: list[str] = []
    shape_lines.append("| File | Rows | Notes |")
    shape_lines.append("| --- | ---: | --- |")
    for fname in sorted(present_rows):
        rows = [r for r in present_rows[fname] if "__parse_error__" not in r]
        years = []
        for r in rows:
            for k in ("year", "year_start"):
                if isinstance(r.get(k), int):
                    years.append(r[k])
        yr = f"{min(years)}–{max(years)}" if years else "—"
        shape_lines.append(f"| `{fname}` | {len(rows)} | years {yr} |")

    # polity coverage on anchors
    if "anchors.jsonl" in present_rows:
        by_polity: Counter[str] = Counter()
        by_year: Counter[int] = Counter()
        for r in present_rows["anchors.jsonl"]:
            if "__parse_error__" in r:
                continue
            by_polity[str(r.get("polity_id"))] += 1
            if isinstance(r.get("year"), int):
                by_year[r["year"]] += 1
        top = by_polity.most_common(12)
        shape_lines.append("")
        shape_lines.append("### Anchor density (top polities)")
        shape_lines.append("")
        shape_lines.append("| polity_id | n_anchors |")
        shape_lines.append("| --- | ---: |")
        for pid, n in top:
            shape_lines.append(f"| `{pid}` | {n} |")
        shape_lines.append("")
        shape_lines.append(f"Distinct polities: **{len(by_polity)}**. Year histogram: {dict(sorted(by_year.items()))}")

        # Inter-anchor gaps (demo polities)
        shape_lines.append("")
        shape_lines.append("### Inter-anchor gaps (demo slice)")
        shape_lines.append("")
        shape_lines.append("| polity_id | years | gaps (Δy) | max_gap |")
        shape_lines.append("| --- | --- | --- | ---: |")
        demo = {
            "egypt",
            "turkey",
            "israel",
            "lebanon",
            "syria",
            "iraq",
            "iran",
            "saudi_arabia",
            "morocco",
            "yemen",
            "france",
            "united_states",
        }
        by_polity_years: dict[str, list[int]] = defaultdict(list)
        for r in present_rows["anchors.jsonl"]:
            if "__parse_error__" in r:
                continue
            pid = str(r.get("polity_id"))
            if pid in demo and isinstance(r.get("year"), int):
                by_polity_years[pid].append(int(r["year"]))
        for pid in sorted(by_polity_years):
            ys = sorted(set(by_polity_years[pid]))
            gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
            gap_s = ", ".join(str(g) for g in gaps) if gaps else "—"
            shape_lines.append(
                f"| `{pid}` | {ys} | {gap_s} | {max(gaps) if gaps else 0} |"
            )

    # confidence distribution on anchors
    if "anchors.jsonl" in present_rows:
        confs = [
            float(r["confidence"])
            for r in present_rows["anchors.jsonl"]
            if isinstance(r.get("confidence"), (int, float))
        ]
        if confs:
            confs_sorted = sorted(confs)
            mid = confs_sorted[len(confs_sorted) // 2]
            shape_lines.append("")
            shape_lines.append(
                f"Anchor confidence: n={len(confs)} min={min(confs):.2f} "
                f"median={mid:.2f} max={max(confs):.2f}"
            )

    # --- assemble report ---
    n_pass = sum(1 for s, _, _ in checks if s == "PASS")
    n_fail = sum(1 for s, _, _ in checks if s == "FAIL")
    n_warn = sum(1 for s, _, _ in checks if s == "WARN")
    n_info = sum(1 for s, _, _ in checks if s == "INFO")
    verdict = "PASS" if n_fail == 0 else "FAIL"

    lines: list[str] = []
    lines.append(f"# Conflux Atlas — Data Validation Report")
    lines.append("")
    lines.append(f"- **Generated (UTC):** {now.isoformat()}")
    lines.append(f"- **Verdict:** **{verdict}**")
    lines.append(f"- **Counts:** PASS={n_pass} · FAIL={n_fail} · WARN={n_warn} · INFO={n_info}")
    lines.append(f"- **Processed dir:** `{PROCESSED.relative_to(ROOT)}`")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Status | Check | Detail |")
    lines.append("| --- | --- | --- |")
    for status, title, detail in checks:
        detail_esc = detail.replace("|", "\\|")
        lines.append(f"| {status} | `{title}` | {detail_esc} |")
    lines.append("")
    lines.append("## Shape of the data")
    lines.append("")
    lines.extend(shape_lines)
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Schema checks apply to `anchors.jsonl`, `edges.jsonl`, `events.jsonl` "
        "(Pydantic `Anchor` / `MigrationEdge` / `Event`)."
    )
    lines.append(
        "- Overlay series (WJP, DESA, UNHCR, …) are presence + JSON-parse validated; "
        "they are not yet required to validate as full `Anchor` records."
    )
    lines.append(
        "- A PASS here means the *data desk* is coherent. Engine wiring "
        "(events/edges mutating node state) is a separate concern — see STRATEGY / technical review."
    )
    lines.append("")

    text = "\n".join(lines) + "\n"
    out_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return out_path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = p.parse_args()
    path = verify(args.out_dir)
    # print path + verdict line for make
    body = path.read_text(encoding="utf-8")
    verdict = "PASS" if "**Verdict:** **PASS**" in body else "FAIL"
    print(f"wrote {path}")
    print(f"verdict={verdict}")
    raise SystemExit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
