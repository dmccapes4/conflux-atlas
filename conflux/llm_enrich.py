"""LLM windowed enrichment — heuristic management infrastructure (§3).

The model gets exactly two jobs, both constrained and verifier-backed:

  1. event attribution  — for a co-variance cluster, pick the documented
     event that explains it (closed vocabulary) or null;
  2. conceptual coupling — for a batched window of series pairs, propose
     complement / conservation / definition / null.

Protocol invariants (STRATEGY_CONNASCENCE.md §3):

  - deterministic decoding (temperature 0, top_k 1, fixed seed) set as
    per-request API options — both jobs share ONE base model, so the
    persona lives in a shared system-prompt preamble instead of a
    Modelfile (a custom Modelfile per agent would re-load identical
    tensors just to swap prompts);
  - JSON-schema-constrained output; malformed output is retried once,
    then dropped;
  - every accepted proposal is recorded as a ``Claim`` under
    ``llm_proposer:<model>`` and settled by the *deterministic verifier*
    — the model earns a trust posterior like any other source;
  - proposals NEVER materialize edges directly. ``verified_edges()`` is
    the only promotion path, and it re-runs the arithmetic.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

# progress(windows_done, windows_total, seconds_for_this_window)
ProgressFn = Callable[[int, int, float], None]

from .connascence import (
    ConnascenceEdge,
    CovarianceCluster,
    _claim_id,
    definition_overlap,
)
from .learning import Claim, TrustStore
from .observations import ShareObservation, level_tolerance
from .schema import Event, MigrationEdge

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_URL = "http://localhost:11434"
WINDOW_SIZE = 12  # pairs / clusters per prompt window

EVENT_SLACK_YEARS = 5

# Deterministic decoding — sent as per-request options so both agents share
# one loaded model (no Modelfile; identical parameters, different prompts).
DECODE_OPTIONS: dict[str, Any] = {
    "temperature": 0.0,
    "top_p": 1.0,
    "top_k": 1,
    "repeat_penalty": 1.0,
    "seed": 42,
    "num_ctx": 8192,
}

# Shared persona preamble — prepended to each job's system prompt. This is
# the contract the Modelfile SYSTEM would have carried; per-request system
# prompts override a Modelfile's, so it must travel with the request.
_BASE_SYSTEM = """You are the Conflux Atlas connascence enrichment proposer. \
You classify relationships between pieces of demographic evidence.

Hard rules:
- Output valid JSON only. No prose, no markdown, no thinking text.
- Choose only from the closed vocabularies given in each request. Never \
invent identifiers.
- When no option clearly applies, answer null. Abstaining is always \
acceptable; guessing is not.
- Your proposals are scored against deterministic verifiers and your \
accuracy is tracked in a trust ledger. A wrong proposal is worse than no \
proposal.

"""

_EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "attributions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cluster_id": {"type": "string"},
                    "event_id": {"type": ["string", "null"]},
                    "rationale": {"type": "string"},
                },
                "required": ["cluster_id", "event_id", "rationale"],
            },
        }
    },
    "required": ["attributions"],
}

_COUPLING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pair_id": {"type": "string"},
                    "kind": {
                        "type": ["string", "null"],
                        "enum": ["complement", "conservation", "definition", None],
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["pair_id", "kind", "rationale"],
            },
        }
    },
    "required": ["proposals"],
}


# ---------------------------------------------------------------------------
# Ollama client (stdlib only)
# ---------------------------------------------------------------------------


class OllamaClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_URL,
        timeout: float = 300.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def available(self) -> bool:
        try:
            self._post("/api/show", {"model": self.model})
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            return False

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any] | None:
        """One structured call; retry malformed output once, then None.

        The shared persona travels with every request (per-request system
        prompts override any Modelfile SYSTEM, so nothing may live only
        there), and decoding is pinned deterministic via options.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _BASE_SYSTEM + system},
                {"role": "user", "content": user},
            ],
            "format": schema,
            "stream": False,
            "think": False,  # qwen3: suppress thinking tokens
            "options": dict(DECODE_OPTIONS),
        }
        for attempt in (1, 2):
            try:
                resp = self._post("/api/chat", payload)
            except urllib.error.HTTPError:
                if attempt == 1:
                    # older ollama rejects "think" — drop it and retry
                    payload.pop("think", None)
                    continue
                return None
            except (urllib.error.URLError, OSError):
                return None
            content = (resp.get("message") or {}).get("content", "")
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                continue
        return None


# ---------------------------------------------------------------------------
# Job 1 — event attribution for co-variance clusters
# ---------------------------------------------------------------------------

_EVENT_SYSTEM = """Job: event attribution. You are given clusters (groups of \
country-religion series that moved together in a window) and a CLOSED list of \
documented events. For each cluster pick the single event_id that best \
explains the co-movement, or null if none plausibly does. One sentence of \
rationale."""


