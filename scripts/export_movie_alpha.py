#!/usr/bin/env python3
"""Export a static atlas payload for the alpha simulation movie.

Writes ``movie-alpha/data/atlas.json`` from ConfluxModel views (MENA + diaspora),
events, beacons, Phase 2b trust posteriors, and a scripted settlement tape for
the source-weighting screen.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from conflux.model import LAYOUT, YEAR_MAX, YEAR_MIN, ConfluxModel

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "movie-alpha" / "data" / "atlas.json"
TRUST = ROOT / "data-validation-reports" / "PHASE2B_TRUST.json"
BEACONS = ROOT / "data" / "processed" / "beacons.jsonl"
ANCHORS = ROOT / "data" / "processed" / "anchors.jsonl"

MENA = (
    "algeria",
    "bahrain",
    "egypt",
    "iran",
    "iraq",
    "israel",
    "jordan",
    "kuwait",
    "lebanon",
    "libya",
    "morocco",
    "oman",
    "palestinian_territories",
    "qatar",
    "saudi_arabia",
    "sudan",
    "syria",
    "tunisia",
    "turkey",
    "united_arab_emirates",
    "western_sahara",
    "yemen",
)
DIASPORA = (
    "france",
    "united_states",
    "greece",
    "germany",
    "united_kingdom",
    "canada",
)

# Geographic-ish board (0..1). Only MENA + diaspora — no rest-of-world fill.
MOVIE_LAYOUT: dict[str, tuple[float, float]] = {
    **LAYOUT,
    "algeria": (0.22, 0.56),
    "tunisia": (0.32, 0.50),
    "libya": (0.40, 0.55),
    "sudan": (0.50, 0.72),
    "jordan": (0.55, 0.46),
    "palestinian_territories": (0.525, 0.50),
    "kuwait": (0.68, 0.48),
    "bahrain": (0.70, 0.52),
    "qatar": (0.72, 0.54),
    "united_arab_emirates": (0.74, 0.56),
    "oman": (0.76, 0.62),
    "western_sahara": (0.08, 0.62),
    "germany": (0.28, 0.18),
    "united_kingdom": (0.16, 0.16),
    "canada": (0.05, 0.08),
}

DISPLAY = {
    "palestinian_territories": "Palestine",
    "united_arab_emirates": "UAE",
    "united_states": "United States",
    "united_kingdom": "United Kingdom",
    "saudi_arabia": "Saudi Arabia",
    "western_sahara": "W. Sahara",
}


def _polities_with_anchors() -> tuple[str, ...]:
    have: set[str] = set()
    with ANCHORS.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            have.add(json.loads(line)["polity_id"])
    return tuple(p for p in (*MENA, *DIASPORA) if p in have)


def _rgb_outline(shares: dict[str, float]) -> list[float]:
    """Map Muslim→R, Christian→G, Jewish→B with gamma so minorities read."""
    m = float(shares.get("muslim", 0.0))
    c = float(shares.get("christian", 0.0))
    j = float(shares.get("jewish", 0.0))
    # Lift small components so Israel/Lebanon don't wash out.
    gamma = 0.55
    r, g, b = m**gamma, c**gamma, j**gamma
    s = r + g + b
    if s < 1e-9:
        return [0.35, 0.38, 0.42]
    return [r / s, g / s, b / s]


def _bands(shares: dict[str, float]) -> list[dict]:
    ranked = sorted(
        (
            (k, float(v))
            for k, v in shares.items()
            if k in ("muslim", "christian", "jewish", "unaffiliated", "other") and v > 0.01
        ),
        key=lambda kv: -kv[1],
    )
    out = []
    for i, (name, frac) in enumerate(ranked[:3]):
        out.append({"group": name, "share": round(frac, 4), "ring": i})
    return out


def _serialize_node(n, prev_shares: dict[str, float] | None) -> dict:
    shares = {k: round(float(v), 5) for k, v in n.shares.items()}
    vel = 0.0
    if prev_shares:
        keys = set(shares) | set(prev_shares)
        vel = math.sqrt(sum((shares.get(k, 0) - prev_shares.get(k, 0)) ** 2 for k in keys))
    return {
        "id": n.polity_id,
        "name": DISPLAY.get(n.polity_id, n.display_name),
        "pop": int(n.total_population),
        "shares": shares,
        "dominant": n.dominant_religion,
        "confidence": round(float(n.confidence), 3),
        "anchor_year": int(n.anchor_year),
        "net_migration": int(n.net_migration),
        "rgb": [round(x, 4) for x in _rgb_outline(shares)],
        "bands": _bands(shares),
        "velocity": round(vel, 5),
        "sources": list(n.source_ids[:4]),
        "diaspora": n.polity_id in DIASPORA,
    }


def _load_beacons() -> list[dict]:
    if not BEACONS.exists():
        return []
    rows = []
    with BEACONS.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            b = json.loads(line)
            rows.append(
                {
                    "id": b["beacon_id"],
                    "title": b["title"],
                    "year_start": b["year_start"],
                    "year_end": b.get("year_end"),
                    "video_role": b.get("video_role"),
                    "significance": b.get("demographic_significance"),
                    "linked_event_ids": b.get("linked_event_ids") or [],
                    "status": b.get("status"),
                }
            )
    return rows


def _settlement_tape(final_posts: dict) -> list[dict]:
    """Scripted Beta bumps from uniform prior toward Phase 2b means (demo tape)."""
    tape: list[dict] = []
    # Pick a readable subset for the movie.
    keys = [
        "source_trust:pew_global_religious_composition_2010_2020",
        "source_trust:arab_barometer",
        "source_trust:arda_national_profiles_2005",
        "source_trust:cbs_population_madaf",
        "definition_gap:cjp_vs_pew_jewish",
        "source_trust:hand_seed_v0",
    ]
    state = {k: {"alpha": 1.0, "beta": 1.0, "trials": 0} for k in keys if k in final_posts}
    # Seed a few extras if missing.
    for k in list(final_posts)[:8]:
        if k not in state and k.startswith("source_trust:"):
            state[k] = {"alpha": 1.0, "beta": 1.0, "trials": 0}
        if len(state) >= 6:
            break

    steps = [
        ("pew_global_religious_composition_2010_2020", True, 1.0, "Pew 2010 share claim hits 2020 census band"),
        ("arab_barometer", True, 0.7, "Arab Barometer majority label corroborated (independence-discounted)"),
        ("arda_national_profiles_2005", False, 0.5, "ARDA 2005 misses a later Pew band — partial miss"),
        ("cbs_population_madaf", True, 1.0, "CBS Madaf Jewish counts settle against WJP overlay"),
        ("pew_global_religious_composition_2010_2020", True, 1.0, "Second Pew polity settles OK"),
        ("arab_barometer", True, 0.7, "Another Arab Barometer hit"),
        ("arda_national_profiles_2005", True, 0.5, "ARDA recovers on a calmer polity"),
        ("hand_seed_v0", False, 0.8, "Hand seed overstates a 1950 Christian share"),
        ("pew_global_religious_composition_2010_2020", True, 1.0, "Pew keeps earning trust"),
        ("cbs_population_madaf", True, 0.9, "CBS partial on edge case"),
        ("cjp_vs_pew_jewish", True, 1.0, "Definition gap claim: CJP≠Pew Jewish — expected, routed separately"),
        ("arab_barometer", False, 0.6, "One Barometer miss under shock window"),
        ("pew_global_religious_composition_2010_2020", True, 1.0, "Calm-window Pew hit"),
        ("arda_national_profiles_2005", False, 0.4, "ARDA miss under weak corroboration"),
        ("hand_seed_v0", True, 0.5, "Hand seed OK on coarse dominant-religion claim"),
    ]

    def hyp(short: str) -> str:
        if short.startswith("cjp"):
            return "definition_gap:cjp_vs_pew_jewish"
        return f"source_trust:{short}"

    for i, (short, ok, w, note) in enumerate(steps):
        hid = hyp(short)
        if hid not in state:
            continue
        st = state[hid]
        if ok:
            st["alpha"] += w
        else:
            st["beta"] += w
        st["trials"] += 1
        a, b = st["alpha"], st["beta"]
        mean = a / (a + b)
        tape.append(
            {
                "t": i,
                "hypothesis_id": hid,
                "success": ok,
                "weight": w,
                "note": note,
                "alpha": round(a, 3),
                "beta": round(b, 3),
                "mean": round(mean, 4),
                "snapshot": {
                    k: {
                        "alpha": round(v["alpha"], 3),
                        "beta": round(v["beta"], 3),
                        "mean": round(v["alpha"] / (v["alpha"] + v["beta"]), 4),
                        "trials": v["trials"],
                    }
                    for k, v in state.items()
                },
            }
        )
    return tape


def main() -> None:
    polities = _polities_with_anchors()
    model = ConfluxModel(polity_ids=polities, apply_event_deltas=True)

    frames: dict[str, dict] = {}
    prev: dict[str, dict[str, float]] = {}
    # Annual frames — pop overlays animate; shares hold between anchors.
    for year in range(YEAR_MIN, YEAR_MAX + 1):
        view = model.view(year)
        nodes = {}
        for pid, node in view.nodes.items():
            nodes[pid] = _serialize_node(node, prev.get(pid))
            prev[pid] = dict(node.shares)
        edges = []
        for re in view.edges:
            e = re.edge
            edges.append(
                {
                    "id": e.edge_id,
                    "from": e.from_polity,
                    "to": e.to_polity,
                    "group": e.group.value if hasattr(e.group, "value") else str(e.group),
                    "volume": int(e.volume_est or 0),
                    "alpha": round(float(re.alpha), 3),
                    "year_start": e.year_start,
                    "year_end": e.year_end,
                    "event": e.trigger_event_id,
                }
            )
        frames[str(year)] = {"year": year, "nodes": nodes, "edges": edges}

    events = []
    for ev in model.events:
        events.append(
            {
                "id": ev.event_id,
                "title": ev.title,
                "year": ev.year,
                "year_end": ev.year_end,
                "polities": list(ev.affected_polities),
            }
        )

    trust_final = {}
    if TRUST.exists():
        trust_final = json.loads(TRUST.read_text(encoding="utf-8")).get("posteriors") or {}

    # Histograms for data view: share of muslim by polity at 1950/2010/2020
    hist_years = [1950, 2010, 2020]
    histograms = {}
    for hy in hist_years:
        fr = frames[str(hy)]["nodes"]
        histograms[str(hy)] = [
            {
                "id": pid,
                "name": n["name"],
                "muslim": n["shares"].get("muslim", 0),
                "christian": n["shares"].get("christian", 0),
                "jewish": n["shares"].get("jewish", 0),
                "pop": n["pop"],
                "confidence": n["confidence"],
            }
            for pid, n in sorted(fr.items(), key=lambda kv: -kv[1]["shares"].get("muslim", 0))
        ]

    meta = {
        "title": "Conflux Atlas — Alpha Movie",
        "version": "alpha",
        "year_min": YEAR_MIN,
        "year_max": YEAR_MAX,
        "polities": list(polities),
        "layout": {k: list(v) for k, v in MOVIE_LAYOUT.items() if k in polities},
        "mena": list(MENA),
        "diaspora": list(DIASPORA),
        "legend": {
            "rgb": "Outline RGB ≈ Muslim / Christian / Jewish (gamma-weighted)",
            "bands": "Concentric rings: majority → minority",
            "bulge": "Outline pulse scales with share velocity + |net migration|",
            "arcs": "Migration edges (volume × alpha fade)",
        },
        "honesty": (
            "Alpha build: hold-shares between anchors; event deltas rewrite nodes when edges fire. "
            "Pre-1900 beacons are narrative markers only — the numeric desk starts ~1900."
        ),
    }

    payload = {
        "meta": meta,
        "frames": frames,
        "events": events,
        "beacons": _load_beacons(),
        "trust_final": trust_final,
        "settlement_tape": _settlement_tape(trust_final),
        "histograms": histograms,
        "tour_beacons": [
            {
                "event_id": "lausanne_population_exchange_1923",
                "year": 1923,
                "title": "Lausanne population exchange",
                "blurb": "Greece ↔ Turkey: a forced bilateral swap. Watch the edge thicken and node bands twitch.",
            },
            {
                "event_id": "arab_israeli_war_1948",
                "year": 1948,
                "title": "1948 war & Jewish exodus corridors",
                "blurb": "Multiple origin→Israel bursts. Israel's Jewish band grows; source countries lose Jewish share.",
            },
            {
                "event_id": "lebanese_civil_war_1975",
                "year": 1975,
                "title": "Lebanese Civil War",
                "blurb": "Outflows to France and neighbors. Confidence bleeds where citations go quiet.",
            },
            {
                "event_id": "iranian_revolution_1979",
                "year": 1979,
                "title": "Iranian Revolution",
                "blurb": "Jewish emigration toward Israel — a thin but sharp edge on the map.",
            },
            {
                "event_id": "syrian_civil_war_2011",
                "year": 2011,
                "title": "Syrian Civil War refugees",
                "blurb": "UNHCR-scale stocks to Turkey, Lebanon, Jordan, Egypt, Germany, Iraq. Stocks ≠ flows — we say so.",
            },
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    mb = OUT.stat().st_size / 1e6
    print(f"wrote {OUT} ({mb:.2f} MB) polities={len(polities)} years={YEAR_MAX - YEAR_MIN + 1}")


if __name__ == "__main__":
    main()
