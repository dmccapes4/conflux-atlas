"""Load anchors/edges and build a runtime view for year Y.

Interpolation policy (v0): **hold** the latest religion anchor with year <= Y
for shares; **overlay** annual population totals preferring UN WPP, then OWID
(so node size tracks modern growth between share anchors).

When ``apply_event_deltas=True``, migration edges rewrite node totals/shares
(progressively through each edge window) and events may reset confidence.
Optional WJP core-Jewish overlays adjust the jewish share when a country CJP
row exists near Y. DESA origin×destination stocks annotate modern edges.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .deltas import (
    AppliedDelta,
    apply_volume_to_nodes,
    collect_applied_deltas,
    confidence_resets_at,
    dominant_str,
)
from .schema import Anchor, Event, MigrationEdge, Religion, dominant_from_shares

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANCHORS = ROOT / "data" / "processed" / "anchors.jsonl"
DEFAULT_EDGES = ROOT / "data" / "processed" / "edges.jsonl"
DEFAULT_POPS = ROOT / "data" / "processed" / "population_totals.jsonl"
DEFAULT_POPS_WPP = ROOT / "data" / "processed" / "population_totals_wpp.jsonl"
DEFAULT_EVENTS = ROOT / "data" / "processed" / "events.jsonl"
DEFAULT_WJP = ROOT / "data" / "processed" / "wjp_country_core_jewish_population.jsonl"
DEFAULT_DESA_OD = ROOT / "data" / "processed" / "un_desa_migrant_stock_od.jsonl"

# First demo slice — hand-seeded MENA + diaspora (+ greece for 1923 exchange).
DEMO_POLITIES: tuple[str, ...] = (
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
    "greece",
)

YEAR_MIN = 1900
YEAR_MAX = 2025

# Gentle confidence bleed per year since last cited anchor (floor per polity).
CONF_DECAY_PER_YEAR = 0.004
CONF_FLOOR = 0.15

# Keep drawing an edge this many years after year_end (fade).
EDGE_FADE_YEARS = 8

# Prefer WPP within this gap; else fall back to OWID.
POP_PRIOR_GAP_YEARS = 5
WJP_PRIOR_GAP_YEARS = 5

RELIGION_RGB: dict[str, tuple[int, int, int]] = {
    Religion.MUSLIM.value: (46, 160, 110),
    Religion.CHRISTIAN.value: (80, 140, 220),
    Religion.JEWISH.value: (230, 180, 60),
    Religion.UNAFFILIATED.value: (140, 148, 160),
    Religion.BUDDHIST.value: (200, 120, 80),
    Religion.HINDU.value: (200, 90, 70),
    Religion.OTHER.value: (160, 110, 190),
}

# Rough geographic layout in normalized board coords (0..1).
LAYOUT: dict[str, tuple[float, float]] = {
    "morocco": (0.10, 0.55),
    "spain_stub": (0.12, 0.42),
    "france": (0.18, 0.28),
    "united_states": (0.08, 0.14),
    "algeria_stub": (0.22, 0.58),
    "tunisia_stub": (0.30, 0.52),
    "libya_stub": (0.38, 0.55),
    "egypt": (0.48, 0.58),
    "saudi_arabia": (0.62, 0.62),
    "yemen": (0.66, 0.78),
    "israel": (0.52, 0.48),
    "lebanon": (0.54, 0.40),
    "syria": (0.58, 0.36),
    "iraq": (0.66, 0.42),
    "iran": (0.78, 0.40),
    "turkey": (0.58, 0.26),
    "greece": (0.46, 0.30),
}


@dataclass
class RuntimeNode:
    polity_id: str
    display_name: str
    year: int
    total_population: int
    shares: dict[str, float]
    dominant_religion: str
    confidence: float
    anchor_year: int
    source_ids: list[str] = field(default_factory=list)
    ghost: bool = False  # edge endpoint with no anchor yet
    pop_source: str | None = None  # "anchor" | "un_wpp" | "owid_population" …
    pop_low: int | None = None
    pop_high: int | None = None
    net_migration: int = 0
    wjp_jewish: int | None = None


@dataclass
class RuntimeEdge:
    edge: MigrationEdge
    alpha: float  # 1 active, fades after year_end
    desa_stock: int | None = None  # nearest DESA OD stock if available


@dataclass
class YearView:
    year: int
    nodes: dict[str, RuntimeNode]
    edges: list[RuntimeEdge]
    apply_event_deltas: bool = False
    applied_deltas: list[AppliedDelta] = field(default_factory=list)


class ConfluxModel:
    def __init__(
        self,
        anchors_path: Path | None = None,
        edges_path: Path | None = None,
        pops_path: Path | None = None,
        pops_wpp_path: Path | None = None,
        events_path: Path | None = None,
        wjp_path: Path | None = None,
        desa_od_path: Path | None = None,
        polity_ids: Iterable[str] | None = None,
        *,
        apply_event_deltas: bool = False,
        apply_wjp_overlay: bool = True,
        prefer_wpp: bool = True,
    ) -> None:
        self.polity_ids = tuple(polity_ids or DEMO_POLITIES)
        self.apply_event_deltas = apply_event_deltas
        self.apply_wjp_overlay = apply_wjp_overlay
        self.prefer_wpp = prefer_wpp
        self.anchors_by_polity: dict[str, list[Anchor]] = {p: [] for p in self.polity_ids}
        # Separate overlay series; preference resolved at lookup time.
        self.pops_owid: dict[str, dict[int, int]] = {p: {} for p in self.polity_ids}
        self.pops_wpp: dict[str, dict[int, int]] = {p: {} for p in self.polity_ids}
        self.edges: list[MigrationEdge] = []
        self.events: list[Event] = []
        # polity -> year -> core jewish pop
        self.wjp_by_polity: dict[str, dict[int, int]] = {}
        # (to, from, year) -> stock
        self.desa_od: dict[tuple[str, str, int], int] = {}
        self._load_anchors(anchors_path or DEFAULT_ANCHORS)
        self._load_edges(edges_path or DEFAULT_EDGES)
        self._load_pop_series(pops_path or DEFAULT_POPS, self.pops_owid)
        self._load_pop_series(pops_wpp_path or DEFAULT_POPS_WPP, self.pops_wpp)
        self._load_events(events_path or DEFAULT_EVENTS)
        self._load_wjp(wjp_path or DEFAULT_WJP)
        self._load_desa_od(desa_od_path or DEFAULT_DESA_OD)

    def _load_anchors(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        wanted = set(self.polity_ids)
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("polity_id") not in wanted:
                    continue
                a = Anchor.model_validate(rec)
                self.anchors_by_polity.setdefault(a.polity_id, []).append(a)
        for pid, rows in self.anchors_by_polity.items():
            rows.sort(key=lambda a: a.year)
            self.anchors_by_polity[pid] = rows

    def _load_edges(self, path: Path) -> None:
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                self.edges.append(MigrationEdge.model_validate(json.loads(line)))

    def _load_events(self, path: Path) -> None:
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                self.events.append(Event.model_validate(json.loads(line)))

    def _load_pop_series(self, path: Path, dest: dict[str, dict[int, int]]) -> None:
        if not path.exists():
            return
        wanted = set(self.polity_ids)
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                pid = rec.get("polity_id")
                if pid not in wanted:
                    continue
                dest.setdefault(pid, {})[int(rec["year"])] = int(rec["total_population"])

    def _load_wjp(self, path: Path) -> None:
        if not path.exists():
            return
        wanted = set(self.polity_ids)
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                pid = rec.get("polity_id")
                if pid not in wanted:
                    continue
                year = int(rec["year"])
                cjp = int(rec["core_jewish_population"])
                self.wjp_by_polity.setdefault(pid, {})[year] = cjp

    def _load_desa_od(self, path: Path) -> None:
        if not path.exists():
            return
        wanted = set(self.polity_ids)
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                to_p = rec.get("to_polity")
                from_p = rec.get("from_polity")
                if to_p not in wanted and from_p not in wanted:
                    continue
                year = int(rec["year"])
                stock = int(rec["migrant_stock"])
                self.desa_od[(str(to_p), str(from_p), year)] = stock

    def _lookup_prior(
        self, series: dict[int, object], year: int, gap: int
    ) -> tuple[int, object] | None:
        if year in series:
            return year, series[year]
        prior = [y for y in series if y <= year]
        if not prior:
            return None
        y = max(prior)
        if year - y <= gap:
            return y, series[y]
        return None

    def _pop_overlay(self, polity_id: str, year: int) -> tuple[int | None, str | None]:
        order = (
            (self.pops_wpp, "un_wpp"),
            (self.pops_owid, "owid_population"),
        )
        if not self.prefer_wpp:
            order = (
                (self.pops_owid, "owid_population"),
                (self.pops_wpp, "un_wpp"),
            )
        for series_map, src in order:
            series = series_map.get(polity_id) or {}
            hit = self._lookup_prior(series, year, POP_PRIOR_GAP_YEARS)
            if hit is not None:
                return int(hit[1]), src  # type: ignore[arg-type]
        return None, None

    def _wjp_overlay(self, polity_id: str, year: int) -> int | None:
        series = self.wjp_by_polity.get(polity_id) or {}
        hit = self._lookup_prior(series, year, WJP_PRIOR_GAP_YEARS)
        if hit is None:
            return None
        return int(hit[1])  # type: ignore[arg-type]

    def _desa_for_edge(self, e: MigrationEdge, year: int) -> int | None:
        # Prefer exact (to=dest, from=origin); nearest prior stock year ≤ 10y.
        candidates = [
            (y, stock)
            for (to_p, from_p, y), stock in self.desa_od.items()
            if to_p == e.to_polity and from_p == e.from_polity and y <= year
        ]
        if not candidates:
            return None
        y, stock = max(candidates, key=lambda t: t[0])
        if year - y > 10:
            return None
        return stock

    def available_years(self) -> tuple[int, int]:
        years: list[int] = []
        for rows in self.anchors_by_polity.values():
            years.extend(a.year for a in rows)
        if not years:
            return YEAR_MIN, YEAR_MAX
        return min(YEAR_MIN, min(years)), max(YEAR_MAX, max(years))

    def _latest_anchor(self, polity_id: str, year: int) -> Anchor | None:
        rows = self.anchors_by_polity.get(polity_id) or []
        best: Anchor | None = None
        for a in rows:
            if a.year <= year:
                best = a
            else:
                break
        return best

    def _confidence_at(self, anchor: Anchor, year: int) -> float:
        gap = max(0, year - anchor.year)
        return max(CONF_FLOOR, anchor.confidence - gap * CONF_DECAY_PER_YEAR)

    def _apply_wjp_to_shares(
        self, shares: dict[str, float], pop: int, jewish_n: int
    ) -> dict[str, float]:
        if pop <= 0:
            return shares
        j_share = min(0.99, max(0.0, jewish_n / pop))
        others = {k: v for k, v in shares.items() if k != Religion.JEWISH.value}
        other_sum = sum(others.values())
        remain = max(0.0, 1.0 - j_share)
        if other_sum <= 0:
            out = {Religion.JEWISH.value: j_share, Religion.OTHER.value: remain}
        else:
            out = {k: remain * (v / other_sum) for k, v in others.items()}
            out[Religion.JEWISH.value] = j_share
        return out

    def view(self, year: int) -> YearView:
        year = int(max(YEAR_MIN, min(YEAR_MAX, year)))
        nodes: dict[str, RuntimeNode] = {}

        for pid in self.polity_ids:
            a = self._latest_anchor(pid, year)
            if a is None:
                continue
            shares = dict(a.shares)
            pop = a.total_population
            pop_src = "anchor"
            overlay, overlay_src = self._pop_overlay(pid, year)
            if overlay is not None:
                pop = overlay
                pop_src = overlay_src or "owid_population"
            src_ids = list(a.source_ids)
            if pop_src not in src_ids and pop_src != "anchor":
                src_ids.append(pop_src)

            wjp_n = None
            if self.apply_wjp_overlay:
                wjp_n = self._wjp_overlay(pid, year)
                if wjp_n is not None:
                    shares = self._apply_wjp_to_shares(shares, pop, wjp_n)
                    if "jewishdatabank_world_jewish_population" not in src_ids:
                        src_ids.append("jewishdatabank_world_jewish_population")

            dom = dominant_from_shares(shares).value
            nodes[pid] = RuntimeNode(
                polity_id=pid,
                display_name=a.display_name or pid.replace("_", " ").title(),
                year=year,
                total_population=pop,
                shares=shares,
                dominant_religion=dom,
                confidence=self._confidence_at(a, year),
                anchor_year=a.year,
                source_ids=src_ids,
                pop_source=pop_src,
                wjp_jewish=wjp_n,
            )

        # Ghost placeholders for edge endpoints missing an anchor this year.
        for e in self.edges:
            for pid in (e.from_polity, e.to_polity):
                if pid in nodes:
                    continue
                if not self._edge_alpha(e, year):
                    continue
                nodes[pid] = RuntimeNode(
                    polity_id=pid,
                    display_name=pid.replace("_", " ").title(),
                    year=year,
                    total_population=0,
                    shares={Religion.OTHER.value: 1.0},
                    dominant_religion=Religion.OTHER.value,
                    confidence=0.2,
                    anchor_year=year,
                    source_ids=[],
                    ghost=True,
                )

        applied: list[AppliedDelta] = []
        if self.apply_event_deltas:
            applied = collect_applied_deltas(self.edges, year)
            # Ensure endpoints exist so deltas can land.
            for d in applied:
                for pid in (d.from_polity, d.to_polity):
                    if pid in nodes:
                        continue
                    nodes[pid] = RuntimeNode(
                        polity_id=pid,
                        display_name=pid.replace("_", " ").title(),
                        year=year,
                        total_population=0,
                        shares={Religion.OTHER.value: 1.0},
                        dominant_religion=Religion.OTHER.value,
                        confidence=0.2,
                        anchor_year=year,
                        source_ids=["hand_seed_edges_v0"],
                        ghost=True,
                    )
            for d in applied:
                origin = nodes.get(d.from_polity)
                dest = nodes.get(d.to_polity)
                if origin is None or dest is None:
                    continue
                new_from, fs, new_to, ts = apply_volume_to_nodes(
                    from_pop=origin.total_population,
                    from_shares=origin.shares,
                    to_pop=dest.total_population,
                    to_shares=dest.shares,
                    group=d.group,
                    volume=d.volume,
                )
                # Band around est using low/high volume vs est.
                band_lo = d.volume - d.volume_low
                band_hi = d.volume_high - d.volume
                origin.total_population = new_from
                origin.shares = fs
                origin.dominant_religion = dominant_str(fs)
                origin.net_migration -= d.volume
                origin.pop_low = max(0, new_from - band_hi)
                origin.pop_high = new_from + band_lo
                origin.ghost = False if new_from > 0 else origin.ghost
                dest.total_population = new_to
                dest.shares = ts
                dest.dominant_religion = dominant_str(ts)
                dest.net_migration += d.volume
                dest.pop_low = max(0, new_to - band_lo)
                dest.pop_high = new_to + band_hi
                dest.ghost = False

            resets = confidence_resets_at(self.events, year)
            for pid, conf in resets.items():
                if pid in nodes and not nodes[pid].ghost:
                    nodes[pid].confidence = conf

        runtime_edges: list[RuntimeEdge] = []
        for e in self.edges:
            alpha = self._edge_alpha(e, year)
            if alpha <= 0:
                continue
            if e.from_polity not in nodes and e.to_polity not in nodes:
                continue
            runtime_edges.append(
                RuntimeEdge(edge=e, alpha=alpha, desa_stock=self._desa_for_edge(e, year))
            )

        return YearView(
            year=year,
            nodes=nodes,
            edges=runtime_edges,
            apply_event_deltas=self.apply_event_deltas,
            applied_deltas=applied,
        )

    @staticmethod
    def _edge_alpha(e: MigrationEdge, year: int) -> float:
        if year < e.year_start:
            return 0.0
        if year <= e.year_end:
            return 1.0
        fade = year - e.year_end
        if fade > EDGE_FADE_YEARS:
            return 0.0
        return max(0.0, 1.0 - fade / EDGE_FADE_YEARS)

    @staticmethod
    def radius_for_pop(pop: int, *, ghost: bool = False) -> float:
        if ghost or pop <= 0:
            return 10.0
        # log scale: 700k → ~18px, 280M → ~52px
        return 12.0 + 6.5 * math.log10(max(pop, 10))


def layout_xy(polity_id: str, board: tuple[int, int, int, int]) -> tuple[float, float]:
    """Map polity to pixel center inside board rect (x, y, w, h)."""
    x0, y0, w, h = board
    u, v = LAYOUT.get(polity_id, (0.5, 0.5))
    # slight deterministic jitter so overlapping Levant nodes separate
    jitter = (hash(polity_id) % 7 - 3) * 4
    return x0 + u * w + jitter, y0 + v * h + jitter
