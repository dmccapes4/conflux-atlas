# Phase 2 Test Specification — Settlement & Trust

**Date:** 14 July 2026  
**Audience:** implementing agent (Grok) — review, then implement `conflux/learning.py` and `conflux/settlement.py` until `make test-phase2` is green.  
**Strategy anchor:** `STRATEGY_V0.2.md` §5 Phase 2 (settlement-gated trust, *not* anomaly detection).  
**Test files (the contract):** `tests/test_phase2_learning.py`, `tests/test_phase2_settlement.py`, `tests/test_phase2_source_trust.py`.  
**Builds on Phase 1 as merged:** `movement.build_catalog` / `CatalogRow` / `hash_outcome_table` are the substrate — do not modify them to make Phase 2 pass (flag spec bugs instead).

## 0. How these tests work

Same mechanism as Phase 1: `importorskip` keeps them skipped until the modules exist, then they join the default gate automatically.

```bash
make test-phase2     # phase2 contracts only, with skip reasons
make test            # full offline gate — must stay green throughout
```

Tests pin **mechanics** — settlement-only learning, temporal hygiene, exactly-once settlement, ledger↔posterior consistency, calibration math. They never pin accuracy or calibration *quality*: whether any policy or source earns trust on real data is the Phase 2 research result and goes in `docs/REPORT_PHASE2_TRUST.md`. If a contract seems wrong, change spec + test in the same commit with a note — never code around them.

This phase is the project's center of gravity: *"nobody keeps score on demography"* — these two modules are the scorekeeper.

---

## 1. `conflux/learning.py`

Near-verbatim port of `2OPMD/2ndOpinionMD/ptv-embed-lab/ptv_embed/learning.py` (nakatomi lineage). Read that file first; keep its shape. Two deliberate departures: `Prediction` is renamed/refit as a demographic `Claim`, and the store must **load** as well as save.

### 1.1 `Posterior` — frozen dataclass

Beta(α, β), uniform prior `Beta(1, 1)`, `trials` counter. Properties `mean`, `variance`; method `bumped(success) -> Posterior` returning a **new** object (immutability is tested: bumping a copy must not disturb the original). Port as-is.

### 1.2 `Claim` — mutable dataclass

One falsifiable statement, made at a cut, settled later:

| Field | Type | Notes |
| --- | --- | --- |
| `claim_id` | str | unique, **deterministic** from content (idempotent reruns must not mint duplicates) |
| `hypothesis_id` | str | namespaced key: `policy:<name>` or `source_trust:<source_id>` |
| `polity_id`, `group` | str | what the claim is about |
| `cut_year` | int | knowledge-freeze year |
| `predicted` | str | direction label for policy claims; band label for corroboration claims |
| `stated_p` | float | claimed probability ∈ (0, 1] — feeds calibration |
| `train_n` | int | how much training evidence backed the claim |
| `year_from`, `year_to` | int | the transition being claimed (policy claims) |
| `made_at`, `settled`, `success`, `settled_at` | | lifecycle, as in the ptv original |
| `meta` | dict | free-form (corroboration claims stash claimed/observed shares + tolerance here) |

### 1.3 `TrustStore`

`posteriors: dict[str, Posterior]`, `ledger: list[Claim]`. Methods `get / bump / record / settle / summary / save / load`.

Hard rules (each tested):

- **`get()` is read-only** — returns the uniform prior for unknown keys *without inserting* (phantom keys distort summaries).
- **`record()` never touches a posterior.** THE rule, verbatim from nakatomi: *nothing but a settled outcome may bump a posterior.* Making claims is free; being right isn't.
- **`settle(claim, success)`** marks the claim (settled/success/settled_at) and bumps its hypothesis. **Double settlement raises `ValueError`** — a settlement is a historical fact; double-bumps silently inflate trust.
- **`summary()`** sorted by posterior mean descending.
- **`save(path)` / `TrustStore.load(path)`** — full JSON roundtrip: posteriors (α, β, trials exact), ledger with settled *and unsettled* claims, and settlement facts enforced after reload (a claim settled before save must raise on re-settlement after load). The demographic tape spans years and processes; ptv's save-only store is not enough here.

---

## 2. `conflux/settlement.py`

Two claim families sharing the one store, plus calibration math and the report writer.

### 2.1 Policy claims — the 1975-cut miniature

`make_policy_claims(catalog, *, cut_year, min_bucket_n) -> list[Claim]`

The temporal analogue of the Phase 1 LOPO scorecard, and the dress rehearsal for the North-Star protocol:

