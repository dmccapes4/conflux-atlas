"""Contracts for the HMI window harness (HYPOTHESIS_HMI_WINDOWS.md).

The harness settles an adversarial hypothesis, so its own arithmetic must
be beyond suspicion: planted gold really planted, scoring exact, sampling
deterministic, the decision rule frozen.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("conflux.hmi_harness")

from conflux.hmi_harness import (  # noqa: E402
    CallTelemetry,
    aggregate_telemetry,
    build_pages,
    run_task_b,
    sample_pairs,
    score_extraction,
    select_best,
    strictify_schema,
)
from conflux.llm_enrich import PairCandidate  # noqa: E402


def _od_row(origin, dest, year, refugees, asylum=0):
    return {
        "origin_polity_id": origin,
        "dest_polity_id": dest,
        "year": year,
        "refugees": refugees,
        "asylum_seekers": asylum,
    }


OD_ROWS = [
    _od_row("syria", "turkey", 2015, 2_503_549, asylum=133_281),
    _od_row("syria", "lebanon", 2015, 1_070_854),
    _od_row("syria", "jordan", 2015, 628_887, asylum=25_000),
    _od_row("syria", "iraq", 2015, 244_642),
    _od_row("syria", "germany", 2015, 115_604, asylum=59_000),
    _od_row("syria", "egypt", 2015, 117_658),
]


# ---------------------------------------------------------------------------
# Synthetic corpus
# ---------------------------------------------------------------------------


class TestBuildPages:
    def test_gold_planted_and_deterministic(self):
        a = build_pages(OD_ROWS, n_pages=2, facts_per_page=3)
        b = build_pages(OD_ROWS, n_pages=2, facts_per_page=3)
        assert [p.text for p in a] == [p.text for p in b]
        assert sum(len(p.gold) for p in a) == 6
        # every gold tuple's number appears verbatim (with separators) on its page
        for page in a:
            for origin, dest, year, refugees in page.gold:
                assert f"{refugees:,}" in page.text
                assert str(year) in page.text

    def test_zero_refugee_rows_excluded(self):
        rows = OD_ROWS + [_od_row("syria", "qatar", 2015, 0)]
        pages = build_pages(rows, n_pages=3, facts_per_page=3)
        gold = {g for p in pages for g in p.gold}
        assert all(g[3] > 0 for g in gold)
        assert not any(g[1] == "qatar" for g in gold)

    def test_short_final_chunk_dropped_not_padded(self):
        pages = build_pages(OD_ROWS, n_pages=10, facts_per_page=4)
        # 6 rows / 4 per page -> exactly 1 full page; no ragged page
        assert len(pages) == 1
        assert len(pages[0].gold) == 4


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoreExtraction:
    def _pages(self):
        return build_pages(OD_ROWS, n_pages=2, facts_per_page=3)

    def test_perfect_extraction_scores_one(self):
        pages = self._pages()
        rows = [
            {"origin": o, "dest": d, "year": y, "refugees": r}
            for p in pages
            for (o, d, y, r) in p.gold
        ]
        s = score_extraction(rows, pages)
        assert s["f1"] == 1.0 and s["precision"] == 1.0 and s["recall"] == 1.0
        assert s["hallucinated"] == 0 and s["numeric_error"] == 0

    def test_numeric_error_vs_hallucination(self):
        pages = self._pages()
        o, d, y, r = pages[0].gold[0]
        rows = [
            {"origin": o, "dest": d, "year": y, "refugees": r + 1},  # wrong number
            {"origin": "mars", "dest": d, "year": y, "refugees": 5},  # invented
        ]
        s = score_extraction(rows, pages)
        assert s["numeric_error"] == 1
        assert s["hallucinated"] == 1
        assert s["tp"] == 0

    def test_duplicates_counted_once(self):
        pages = self._pages()
        o, d, y, r = pages[0].gold[0]
        row = {"origin": o, "dest": d, "year": y, "refugees": r}
        s = score_extraction([row, row, dict(row)], pages)
        assert s["tp"] == 1 and s["n_extracted"] == 1

    def test_asylum_distractor_extraction_costs(self):
        pages = self._pages()
        # the turkey row carries an asylum distractor; extracting it must cost
        s = score_extraction(
            [{"origin": "syria", "dest": "turkey", "year": 2015, "refugees": 133_281}],
            pages,
        )
        assert s["numeric_error"] == 1  # right entity key, wrong (non-refugee) figure


# ---------------------------------------------------------------------------
# Task B end-to-end with a fake client
# ---------------------------------------------------------------------------


class FakeClient:
    """Answers from an oracle mapping page_id -> rows; records telemetry."""

    def __init__(self, oracle, model="fake"):
        self.oracle = oracle
        self.model = model
        self.telemetry: list[CallTelemetry] = []

    def chat_json(self, system, user, schema):
        req = json.loads(user)
        rows = []
        for page in req["pages"]:
            rows.extend(self.oracle.get(page["page_id"], []))
        self.telemetry.append(
            CallTelemetry(latency_s=0.01, prompt_tokens=100, completion_tokens=20, ok=True)
        )
        return {"rows": rows}


class TestRunTaskB:
    def test_oracle_client_hits_f1_one_at_every_window(self):
        pages = build_pages(OD_ROWS, n_pages=2, facts_per_page=3)
        oracle = {
            p.page_id: [
                {"origin": o, "dest": d, "year": y, "refugees": r}
                for (o, d, y, r) in p.gold
            ]
            for p in pages
        }
        for w in (1, 2):
            client = FakeClient(oracle)
            out = run_task_b(client, pages, window_size=w)
            assert out["f1"] == 1.0
            assert out["windows_run"] == -(-len(pages) // w)
            assert out["telemetry"]["n_calls"] == out["windows_run"]
            assert out["tokens_per_gold_fact"] is not None

    def test_failed_window_counted_and_scored_as_misses(self):
        pages = build_pages(OD_ROWS, n_pages=2, facts_per_page=3)

        class NullClient(FakeClient):
            def chat_json(self, system, user, schema):
                self.telemetry.append(
                    CallTelemetry(
                        latency_s=0.01, prompt_tokens=100, completion_tokens=0, ok=False
                    )
                )
                return None

        out = run_task_b(NullClient({}), pages, window_size=1)
        assert out["windows_failed"] == len(pages)
        assert out["recall"] == 0.0 and out["f1"] == 0.0


# ---------------------------------------------------------------------------
# Pair sampling
# ---------------------------------------------------------------------------


def _pair(pid, fam):
    if fam == "conservation":
        kw = dict(source_a="*series*", source_b="*series*", polity_a="a", polity_b="b",
                  group_a="muslim", group_b="muslim")
    elif fam == "complement":
        kw = dict(source_a="s1", source_b="s1", polity_a="a", polity_b="a",
                  group_a="muslim", group_b="christian", year_a=2000, year_b=2000)
    else:
        kw = dict(source_a="s1", source_b="s2", polity_a="a", polity_b="a",
                  group_a="muslim", group_b="muslim", year_a=2000, year_b=2000)
    return PairCandidate(pair_id=pid, kind_hint={}, **kw)


class TestSamplePairs:
    def test_deterministic_and_capped(self):
        pairs = (
            [_pair(f"cons{i}", "conservation") for i in range(5)]
            + [_pair(f"comp{i}", "complement") for i in range(50)]
            + [_pair(f"defn{i}", "definition") for i in range(50)]
        )
        a = sample_pairs(pairs, 20)
        b = sample_pairs(list(reversed(pairs)), 20)
        assert [p.pair_id for p in a] == [p.pair_id for p in b]
        assert len(a) == 20

    def test_conservation_always_all_in(self):
        pairs = (
            [_pair(f"cons{i}", "conservation") for i in range(5)]
            + [_pair(f"comp{i}", "complement") for i in range(50)]
        )
        got = {p.pair_id for p in sample_pairs(pairs, 12)}
        assert {f"cons{i}" for i in range(5)} <= got


# ---------------------------------------------------------------------------
# OpenAI strict-mode schema transform
# ---------------------------------------------------------------------------


class TestStrictify:
    def test_objects_closed_and_fully_required_recursively(self):
        schema = {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
                        "required": ["a"],
                    },
                }
            },
            "required": ["rows"],
        }
        out = strictify_schema(schema)
        assert out["additionalProperties"] is False
        inner = out["properties"]["rows"]["items"]
        assert inner["additionalProperties"] is False
        assert sorted(inner["required"]) == ["a", "b"]
        # input untouched
        assert "additionalProperties" not in schema


# ---------------------------------------------------------------------------
# Decision rule
# ---------------------------------------------------------------------------


def _cell(task, model, w, primary, guard, tokens):
    c = {
        "task": task,
        "model": model,
        "window_size": w,
        "telemetry": {"total_tokens": tokens},
    }
    if task == "A_coupling":
        c.update(posterior_mean=primary, **{"yield": guard}, tokens_per_verified=tokens)
    else:
        c.update(f1=primary, recall=guard, tokens_per_gold_fact=tokens)
    return c


class TestSelectBest:
    def test_argmax_primary(self):
        cells = [
            _cell("A_coupling", "m", 1, 0.90, 0.5, 100),
            _cell("A_coupling", "m", 12, 0.80, 0.5, 50),
        ]
        assert select_best(cells, "A_coupling")["window_size"] == 1

    def test_guard_blocks_all_abstain_winner(self):
        cells = [
            _cell("A_coupling", "m", 1, 0.99, 0.01, 10),  # abstains everything
            _cell("A_coupling", "m", 12, 0.85, 0.50, 80),
        ]
        assert select_best(cells, "A_coupling")["window_size"] == 12

    def test_tiebreak_on_economy(self):
        cells = [
            _cell("B_extraction", "m", 3, 0.9, 0.9, 200),
            _cell("B_extraction", "m", 6, 0.9, 0.9, 120),
        ]
        assert select_best(cells, "B_extraction")["window_size"] == 6

    def test_empty_returns_none(self):
        assert select_best([], "A_coupling") is None


class TestTelemetryAggregate:
    def test_totals(self):
        calls = [
            CallTelemetry(latency_s=1.0, prompt_tokens=100, completion_tokens=10, ok=True),
            CallTelemetry(latency_s=3.0, prompt_tokens=200, completion_tokens=30, ok=True),
        ]
        agg = aggregate_telemetry(calls)
        assert agg["n_calls"] == 2
        assert agg["total_tokens"] == 340
        assert agg["mean_latency_s"] == 2.0

    def test_empty_safe(self):
        assert aggregate_telemetry([])["n_calls"] == 0
