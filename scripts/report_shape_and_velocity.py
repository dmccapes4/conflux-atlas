#!/usr/bin/env python3
"""Write Phase 0 shape-of-data + inter-anchor velocity reports under docs/.

Inter-anchor Δshare/Δt with gap length — never fabricated annual vol.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conflux.model import DEMO_POLITIES  # noqa: E402
from conflux.schema import Anchor  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
DOCS = ROOT / "docs"

DEMO = [p for p in DEMO_POLITIES if p != "greece"]


def _load_anchors() -> dict[str, list[Anchor]]:
    by: dict[str, list[Anchor]] = defaultdict(list)
    path = PROCESSED / "anchors.jsonl"
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            a = Anchor.model_validate(json.loads(line))
            by[a.polity_id].append(a)
    for pid in by:
        by[pid].sort(key=lambda a: a.year)
    return by


def write_shape(by: dict[str, list[Anchor]], out: Path) -> None:
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        "# Shape of the Data",
        "",
        f"*Generated {now}. Phase 0 Paper A Figure 1 precursor.*",
        "",
        "## Demo-slice anchor density",
        "",
        "| polity_id | n | years | gaps (years) | max_gap | conf min–max |",
        "| --- | ---: | --- | --- | ---: | --- |",
    ]
    for pid in DEMO:
        rows = by.get(pid) or []
        ys = [a.year for a in rows]
        gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        confs = [a.confidence for a in rows]
        gap_s = ", ".join(str(g) for g in gaps) if gaps else "—"
        conf_s = f"{min(confs):.2f}–{max(confs):.2f}" if confs else "—"
        lines.append(
            f"| `{pid}` | {len(rows)} | {ys} | {gap_s} | {max(gaps) if gaps else 0} | {conf_s} |"
        )

    all_years = sorted({a.year for rows in by.values() for a in rows})
    lines += [
        "",
        f"Full anchors.jsonl: **{sum(len(v) for v in by.values())}** rows across "
        f"**{len(by)}** polities; year span {all_years[0]}–{all_years[-1]}.",
        "",
        "## Missingness notes",
        "",
        "- Pre-2010 religion shares for most polities are hand seeds (1900/1950/2000) + Pew 2010/2020.",
        "- Greece is an edge endpoint only (1923 exchange), not a seeded share series.",
        "- Overlay series (WPP/OWID/WJP/DESA) are separate files — see `make verify-all`.",
        "",
        "See also `docs/INTER_ANCHOR_VELOCITY.md`.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def write_velocity(by: dict[str, list[Anchor]], out: Path) -> None:
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        "# Inter-Anchor Velocity",
        "",
        f"*Generated {now}. Δshare / Δt between cited anchors — **not** annualized vol.*",
        "",
        "For each consecutive anchor pair on a demo polity, report the change in "
        "dominant-group share and muslim/christian/jewish shares, divided by the gap length. "
        "Large gaps (e.g. 1900→1950) make annualized figures misleading; we report "
        "**per-year average over the gap** only as a descriptive rate, always with `gap`.",
        "",
        "| polity | y0→y1 | gap | Δmuslim/yr | Δchristian/yr | Δjewish/yr | notes |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for pid in DEMO:
        rows = by.get(pid) or []
        for i in range(len(rows) - 1):
            a0, a1 = rows[i], rows[i + 1]
            gap = a1.year - a0.year
            if gap <= 0:
                continue
            def rate(key: str) -> float:
                return (a1.shares.get(key, 0.0) - a0.shares.get(key, 0.0)) / gap

            note = "sparse" if gap >= 40 else ("modern" if a0.year >= 2000 else "")
            lines.append(
                f"| `{pid}` | {a0.year}→{a1.year} | {gap} | "
                f"{rate('muslim'):+.4f} | {rate('christian'):+.4f} | {rate('jewish'):+.4f} | {note} |"
            )
    lines += [
        "",
        "## Reading guide",
        "",
        "- Magnitudes near ±0.001–0.01 /yr over Pew decades are typical composition drift.",
        "- Rates spanning 1900→1950 mix real change with seed uncertainty — treat as exploratory.",
        "- Event-delta accounting (model flag) moves populations *within* gaps; this table is "
        "anchor-to-anchor only.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--docs", type=Path, default=DOCS)
    args = p.parse_args()
    args.docs.mkdir(parents=True, exist_ok=True)
    by = _load_anchors()
    shape = args.docs / "SHAPE_OF_THE_DATA.md"
    vel = args.docs / "INTER_ANCHOR_VELOCITY.md"
    write_shape(by, shape)
    write_velocity(by, vel)
    print(f"wrote {shape}")
    print(f"wrote {vel}")


if __name__ == "__main__":
    main()
