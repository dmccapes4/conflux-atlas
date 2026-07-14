"""Event-delta accounting: migration edges rewrite node totals/shares.

Behind ``ConfluxModel(apply_event_deltas=True)``. Default remains off so
golden overlays stay stable; the demo/smoke enable the flag to show movement.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import Event, EventEffectType, MigrationEdge, Religion, dominant_from_shares


@dataclass
class AppliedDelta:
    edge_id: str
    volume: int
    volume_low: int
    volume_high: int
    group: str
    from_polity: str
    to_polity: str
    frac: float


def edge_progress_frac(edge: MigrationEdge, year: int) -> float:
    """0 before start; linear through [start, end]; 1 after end."""
    if year < edge.year_start:
        return 0.0
    if year >= edge.year_end:
        return 1.0
    span = edge.year_end - edge.year_start
    if span <= 0:
        return 1.0
    return (year - edge.year_start + 1) / (span + 1)


def _counts_from_shares(pop: int, shares: dict[str, float]) -> dict[str, float]:
    keys = set(shares) | {r.value for r in Religion}
    return {k: float(shares.get(k, 0.0)) * pop for k in keys}


def _shares_from_counts(counts: dict[str, float], pop: int) -> dict[str, float]:
    if pop <= 0:
        return {Religion.OTHER.value: 1.0}
    raw = {k: max(0.0, v) for k, v in counts.items() if v > 1e-9}
    s = sum(raw.values())
    if s <= 0:
        return {Religion.OTHER.value: 1.0}
    # rescale to pop so shares sum to 1
    return {k: v / s for k, v in raw.items()}


def apply_volume_to_nodes(
    *,
    from_pop: int,
    from_shares: dict[str, float],
    to_pop: int,
    to_shares: dict[str, float],
    group: str,
    volume: int,
) -> tuple[int, dict[str, float], int, dict[str, float]]:
    """Subtract ``volume`` of ``group`` from origin; add to destination.

    Crude Phase 0 accounting: group mass is taken from the origin share bucket
    first; any shortfall is taken pro-rata from other groups so total pop still
    moves by ``volume``. Destination gains ``volume`` of ``group``.
    """
    v = max(0, int(volume))
    g = group

    f_counts = _counts_from_shares(from_pop, from_shares)
    available = f_counts.get(g, 0.0)
    from_group_take = min(available, float(v))
    f_counts[g] = available - from_group_take
    shortfall = float(v) - from_group_take
    if shortfall > 0:
        others = {k: c for k, c in f_counts.items() if k != g and c > 0}
        other_sum = sum(others.values())
        if other_sum > 0:
            for k, c in others.items():
                f_counts[k] = max(0.0, c - shortfall * (c / other_sum))
    new_from_pop = max(0, from_pop - v)
    # Align count mass to new population.
    cs = sum(max(0.0, c) for c in f_counts.values())
    if new_from_pop > 0 and cs > 0:
        scale = new_from_pop / cs
        f_counts = {k: max(0.0, c) * scale for k, c in f_counts.items()}
    new_from_shares = _shares_from_counts(f_counts, new_from_pop)

    t_counts = _counts_from_shares(to_pop, to_shares)
    t_counts[g] = t_counts.get(g, 0.0) + float(v)
    new_to_pop = to_pop + v
    new_to_shares = _shares_from_counts(t_counts, new_to_pop)
    return int(new_from_pop), new_from_shares, int(new_to_pop), new_to_shares


def collect_applied_deltas(edges: list[MigrationEdge], year: int) -> list[AppliedDelta]:
    out: list[AppliedDelta] = []
    for e in edges:
        frac = edge_progress_frac(e, year)
        if frac <= 0:
            continue
        est = int(round(e.volume_est * frac))
        low = int(round((e.volume_low if e.volume_low is not None else e.volume_est) * frac))
        high = int(round((e.volume_high if e.volume_high is not None else e.volume_est) * frac))
        g = e.group.value if isinstance(e.group, Religion) else str(e.group)
        out.append(
            AppliedDelta(
                edge_id=e.edge_id,
                volume=est,
                volume_low=low,
                volume_high=high,
                group=g,
                from_polity=e.from_polity,
                to_polity=e.to_polity,
                frac=frac,
            )
        )
    return out


def confidence_resets_at(events: list[Event], year: int) -> dict[str, float]:
    """Latest confidence_reset per polity for events that have started by ``year``."""
    resets: dict[str, tuple[int, float]] = {}
    for ev in events:
        if year < ev.year:
            continue
        for fx in ev.effects:
            if fx.type != EventEffectType.CONFIDENCE_RESET:
                continue
            if not fx.polity_id or fx.confidence is None:
                continue
            prev = resets.get(fx.polity_id)
            if prev is None or ev.year >= prev[0]:
                resets[fx.polity_id] = (ev.year, float(fx.confidence))
    return {pid: conf for pid, (_y, conf) in resets.items()}


def dominant_str(shares: dict[str, float]) -> str:
    return dominant_from_shares(shares).value
