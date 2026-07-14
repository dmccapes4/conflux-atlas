"""Multi-source share observations — the expanded corroboration timeline.

Phase 2 ran source corroboration over ``anchors.jsonl`` only, which left
Pew as a settler that was never itself settled, and put ``hand_seed_v0``
(authored with knowledge of the Pew era — partially circular) at the top
of the ledger. This module widens the desk to the *ingested* sources:

    anchors.jsonl (hand seeds excluded) · ARDA 2005 · Arab Barometer ·
    CBS Israel · WJP country CJP · McCarthy Six Vilayets · Ottoman 1914
    provinces

and replaces the flat ±5pp tolerance with a level-scaled one so trace
shares (jewish 0.2% vs 0.4%) cannot mint free successes.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from .learning import Claim
from .movement import level_bin

# Sources whose trust nobody cares about (authored in-house, or fixtures).
EXCLUDED_SOURCES = frozenset({"hand_seed_v0", "hand_seed_edges_v0", "test_fixture"})

# A share below this is "not reported": zero-vs-zero agreements are trivial
# successes and must never enter the ledger.
MIN_SHARE = 0.005

DEFAULT_GROUPS = ("muslim", "christian", "jewish")

DEFAULT_MAX_GAP_YEARS = 30


@dataclass(frozen=True)
class ShareObservation:
    """One source's statement of one group's share in one polity-year."""

    obs_id: str
    polity_id: str
    group: str
    year: int
    share: float
    confidence: float
    source_id: str


def level_tolerance(share: float) -> float:
    """Corroboration tolerance scaled to the share's level bin.

    A flat ±5pp is generous at plural/majority levels and absurd for
    trace shares (any two near-zero values "agree"). Reuses the Phase 1
    level bins so the yardstick is shared across the system.
    """
    bin_ = level_bin(share)
    return {
        "trace": 0.005,
        "minority": 0.01,
        "significant": 0.03,
    }.get(bin_, 0.05)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _rows(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _primary_source(rec: dict, fallback: str) -> str:
    sids = rec.get("source_ids") or []
    return str(sids[0]) if sids else fallback


def _obs(polity: str, group: str, year: int, share: float, conf: float, src: str) -> ShareObservation:
    return ShareObservation(
        obs_id=f"{src}|{polity}|{group}|{year}",
        polity_id=polity,
        group=group,
        year=int(year),
        share=float(share),
        confidence=float(conf),
        source_id=src,
    )


def observations_from_share_records(
    records: Iterable[dict],
    *,
    groups: Sequence[str] = DEFAULT_GROUPS,
    fallback_source: str = "unknown",
    exclude_sources: frozenset[str] = EXCLUDED_SOURCES,
) -> list[ShareObservation]:
    """Records with a full ``shares`` dict (anchors, ARDA, AB, CBS, McCarthy)."""
    out: list[ShareObservation] = []
    for rec in records:
        src = _primary_source(rec, fallback_source)
        if src in exclude_sources:
            continue
        shares = rec.get("shares") or {}
        pid = rec.get("polity_id")
        year = rec.get("year")
        conf = rec.get("confidence", 0.5)
        if not pid or year is None:
            continue
        for g in groups:
            share = float(shares.get(g, 0.0))
            if share < MIN_SHARE:
                continue
            out.append(_obs(str(pid), g, int(year), share, conf, src))
    return out


def observations_from_wjp(records: Iterable[dict]) -> list[ShareObservation]:
    """WJP country CJP → jewish share = core_jewish_population / total_population."""
    out: list[ShareObservation] = []
    for rec in records:
        cjp = rec.get("core_jewish_population")
        total = rec.get("total_population")
        pid = rec.get("polity_id")
        year = rec.get("year")
        if not pid or year is None or cjp is None or not total:
            continue
        share = float(cjp) / float(total)
        if share < MIN_SHARE:
            continue
        src = _primary_source(rec, "jewishdatabank_world_jewish_population")
        out.append(_obs(str(pid), "jewish", int(year), share, rec.get("confidence", 0.5), src))
    return out


def observations_from_ottoman_provinces(records: Iterable[dict]) -> list[ShareObservation]:
    """Ottoman 1914 provinces → muslim share per province polity."""
    out: list[ShareObservation] = []
    for rec in records:
        share = rec.get("muslim_share")
        prov = rec.get("province")
        year = rec.get("year")
        if share is None or not prov or year is None:
            continue
        if float(share) < MIN_SHARE:
            continue
        pid = "ottoman_province_" + str(prov).strip().lower().replace(" ", "_")
        src = _primary_source(rec, "ottoman_demographics_wiki")
        out.append(_obs(pid, "muslim", int(year), float(share), rec.get("confidence", 0.4), src))
    return out


def _dedupe(observations: Iterable[ShareObservation]) -> list[ShareObservation]:
    """Keep the highest-confidence observation per obs_id."""
    best: dict[str, ShareObservation] = {}
    for o in observations:
        prev = best.get(o.obs_id)
        if prev is None or o.confidence > prev.confidence:
            best[o.obs_id] = o
    return sorted(best.values(), key=lambda o: (o.polity_id, o.group, o.year, o.source_id))


def load_observation_desk(
    processed_dir: str | Path,
    *,
    groups: Sequence[str] = DEFAULT_GROUPS,
) -> list[ShareObservation]:
    """Assemble the full multi-source observation timeline from data/processed."""
    d = Path(processed_dir)
    obs: list[ShareObservation] = []
    for fname in (
        "anchors.jsonl",
        "arda_national_profiles_2005.jsonl",
        "arab_barometer_religion_shares.jsonl",
        "cbs_israel_population_groups.jsonl",
        "mccarthy_six_vilayets_religion.jsonl",
    ):
        obs.extend(observations_from_share_records(_rows(d / fname), groups=groups))
    obs.extend(observations_from_wjp(_rows(d / "wjp_country_core_jewish_population.jsonl")))
    obs.extend(observations_from_ottoman_provinces(_rows(d / "ottoman_1914_provinces.jsonl")))
    return _dedupe(obs)


# ---------------------------------------------------------------------------
# Corroboration over observations (level-scaled tolerance)
# ---------------------------------------------------------------------------


def _claim_id(src: str, pid: str, group: str, y0: int, y1: int, settler: str) -> str:
    raw = f"source_trust:{src}|{pid}|{group}|{y0}|{y1}|{settler}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def make_observation_claims(
    observations: Sequence[ShareObservation],
    *,
    max_gap_years: int = DEFAULT_MAX_GAP_YEARS,
) -> list[Claim]:
    """Corroboration claims over the observation timeline.

    Same discipline as Phase 2 anchor corroboration — next qualifying
    (different-source) observation, no self-corroboration, gap cap — with
    two upgrades: same-year cross-source pairs DO settle (the cleanest
    corroboration: zero world movement between measurements), and
    tolerance is level-scaled per claim (stored in ``meta`` so the Phase 2
    ``settle_corroboration_claims`` applies it unchanged).
    """
    by_pg: dict[tuple[str, str], list[ShareObservation]] = defaultdict(list)
    for o in observations:
        by_pg[(o.polity_id, o.group)].append(o)

    claims: list[Claim] = []
    for (pid, group), rows in sorted(by_pg.items()):
        series = sorted(rows, key=lambda o: (o.year, o.source_id))
        for i, a in enumerate(series):
            nxt: ShareObservation | None = None
            for b in series[i + 1 :]:
                gap = b.year - a.year
                if gap > max_gap_years:
                    break
                if b.source_id == a.source_id:
                    continue
                nxt = b
                break
            if nxt is None:
                continue
            tol = level_tolerance(a.share)
            hyp = f"source_trust:{a.source_id}"
            claims.append(
                Claim(
                    claim_id=_claim_id(a.source_id, pid, group, a.year, nxt.year, nxt.source_id),
                    hypothesis_id=hyp,
                    polity_id=pid,
                    group=group,
                    cut_year=a.year,
                    predicted="agree",
                    stated_p=min(1.0, max(1e-6, float(a.confidence))),
                    train_n=1,
                    year_from=a.year,
                    year_to=nxt.year,
                    meta={
                        "claimed_share": a.share,
                        "observed_share": nxt.share,
                        "tolerance_pp": tol,
                        "tolerance_level": level_bin(a.share),
                        "claiming_source": a.source_id,
                        "settling_source": nxt.source_id,
                    },
                )
            )
    return claims