def _cluster_prompt(
    clusters: Sequence[CovarianceCluster], events: Sequence[Event]
) -> str:
    ev = [
        {
            "event_id": e.event_id,
            "year": e.year,
            "year_end": e.year_end,
            "title": e.title,
            "affected_polities": e.affected_polities,
        }
        for e in events
    ]
    cl = [
        {
            "cluster_id": c.cluster_id,
            "series": c.series,
            "window": [c.year_min, c.year_max],
            "dominant_direction": c.dominant_direction,
        }
        for c in clusters
    ]
    return json.dumps({"documented_events": ev, "clusters": cl}, ensure_ascii=False)


def verify_event_attribution(
    cluster: CovarianceCluster,
    event: Event,
    migration_edges: Sequence[MigrationEdge],
) -> bool:
    """Deterministic verifier: window overlap ±slack AND polity contact."""
    e_end = event.year_end if event.year_end is not None else event.year
    if not (
        cluster.year_min - EVENT_SLACK_YEARS <= e_end
        and event.year <= cluster.year_max + EVENT_SLACK_YEARS
    ):
        return False
    cluster_polities = {s.split("|")[1] for s in cluster.series}
    if cluster_polities & set(event.affected_polities):
        return True
    for me in migration_edges:
        if me.trigger_event_id == event.event_id and (
            me.from_polity in cluster_polities or me.to_polity in cluster_polities
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Job 2 — conceptual coupling proposals
# ---------------------------------------------------------------------------

_COUPLING_SYSTEM = """Job: conceptual coupling. Classify pairs of demographic \
evidence series into connascence couplings. kinds: "complement" (same polity, \
same year, different religion groups measured by one source — shares sum to \
1), "conservation" (same religion group in two different polities linked by a \
documented migration flow), "definition" (two sources measuring the same \
group under systematically different definitions, e.g. a core-population \
count vs a broad affiliation estimate), or null (no definitional coupling — \
mere similarity does not count)."""


@dataclass(frozen=True)
class PairCandidate:
    pair_id: str
    kind_hint: dict[str, Any]  # metadata shown to the model
    # verifier inputs
    polity_a: str
    polity_b: str
    group_a: str
    group_b: str
    source_a: str
    source_b: str
    year_a: int | None = None
    year_b: int | None = None


def _pair_prompt(pairs: Sequence[PairCandidate]) -> str:
    return json.dumps(
        {"pairs": [{"pair_id": p.pair_id, **p.kind_hint} for p in pairs]},
        ensure_ascii=False,
    )


def verify_coupling(
    pair: PairCandidate,
    kind: str,
    migration_edges: Sequence[MigrationEdge],
    observations: Sequence[ShareObservation],
) -> bool:
    """Deterministic verifier per proposed kind (§3 table)."""
    if kind == "complement":
        return (
            pair.polity_a == pair.polity_b
            and pair.group_a != pair.group_b
            and pair.source_a == pair.source_b
            and pair.year_a is not None
            and pair.year_a == pair.year_b
        )
    if kind == "conservation":
        if pair.group_a != pair.group_b or pair.polity_a == pair.polity_b:
            return False
        for me in migration_edges:
            if me.group.value == pair.group_a and {me.from_polity, me.to_polity} == {
                pair.polity_a,
                pair.polity_b,
            }:
                return True
        return False
    if kind == "definition":
        if pair.group_a != pair.group_b or pair.source_a == pair.source_b:
            return False
        # Registry hit is sufficient…
        if definition_overlap(pair.source_a, pair.source_b, pair.group_a) is not None:
            return True
        # …else require a systematic signed offset in overlapping years.
        return _systematic_offset(pair, observations)
    return False


def _systematic_offset(
    pair: PairCandidate, observations: Sequence[ShareObservation]
) -> bool:
    """Same polity-year pairs from the two sources show a one-sided gap."""
    a = {
        (o.polity_id, o.year): o.share
        for o in observations
        if o.source_id == pair.source_a and o.group == pair.group_a
    }
    diffs: list[float] = []
    for o in observations:
        if o.source_id != pair.source_b or o.group != pair.group_b:
            continue
        ref = a.get((o.polity_id, o.year))
        if ref is None:
            continue
        diffs.append(ref - o.share)
    if len(diffs) < 3:
        return False
    beyond = [d for d in diffs if abs(d) > level_tolerance(abs(d))]
    if len(beyond) < 3:
        return False
    pos = sum(1 for d in beyond if d > 0)
    return max(pos, len(beyond) - pos) / len(beyond) >= 0.8


# ---------------------------------------------------------------------------
# Windowed runner — proposals as claims
# ---------------------------------------------------------------------------


@dataclass
class EnrichmentResult:
    model: str
    windows_run: int = 0
    windows_failed: int = 0
    proposals: int = 0
    verified: int = 0
    rejected: int = 0
    abstained: int = 0  # null answers — free by design, but worth seeing
    verified_event_edges: list[dict[str, Any]] = field(default_factory=list)
    verified_coupling_edges: list[ConnascenceEdge] = field(default_factory=list)


def _windows(items: Sequence[Any], size: int) -> list[Sequence[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def enrich_event_attribution(
    client: OllamaClient,
    clusters: Sequence[CovarianceCluster],
    events: Sequence[Event],
    migration_edges: Sequence[MigrationEdge],
    store: TrustStore,
    result: EnrichmentResult,
    *,
    window_size: int = WINDOW_SIZE,
    progress: ProgressFn | None = None,
) -> None:
    events_by_id = {e.event_id: e for e in events}
    clusters_by_id = {c.cluster_id: c for c in clusters}
    hyp = f"llm_proposer:{client.model}"

    windows = _windows(list(clusters), window_size)
    for i, window in enumerate(windows):
        t0 = time.monotonic()
        out = client.chat_json(_EVENT_SYSTEM, _cluster_prompt(window, events), _EVENT_SCHEMA)
        result.windows_run += 1
        if progress is not None:
            progress(i + 1, len(windows), time.monotonic() - t0)
        if out is None:
            result.windows_failed += 1
            continue
        for row in out.get("attributions", []):
            c = clusters_by_id.get(str(row.get("cluster_id", "")))
            if c is None:
                continue
            eid = row.get("event_id")
            if eid is None:
                result.abstained += 1
                continue  # abstention: no claim, no penalty, no credit
            ev = events_by_id.get(str(eid))
            result.proposals += 1
            claim = Claim(
                claim_id=_claim_id("llm_event", client.model, c.cluster_id, str(eid)),
                hypothesis_id=hyp,
                polity_id="*",
                group="*",
                cut_year=c.year_min,
                predicted=f"event:{eid}",
                stated_p=0.5,
                train_n=1,
                year_from=c.year_min,
                year_to=c.year_max,
                meta={
                    "job": "event_attribution",
                    "cluster_id": c.cluster_id,
                    "series": c.series,
                    "rationale": str(row.get("rationale", ""))[:300],
                },
            )
            ok = ev is not None and verify_event_attribution(c, ev, migration_edges)
            store.record(claim)
            store.settle(claim, success=ok)
            if ok:
                result.verified += 1
                result.verified_event_edges.append(
                    {
                        "cluster_id": c.cluster_id,
                        "event_id": eid,
                        "series": c.series,
                        "window": [c.year_min, c.year_max],
                        "proposer": client.model,
                    }
                )
            else:
                result.rejected += 1


def enrich_conceptual_couplings(
    client: OllamaClient,
    pairs: Sequence[PairCandidate],
    migration_edges: Sequence[MigrationEdge],
    observations: Sequence[ShareObservation],
    store: TrustStore,
    result: EnrichmentResult,
    *,
    window_size: int = WINDOW_SIZE,
    progress: ProgressFn | None = None,
) -> None:
    pairs_by_id = {p.pair_id: p for p in pairs}
    hyp = f"llm_proposer:{client.model}"

    windows = _windows(list(pairs), window_size)
    for i, window in enumerate(windows):
        t0 = time.monotonic()
        out = client.chat_json(_COUPLING_SYSTEM, _pair_prompt(window), _COUPLING_SCHEMA)
        result.windows_run += 1
        if progress is not None:
            progress(i + 1, len(windows), time.monotonic() - t0)
        if out is None:
            result.windows_failed += 1
            continue
        for row in out.get("proposals", []):
            p = pairs_by_id.get(str(row.get("pair_id", "")))
            if p is None:
                continue  # unknown pair_id — not an abstention
            kind = row.get("kind")
            if kind is None:
                result.abstained += 1
                continue
            kind = str(kind)
            result.proposals += 1
            claim = Claim(
                claim_id=_claim_id("llm_coupling", client.model, p.pair_id, kind),
                hypothesis_id=hyp,
                polity_id=p.polity_a,
                group=p.group_a,
                cut_year=p.year_a or 0,
                predicted=f"coupling:{kind}",
                stated_p=0.5,
                train_n=1,
                meta={
                    "job": "conceptual_coupling",
                    "pair_id": p.pair_id,
                    "rationale": str(row.get("rationale", ""))[:300],
                },
            )
            ok = verify_coupling(p, kind, migration_edges, observations)
            store.record(claim)
            store.settle(claim, success=ok)
            if ok:
                result.verified += 1
                result.verified_coupling_edges.append(
                    ConnascenceEdge(
                        src=f"series|{p.polity_a}|{p.group_a}"
                        if p.year_a is None
                        else f"{p.source_a}|{p.polity_a}|{p.group_a}|{p.year_a}",
                        dst=f"series|{p.polity_b}|{p.group_b}"
                        if p.year_b is None
                        else f"{p.source_b}|{p.polity_b}|{p.group_b}|{p.year_b}",
                        kind=f"concept:{kind}",
                        strength=0.8,
                        meta={"proposer": client.model, "pair_id": p.pair_id},
                    )
                )
            else:
                result.rejected += 1