- **Train** = transitions with `year_to <= cut_year`. Fit the hash table (`hash_outcome_table(train, min_n=min_bucket_n)`) and the majority distribution from train only.
- **Claim** = transitions with `year_from >= cut_year`, one claim per (policy × transition) where the policy can speak.
- **Straddlers** (`year_from < cut_year < year_to`) are excluded from **both** sides — a straddling transition's outcome contains post-cut knowledge. (Tested with a 1950→2000 transition across a 1975 cut: zero claims.)
- **Parameter freeze vs feature availability:** learned tables (hash buckets, majority) are frozen at the cut; `reversion`/`persistence` may condition on the immediately preceding *observed* transition even when it post-dates the cut — by `year_from` that outcome has settled. This is standard walk-forward discipline: frozen parameters, current features. State it in the module docstring.
- **Abstention = no claim.** Thin hash bucket (`n < min_bucket_n`), no previous transition, empty training set → the policy stays silent. Never a filler guess; unmade claims are the honest record of what a policy could not say. (Tested: `min_bucket_n=10_000` → zero `hash_mode` claims while `majority` still speaks.)
- **`stated_p`** — suggestion, not pinned: bucket purity for `hash_mode`; train frequency of the predicted direction for `majority`; train frequency with which the reversion/persistence pattern held for those two. Only bounds are tested (∈ (0, 1]); pick something defensible and document it.
- **Deterministic, unique `claim_id`s** — same catalog + cut → byte-identical id list (e.g. hash of `hypothesis_id|polity|group|year_from|year_to|cut_year`).

`settle_policy_claims(claims, catalog, store) -> int`

Look up each claim's transition outcome in the catalog; `success = (predicted == outcome)`; `store.record` + `store.settle`; return number settled. Settlement **compares, never reinterprets**. Re-settling the same claims raises (via the store) and must not move trials. After settlement, per-hypothesis invariant: `posterior.trials == number of settled claims for that hypothesis`, `alpha == 1 + successes`, `beta == 1 + failures` — the ledger and the posteriors never disagree.

### 2.2 Corroboration claims — `source_trust:*`

`make_corroboration_claims(anchors, *, group, tolerance_pp, max_gap_years) -> list[Claim]`  
`settle_corroboration_claims(claims, store) -> int`

The scorekeeper for sources: a source earns trust when a later, independent source lands within tolerance of its share claim.

For each anchor A (source S, polity P, year Y): find the **next** anchor on P from a **different** source within `max_gap_years`. If one exists, emit a claim keyed `source_trust:<S>` that its share for `group` will agree within `tolerance_pp`. Settlement: `success = |share_A − share_next| <= tolerance_pp`.

Rules (each tested):

- **No self-corroboration** — same-source pairs emit nothing; a source agreeing with itself is provenance, not evidence.
- **Next qualifying anchor, not best** — settling against a later agreeing anchor while skipping an intervening contradicting one is settlement shopping. (Tested: A@1950 → B@1960 contradicts → C@1970 agrees; A's claim must settle FALSE against B.)
- **`max_gap_years` cap** — beyond it, the world itself moved; disagreement stops being evidence about the source. (Tested: 1900 claim + 2020 anchor → no claim.)
- **No cross-polity settlement.**
- Multi-valued sources: use the anchor's **first** `source_ids` entry as S (document if you choose otherwise).
- Stash `claimed_share / observed_share / tolerance_pp / settling source` in `claim.meta` — the report reads it; tests don't.

### 2.3 Calibration math

`calibration_table(claims, *, bins) -> list[CalibrationRow]` — settled claims only; bin by `stated_p` with `p_lo <= p < p_hi` (last bin inclusive of 1.0); each returned row has `p_lo, p_hi, n > 0, stated_mean` (within the bin) and `observed` (success frequency ∈ [0, 1]); empty bins are omitted; every settled claim lands in exactly one bin (row `n`s sum to the settled count).

`brier_score(claims) -> float` — mean of `(stated_p − outcome)²` over settled claims, `outcome ∈ {0, 1}`. Pinned: perfect confident claims → 0.0, confidently wrong → 1.0, honest coin flips at 0.5 → 0.25.

### 2.4 `write_trust_report(store, claims, path)`

JSON milestone artifact with at least: `posteriors` (per hypothesis: alpha/beta/trials/mean), `calibration` (the table), `brier`. `docs/REPORT_PHASE2_TRUST.md` cites this file.

---

## 3. Integration smoke (real data)

`test_full_loop_on_real_demo_cohort` runs the canonical **1975 cut** end-to-end on the actual demo anchors: build catalog (muslim/christian/jewish) → policy claims → settle → posteriors move → store survives a save/load roundtrip. Mechanics only; with the Phase 1 scorecard showing majority at ~0.80 on this sparse tape, expect the posteriors to *reflect* that imbalance — report it, don't fight it.

---

## 4. Definition of done

1. `make test-phase2` green (0 skipped); `make test` green (Phases 0+1+2 together, no changes to earlier tests or processed data — if needed, stop and flag).
2. Run the real 1975-cut loop plus corroboration over the full anchor desk; write `data-validation-reports/PHASE2_TRUST.json` via `write_trust_report`.
3. `docs/REPORT_PHASE2_TRUST.md`: which policies earned trust, per-source posteriors (pew vs hand_seed vs wiki vs survey — the first real "who to believe" ledger), calibration table + Brier per family, and the sparsity caveats. **A poorly calibrated policy or an untrustworthy source is a result, not a failure.**
4. Do not wire PortalGC / provenance-engine into any of this — it stays an optional post-Phase-2 governance experiment (STRATEGY v0.2 §8.C).
