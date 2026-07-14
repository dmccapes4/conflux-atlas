"""HMI window harness — instrument for HYPOTHESIS_HMI_WINDOWS.md.

Measures ingestion-window size x model effects on two deterministic-gold
tasks:

  Task A: the production conceptual-coupling job (verifier gold) run at
          varying window sizes with full per-call telemetry;
  Task B: typed evidence extraction from synthetic "report pages" built
          from real UNHCR OD rows (planted gold, exact scoring) — the
          shape the beacon-PDF forge needs.

Clients here mirror the production ``OllamaClient`` contract
(``chat_json(system, user, schema) -> dict | None``) but additionally
record per-call telemetry (latency, prompt/completion tokens, attempts)
so the token-economy hypothesis (H-W2) settles on billed numbers, not
vibes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Sequence

from .learning import TrustStore
from .llm_enrich import (
    _BASE_SYSTEM,
    _windows,
    DECODE_OPTIONS,
    EnrichmentResult,
    OllamaClient,
    PairCandidate,
    enrich_conceptual_couplings,
)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Completion cap. Correct answers for any window in this harness are a few
# hundred tokens; greedy decode on small models can fall into repeat loops
# and generate until the request timeout (observed: 300s on llama3.2:3b).
# A looping model should fail fast and pay as a malformed window.
MAX_COMPLETION_TOKENS = 2048


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


@dataclass
class CallTelemetry:
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    ok: bool  # parsed JSON came back
    attempts: int = 1


def aggregate_telemetry(calls: Sequence[CallTelemetry]) -> dict[str, Any]:
    if not calls:
        return {
            "n_calls": 0,
            "total_latency_s": 0.0,
            "mean_latency_s": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    lat = [c.latency_s for c in calls]
    pt = sum(c.prompt_tokens for c in calls)
    ct = sum(c.completion_tokens for c in calls)
    return {
        "n_calls": len(calls),
        "total_latency_s": round(sum(lat), 2),
        "mean_latency_s": round(sum(lat) / len(lat), 3),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
    }


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


class OllamaHarnessClient(OllamaClient):
    """Production client + per-call telemetry from ollama's eval counts."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.telemetry: list[CallTelemetry] = []

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _BASE_SYSTEM + system},
                {"role": "user", "content": user},
            ],
            "format": schema,
            "stream": False,
            "think": False,
            "options": {**DECODE_OPTIONS, "num_predict": MAX_COMPLETION_TOKENS},
        }
        t0 = time.monotonic()
        prompt_tokens = completion_tokens = 0
        parsed: dict[str, Any] | None = None
        attempts = 0
        for attempt in (1, 2):
            attempts = attempt
            try:
                resp = self._post("/api/chat", payload)
            except urllib.error.HTTPError:
                if attempt == 1:
                    payload.pop("think", None)  # older ollama rejects "think"
                    continue
                break
            except (urllib.error.URLError, OSError):
                break
            prompt_tokens += int(resp.get("prompt_eval_count") or 0)
            completion_tokens += int(resp.get("eval_count") or 0)
            content = (resp.get("message") or {}).get("content", "")
            try:
                parsed = json.loads(content)
                break
            except json.JSONDecodeError:
                continue
        self.telemetry.append(
            CallTelemetry(
                latency_s=time.monotonic() - t0,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                ok=parsed is not None,
                attempts=attempts,
            )
        )
        return parsed


