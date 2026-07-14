# Phase 1 Test Specification — Movement Vectors & Retrieval

**Date:** 14 July 2026  
**Audience:** implementing agent (Grok) — review, then implement `conflux/movement.py` and `conflux/scorecard.py` until `make test-phase1` is green.  
**Strategy anchor:** `STRATEGY_V0.2.md` §5 Phase 1.  
**Test files (the contract):** `tests/test_phase1_movement.py`, `tests/test_phase1_retrieval.py`, `tests/test_phase1_scorecard.py`.

## 0. How these tests work

All three files start with `pytest.importorskip(...)`, so today they **skip** and the Phase 0 gate (`make test`) stays green. The moment `conflux/movement.py` exists they activate in the default gate automatically. While implementing, run:

```bash
make test-phase1     # phase1 contracts only, with skip reasons
make test            # full offline gate — must stay green throughout
```

Tests are **contracts, not research outcomes**. They pin determinism, invariants, honest sparsity handling, and no train/test leakage. They deliberately never assert "hash beats baseline" — whether it does is the Phase 1 *result* and goes in the milestone report. A miss is a result (STRATEGY north-star discipline).

If you believe a threshold or API choice below is wrong, don't silently code around it — change the spec **and** the test in the same commit, with a note. The spec and tests must never disagree.

---

## 1. `conflux/movement.py`