def strictify_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAI structured-output strict mode: every object closed + fully
    required. Returns a deep copy; the input schema is untouched."""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    out = copy.deepcopy(schema)
    walk(out)
    return out


class OpenAIHarnessClient:
    """Same ``chat_json`` contract against the OpenAI chat completions API.

    Deterministic decode pinned as far as the API allows (temperature 0,
    fixed seed); structured output enforced via strict json_schema.
    Token counts are as billed (``usage``), which is the operationally
    honest number for H-W2.
    """

    def __init__(
        self,
        model: str = "gpt-4.1",
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout
        self.telemetry: list[CallTelemetry] = []

    def available(self) -> bool:
        return bool(self.api_key)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            OPENAI_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any] | None:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _BASE_SYSTEM + system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "seed": int(DECODE_OPTIONS.get("seed", 42)),
            "max_tokens": MAX_COMPLETION_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "harness_out",
                    "strict": True,
                    "schema": strictify_schema(schema),
                },
            },
        }
        t0 = time.monotonic()
        prompt_tokens = completion_tokens = 0
        parsed: dict[str, Any] | None = None
        attempts = 0
        for attempt in (1, 2):
            attempts = attempt
            try:
                resp = self._post(payload)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                if attempt == 1:
                    time.sleep(2.0)
                    continue
                break
            usage = resp.get("usage") or {}
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
            completion_tokens += int(usage.get("completion_tokens") or 0)
            choices = resp.get("choices") or [{}]
            content = (choices[0].get("message") or {}).get("content", "") or ""
            try:
                parsed = json.loads(content)
                break
            except json.JSONDecodeError:
                continue
        self.telemetry.append(
            CallTelemetry(
                latency_s=time.monotonic() - t0,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                ok=parsed is not None,
                attempts=attempts,
            )
        )
        return parsed


# ---------------------------------------------------------------------------
# Task A — coupling classification at varying windows (verifier gold)
# ---------------------------------------------------------------------------


def _pair_family(p: PairCandidate) -> str:
    if p.source_a == "*series*":
        return "conservation"
    if p.source_a == p.source_b:
        return "complement"
    return "definition"


def sample_pairs(pairs: Sequence[PairCandidate], limit: int) -> list[PairCandidate]:
    """Deterministic, family-stratified sample — identical across cells.

    Conservation candidates are few and load-bearing (they include the
    decoys); they are always all included. The remainder splits evenly
    between complement and definition, each ordered by sha1(pair_id).
    """
    by_family: dict[str, list[PairCandidate]] = {
        "complement": [],
        "conservation": [],
        "definition": [],
    }
    for p in pairs:
        by_family[_pair_family(p)].append(p)
    for fam in by_family:
        by_family[fam].sort(
            key=lambda p: hashlib.sha1(p.pair_id.encode("utf-8")).hexdigest()
        )
    out = list(by_family["conservation"])
    remaining = max(0, limit - len(out))
    half = remaining // 2
    out += by_family["complement"][: remaining - half]
    out += by_family["definition"][:half]
    out.sort(key=lambda p: hashlib.sha1(p.pair_id.encode("utf-8")).hexdigest())
    return out[:limit] if len(out) > limit else out


def run_task_a(
    client: Any,
    pairs: Sequence[PairCandidate],
    migration_edges: Sequence[Any],
    observations: Sequence[Any],
    *,
    window_size: int,
    progress: Any = None,
) -> dict[str, Any]:
    tel_start = len(client.telemetry)
    store = TrustStore()
    result = EnrichmentResult(model=client.model)
    enrich_conceptual_couplings(
        client,
        pairs,
        migration_edges,
        observations,
        store,
        result,
        window_size=window_size,
        progress=progress,
    )
    calls = client.telemetry[tel_start:]
    tel = aggregate_telemetry(calls)
    p, v = result.proposals, result.verified
    metrics = {
        "task": "A_coupling",
        "window_size": window_size,
        "n_candidates": len(pairs),
        "windows_run": result.windows_run,
        "windows_failed": result.windows_failed,
        "proposals": p,
        "verified": v,
        "rejected": result.rejected,
        "abstained": result.abstained,
        "posterior_mean": round((v + 1) / (p + 2), 4),
        "precision": round(v / p, 4) if p else None,
        "yield": round(v / len(pairs), 4) if pairs else None,
        "telemetry": tel,
        "tokens_per_verified": round(tel["total_tokens"] / v, 1) if v else None,
    }
    return metrics


# ---------------------------------------------------------------------------
# Task B — typed extraction from synthetic report pages (planted gold)
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """Job: typed evidence extraction. You are given numbered \
report pages describing refugee populations. Extract every explicitly stated \
registered-refugee stock as a row {origin, dest, year, refugees}. origin and \
dest must be polity ids from the closed list provided in the request. \
Extract registered refugee stocks ONLY — ignore asylum-seeker counts and any \
other figures. Never infer facts that are not stated on a page."""

_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "dest": {"type": "string"},
                    "year": {"type": "integer"},
                    "refugees": {"type": "integer"},
                },
                "required": ["origin", "dest", "year", "refugees"],
            },
        }
    },
    "required": ["rows"],
}

# Deterministic phrasing rotation — index by fact ordinal, not RNG, so the
# corpus is stable across runs and machines.
_FACT_TEMPLATES = [
    (
        "By the end of {year}, {dest_t} hosted {refugees:,} registered "
        "refugees from {origin_t}."
    ),
    (
        "UNHCR registration data for {year} records {refugees:,} refugees "
        "originating from {origin_t} present in {dest_t}."
    ),
    (
        "The {origin_t}-origin registered refugee stock in {dest_t} stood "
        "at {refugees:,} persons in {year}."
    ),
]
_DISTRACTOR_TEMPLATE = (
    " A further {asylum:,} asylum seekers from {origin_t} had claims "
    "pending in {dest_t} that year."
)


def _title(polity_id: str) -> str:
    return polity_id.replace("_", " ").title()


@dataclass(frozen=True)
class SyntheticPage:
    page_id: str
    text: str
    gold: tuple[tuple[str, str, int, int], ...]  # (origin, dest, year, refugees)


def build_pages(
    od_rows: Sequence[dict[str, Any]],
    *,
    n_pages: int,
    facts_per_page: int,
) -> list[SyntheticPage]:
    """Render real OD rows into synthetic report pages with planted gold.

    Rows are ordered by sha1 of their identity for a stable, shuffled-
    looking corpus. Asylum-seeker figures ride along as distractors the
    extractor must NOT emit.
    """
    rows = sorted(
        od_rows,
        key=lambda r: hashlib.sha1(
            f"{r['origin_polity_id']}|{r['dest_polity_id']}|{r['year']}".encode()
        ).hexdigest(),
    )
    rows = [r for r in rows if int(r.get("refugees") or 0) > 0]
    pages: list[SyntheticPage] = []
    i = 0
    for pnum in range(n_pages):
        chunk = rows[i : i + facts_per_page]
        if len(chunk) < facts_per_page:
            break
        i += facts_per_page
        sentences: list[str] = []
        gold: list[tuple[str, str, int, int]] = []
        for j, r in enumerate(chunk):
            origin = r["origin_polity_id"]
            dest = r["dest_polity_id"]
            year = int(r["year"])
            refugees = int(r["refugees"])
            tpl = _FACT_TEMPLATES[(i + j) % len(_FACT_TEMPLATES)]
            s = tpl.format(
                year=year,
                refugees=refugees,
                origin_t=_title(origin),
                dest_t=_title(dest),
            )
            asylum = int(r.get("asylum_seekers") or 0)
            if asylum > 0 and (i + j) % 2 == 0:
                s += _DISTRACTOR_TEMPLATE.format(
                    asylum=asylum, origin_t=_title(origin), dest_t=_title(dest)
                )
            sentences.append(s)
            gold.append((origin, dest, year, refugees))
        pages.append(
            SyntheticPage(
                page_id=f"page_{pnum:03d}",
                text=" ".join(sentences),
                gold=tuple(gold),
            )
        )
    return pages


def _pages_prompt(pages: Sequence[SyntheticPage], polity_ids: Sequence[str]) -> str:
    return json.dumps(
        {
            "polity_ids": sorted(polity_ids),
            "pages": [{"page_id": p.page_id, "text": p.text} for p in pages],
        },
        ensure_ascii=False,
    )


def score_extraction(
    extracted: Sequence[dict[str, Any]], pages: Sequence[SyntheticPage]
) -> dict[str, Any]:
    gold: set[tuple[str, str, int, int]] = set()
    gold_keys: set[tuple[str, str, int]] = set()
    for p in pages:
        for g in p.gold:
            gold.add(g)
            gold_keys.add(g[:3])
    seen: set[tuple[str, str, int, int]] = set()
    tp = numeric_error = hallucinated = 0
    for row in extracted:
        try:
            tup = (
                str(row["origin"]).strip().lower(),
                str(row["dest"]).strip().lower(),
                int(row["year"]),
                int(row["refugees"]),
            )
        except (KeyError, TypeError, ValueError):
            hallucinated += 1
            continue
        if tup in seen:
            continue  # duplicates neither help nor hurt twice
        seen.add(tup)
        if tup in gold:
            tp += 1
        elif tup[:3] in gold_keys:
            numeric_error += 1
        else:
            hallucinated += 1
    n_extracted = len(seen)
    precision = tp / n_extracted if n_extracted else None
    recall = tp / len(gold) if gold else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall and (precision + recall) > 0
        else 0.0
    )
    return {
        "n_gold": len(gold),
        "n_extracted": n_extracted,
        "tp": tp,
        "numeric_error": numeric_error,
        "hallucinated": hallucinated,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4),
    }


def run_task_b(
    client: Any,
    pages: Sequence[SyntheticPage],
    *,
    window_size: int,
    progress: Any = None,
) -> dict[str, Any]:
    polity_ids = sorted(
        {g[0] for p in pages for g in p.gold} | {g[1] for p in pages for g in p.gold}
    )
    tel_start = len(client.telemetry)
    extracted: list[dict[str, Any]] = []
    windows = _windows(list(pages), window_size)
    windows_failed = 0
    for i, window in enumerate(windows):
        t0 = time.monotonic()
        out = client.chat_json(
            _EXTRACT_SYSTEM, _pages_prompt(window, polity_ids), _EXTRACT_SCHEMA
        )
        if progress is not None:
            progress(i + 1, len(windows), time.monotonic() - t0)
        if out is None:
            windows_failed += 1
            continue
        rows = out.get("rows")
        if isinstance(rows, list):
            extracted.extend(r for r in rows if isinstance(r, dict))
    calls = client.telemetry[tel_start:]
    tel = aggregate_telemetry(calls)
    score = score_extraction(extracted, pages)
    score.update(
        {
            "task": "B_extraction",
            "window_size": window_size,
            "n_pages": len(pages),
            "windows_run": len(windows),
            "windows_failed": windows_failed,
            "telemetry": tel,
            "tokens_per_gold_fact": (
                round(tel["total_tokens"] / score["n_gold"], 1)
                if score["n_gold"]
                else None
            ),
        }
    )
    return score


# ---------------------------------------------------------------------------
# Decision rule (frozen in HYPOTHESIS_HMI_WINDOWS.md §3)
# ---------------------------------------------------------------------------


def select_best(cells: Sequence[dict[str, Any]], task: str) -> dict[str, Any] | None:
    """Best cell for a task: argmax primary metric, tie-break lower tokens
    per verified item / gold fact, guard >= half the best guard."""
    primary_key = "posterior_mean" if task == "A_coupling" else "f1"
    guard_key = "yield" if task == "A_coupling" else "recall"
    econ_key = "tokens_per_verified" if task == "A_coupling" else "tokens_per_gold_fact"
    rows = [c for c in cells if c.get("task") == task and c.get(primary_key) is not None]
    if not rows:
        return None
    best_guard = max((r.get(guard_key) or 0.0) for r in rows)
    eligible = [r for r in rows if (r.get(guard_key) or 0.0) >= best_guard / 2]
    eligible.sort(
        key=lambda r: (
            -(r.get(primary_key) or 0.0),
            r.get(econ_key) if r.get(econ_key) is not None else float("inf"),
        )
    )
    return eligible[0] if eligible else None