Port-and-retune of `ptv-embed-lab/ptv_embed/lab_movement.py`: same place/movement philosophy (discretize a node's *place*, catalog where moves from that place led), retuned from lab day-scale to demographic year/decade-scale. Do **not** port patient graph / connascence.

### 1.1 Bin functions (all total functions — any float in, exactly one bin out)

The unit of movement is **Δshare per decade** (`rate_per_decade = (share_to − share_from) / gap_years × 10`). Rates, never raw deltas, so a 1900→1950 transition is comparable with a 2010→2020 one.

| Function | Input | Bins (inclusive lower bound) |
| --- | --- | --- |
| `delta_bin(rate)` | Δshare/decade | `big_down` ≤ −0.05 < `down` ≤ −0.005 < `flat` < 0.005 ≤ `up` < 0.05 ≤ `big_up` |
| `gap_bin(years)` | anchor spacing | `close` ≤ 5 < `decade` ≤ 15 < `generation` ≤ 35 < `era` |
| `level_bin(share)` | share at origin | `trace` < 0.01 ≤ `minority` < 0.10 ≤ `significant` < 0.35 ≤ `plural` < 0.65 ≤ `majority` < 0.90 ≤ `dominant` |
| `vol_bin(vol)` | mean \|rate/decade\| of **prior** transitions | `None` → `na`; `calm` < 0.005 ≤ `drift` < 0.03 ≤ `turbulent` |

Threshold rationale: 0.005/decade ≈ 0.5 share-points per decade — under census noise, treated as flat. 0.05/decade = 5 points/decade — expulsion/exodus scale (Egypt's Jewish share 1948→1960 moved at this order). `gap_bin` describes *data density*, not dynamics — retrieval must be able to distinguish "flat across 100 sparse years" from "flat across 5 dense ones". `vol_bin` is **causal**: only transitions strictly before the origin anchor count; fewer than 2 prior transitions → `None` → `"na"` (mirrors the volatility discipline in the ptv hash catalog).

Exact boundary behavior is pinned by the parametrized tests — copy from them, not from prose.

### 1.2 `place_hash(level, delta, gap, vol) -> str`

Deterministic `"level|delta|gap|vol"` join. **No polity_id, no group in the signature** (a test inspects the signature): the hash describes a *place* in movement space, so retrieval can surface cross-polity analogies. Identity lives in catalog metadata.

### 1.3 `movement_events(anchors, group) -> list[MovementEvent]`

Consecutive-anchor transitions per polity for one religion group.

`MovementEvent` (dataclass or pydantic — your choice) must expose:
`polity_id, group, year_from, year_to, gap_years, share_from, share_to, delta, rate_per_decade, confidence, origin_hash`.

Rules (each has a dedicated test):

- **No interpolation.** k anchors → exactly k−1 events. Never fabricate annual steps (Phase 0 critique: sparse anchors must not pretend to be time series).
- **Input order irrelevant; polities independent.** Sort internally by (polity, year); never emit a transition spanning two polities.
- **Missing group = share 0.0**, not an error — minorities appearing/vanishing is movement we care about (e.g. `jewish` share going 0.02 → absent).
- **Same-year duplicates:** keep the higher-confidence anchor, drop the other. Never emit `gap_years == 0` (division by zero in the rate).
- **Weakest-link confidence:** `event.confidence = min(conf_from, conf_to)`. A movement claim is only as strong as its weaker endpoint.
- **`origin_hash`:** stamped from the *origin* place — `level_bin(share_from)`, `delta_bin(rate_per_decade)` of this transition, `gap_bin(gap_years)`, `vol_bin` over prior history (`"na"` for a series' first transition). This is what the scorecard conditions on.

### 1.4 `direction(rate) -> "up" | "down" | "flat"`

Same ±0.005 flat threshold as `delta_bin`. Used as the settlement label.

### 1.5 `place_vector(event, *, weighted=False) -> np.ndarray`

Fixed-length **float32**, **L2-normalized**, bitwise-deterministic vector for a place. Export the dimension as `PLACE_VECTOR_DIM` (module constant) — tests check shape against it so silent drift fails loudly.

Suggested blocks (exact composition is your call; the tests pin properties, not features): origin share level, rate/decade, gap (log-scaled), volatility, one-hot-ish bin encodings. Requirements that *are* pinned:

- Finite unit vector even on degenerate input (first transition, zero movement, century gap) — sparse series are the normal case, not the edge case.
- `weighted=True` incorporates `event.confidence`; `weighted=False` must not. Two events identical except confidence: unweighted vectors equal, weighted differ. This is the hook for the Phase 1 publishable ablation (confidence-weighted vs unweighted retrieval) — the tests require both variants exist, and stay silent on which is better.

### 1.6 `build_catalog(anchors, groups) -> list[CatalogRow]`

One row per movement event across all requested groups. Row fields: `polity_id, group, year_from, year_to, origin_hash, vector, outcome` where `outcome = direction(rate_per_decade)`. Vector-side identity rule again: polity/group are metadata beside the vector, never encoded in it.

### 1.7 `cosine_topk(query, matrix, k) -> (indices, scores)`

Plain numpy (matmul on normalized rows). No GPU, no index library — with ≤ a few thousand places this is milliseconds (STRATEGY: GPU is optional scaling, not Phase 1). Pinned: self-similarity ≈ 1.0 at rank 0, descending scores, scores ∈ [−1, 1], `k > len(catalog)` returns all rows without error.

### 1.8 `hash_outcome_table(catalog, min_n) -> dict[str, HashEntry]`

Group rows by `origin_hash`; per bucket: `n`, outcome distribution `dist` (sums to 1), `mode`, `purity = max(dist.values())`. Buckets with `n < min_n` are excluded — 1-sample buckets masquerading as knowledge was the ptv-embed-lab lesson (`--min-bucket-n`).

---

## 2. `conflux/scorecard.py`

The Phase 1 **milestone artifact**: does conditioning on origin place-hash predict transition direction better than dumb baselines?

### 2.1 `run_scorecard(catalog, *, min_bucket_n) -> ScorecardResult`

Evaluation protocol: **leave-one-polity-out** (STRATEGY Phase 2 critique: with ~4 snapshots per polity, leave-one-year-out is too fragile). For each polity P: train the hash table on all rows *except* P's, predict each of P's transitions, settle against the recorded `outcome`.

Policies — all four required, all scored on the **identical** holdout tape:

| Policy | Prediction for a held-out transition |
| --- | --- |
| `hash_mode` | mode of the origin-hash bucket in the training table; **abstain** (`predicted=None`) if bucket missing or `n < min_bucket_n` |
| `reversion` | opposite direction of the polity-group's previous transition (first transition: abstain) |
| `persistence` | same direction as the previous transition (first: abstain) |
| `majority` | global modal direction of the training rows |

`ScorecardResult` must expose: `n_transitions`, `policies: dict[str, PolicyScore]` with `accuracy` (over scored, non-abstained predictions), `n_scored`, `coverage` (scored ÷ eligible), and `predictions` (per-transition records with `polity_id, policy, predicted, actual`) — the leakage test reads these.

Hard rules (each has a test):

- **No leakage:** a polity's own rows never inform its `hash_mode` predictions. The test constructs a world where one polity moves up while all others move down; leakage is detected if the up-polity gets "up" predictions.
- **Abstention is honest:** below `min_bucket_n` the policy abstains, and abstentions surface as reduced `coverage` — never silently backfilled with a guess. Accuracy-on-scored + coverage together tell the real story (same partial-knowledge discipline as ptv bucket stats).
- **Fair comparison:** every policy is evaluated on the same settlement tape (`n_scored` identical across policies; abstained rows are excluded from all policies' accuracy denominators consistently — simplest implementation: score all policies only on transitions where *all* policies produced a prediction).

### 2.2 `write_report(result, path)`

JSON with `n_transitions`, `protocol: "leave_one_polity_out"`, and per-policy `{accuracy, n_scored, coverage}`. This file is what the Phase 1 milestone doc (`docs/REPORT_PHASE1_SCORECARD.md`, written after implementation) cites.

### 2.3 Real-data smoke

`test_scorecard_runs_on_real_demo_cohort` builds the catalog from the actual `anchors.jsonl` demo polities (via `ConfluxModel.anchors_by_polity`) across muslim/christian/jewish and requires ≥ 20 transitions and a well-formed result. It promises **nothing about accuracy** — with ~4 transitions per polity, expect weak signal and wide error bars; say so in the report.

---

## 3. Fixtures

`tests/conftest.py` provides `mk_anchor(polity_id, year, shares, *, confidence, pop)` — builds schema-valid `Anchor`s, folding any share remainder into `"other"` so the sum-to-1 validator passes. Use it; don't hand-roll anchor dicts in new tests.

---

## 4. Definition of done

1. `make test-phase1` → all phase1 tests pass (0 skipped).
2. `make test` → full offline gate green (Phase 0 + Phase 1 together).
3. No changes to Phase 0 tests or processed data needed to get there — if you find you need one, stop and flag it: that's a spec bug, not an implementation detail.
4. Generate the first real scorecard JSON into `data-validation-reports/` and summarize honestly in `docs/REPORT_PHASE1_SCORECARD.md` (accuracy + coverage per policy, sparsity caveats). Whether `hash_mode` beats `reversion` on 1900–2020 hand seeds is the interesting number either way — **report it, don't tune the tests to it**.
