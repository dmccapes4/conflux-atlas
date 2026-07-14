# REPORT — Phase 2b: Connascence Layer + LLM Windowed Enrichment

**Date:** 14 July 2026  
**Branch:** `phase2b-connascence`  
**Implements:** [`STRATEGY_CONNASCENCE.md`](STRATEGY_CONNASCENCE.md) §5 steps 1–7  
**Artifacts:** `data-validation-reports/PHASE2B_{CONNASCENCE,TRUST,CLUSTERS,LLM_ENRICHMENT,LLM_LEDGER}.json`, `PHASE2B_{EDGES,LLM_EDGES}.jsonl`  
**Code:** `conflux/connascence.py`, `conflux/llm_enrich.py`, `scripts/run_phase2b_connascence.py`, `scripts/run_llm_enrichment.py`  
**Tests:** `tests/test_phase2b_connascence.py` (32), `tests/test_phase2b_llm.py` (8) — full suite 163 passed.

---

## 1. Method registry + graded settlement (§2.1) — the discount works, and mostly doesn't fire

377 corroboration claims settled with the independence discount (same method family → 0.5 Beta mass) and definitional routing (14 claims rerouted off `source_trust:*`):

| hypothesis | unweighted | weighted+routed | Δ | reading |
| --- | --- | --- | --- | --- |
| `source_trust:arab_barometer` | 0.729 | 0.729 | 0 | all corroborations cross-family — untouched, as expected |
| `source_trust:arda_national_profiles_2005` | 0.477 | 0.477 | 0 | its poor record is against *cross-family* settlers; not an artifact |
| `source_trust:cbs_population_madaf` | 0.667 | **0.750** | +0.083 | its Arab-proxy-vs-Pew losses were definition gaps, now quarantined |
| `source_trust:jewishdatabank_world_jewish_population` | 0.667 | **0.500** | −0.167 | its wins vs Pew were CJP-definition overlaps, not independent corroboration |
| `source_trust:pew...` | 0.700 | 0.688 | −0.012 | small same-family (WJP) discount |
| `definition_gap:cjp_vs_pew_jewish` | — | 0.800 | new | CJP and Pew usually agree within tolerance |
| `definition_gap:cbs_arab_proxy_vs_pew_muslim` | — | **0.167** | new | systematic definitional disagreement, correctly *not* charged to either source |

This is the §2.1–2.2 mechanism doing exactly what it was built for: WJP's trust was inflated by same-family/definition-overlap agreement (−0.167 once removed), and CBS was being unfairly drained by a proxy-definition mismatch (+0.083 once routed). The 0.167 on the CBS-Arab-proxy gap is a *finding*, not a failure — the proxy over-counts muslims by folding in Arab Christians and Druze, and the ledger now says so in its own lane.

## 2. Co-variance discovery (§2.3, §6.2) — honest result: no strict edges yet

Merged anchor+desk timeline (`desk_movement_events`), 3,852 scored cross-polity pairs, complement exclusion and bucket-stratified null active:

- **Raw α=0.05 tier: 4 edges** (jordan↔morocco muslim, algeria↔morocco muslim, france↔syria muslim, jordan-christian↔lebanon-muslim), best p=0.012 at n=7.
- **Shuffle control: 20 raw-α edges** — permuting outcomes within series produced *more* edges than the real data. At 3,852 candidate pairs and n=3–9 overlaps per pair, raw α admits noise faster than signal.
- **Benjamini–Hochberg FDR across all scored pairs: 0 survivors** (real *and* shuffled).

Consequence, wired into the code: co-variance now has two tiers. The **strict tier** (BH-FDR survivors) is the only tier `apply_partial_settlement` may consume — currently empty, so partial settlement correctly did nothing (0 bumps, by design rather than by accident). The **hypothesis tier** (raw-α, `fdr_pass: false` in meta) feeds clusters, the REVIEW queue, and the LLM attribution job only.

Why the 1948–72 Jewish positive control didn't appear: jewish shares in MENA polities are trace-level (<0.5%) in most desk years and are floored out by `MIN_SHARE`, and the anchor grid (1900/1950/2000/2010/2020) yields at most 2 overlapping transition pairs per polity pair — below any honest admission floor. **The bottleneck is data density, not the math.** Mid-century anchors (1930–1990) are now the highest-leverage ingest target.

## 3. Conservation claims (§2.2) — all abstained, for the same reason

10 migration edges produced 0 settleable claims: bracketing both polities' absolute counts within ±15 years of a 1948–51 edge needs anchors near mid-century, and the nearest are 1900/1950 (origin-side "before 1949" resolves to 1900, 49y gap → abstain). The machinery settles correctly on synthetic books (tests pass, including the violation case); it is waiting on the same mid-century ingest as §2.

## 4. Shock tagging (§2.4) — wired, empty at the 1975 cut

783 policy claims tagged; 0 fall in documented shock windows because post-1975 claim transitions (2000→2010→2020) don't overlap Iran 1979–85 and the 1948/1923 events pre-date the cut. Calm-side calibration reproduces Phase 2 (majority 0.663, persistence 0.667, reversion 0.611). The split becomes informative when earlier cuts or mid-century transitions enter the tape.

## 5. LLM windowed enrichment (§3) — the proposer earned 0.879, and every mistake was caught

`qwen3:8b` via local Ollama; 6 windows, 0 malformed. Per the correction adopted mid-build: **no Modelfile** — both agent jobs share one loaded base model, with the persona/hard-rules preamble travelling in each request's system prompt (a per-request system prompt overrides a Modelfile's anyway) and deterministic decoding (`temperature 0, top_p 1, top_k 1, repeat_penalty 1, seed 42`) sent as per-request options. Two agents, one tensor load.

**Job 1 — event attribution:** 3 hypothesis-tier clusters offered, **3 abstentions, 0 proposals.** Correct behavior: the clusters are post-1950 muslim-share growth co-movements; nothing in the closed event list (Lausanne 1923, 1948 war, Iran 1979) explains them, and abstention is free.

**Job 2 — conceptual coupling:** 56 candidates (real couplings + deliberate decoys), 56 proposals, **50 verified / 6 rejected → `llm_proposer:qwen3:8b` posterior 0.879 over 56 trials** (well above the 0.5 freeze line). The 6 failures are instructive:

- All 3 **no-edge decoys** (egypt↔turkey jewish, morocco↔iraq christian, iran↔yemen muslim) were mislabeled `complement` — the model pattern-matched "same group, different polity" into the wrong bucket. The verifier rejected every one; none became an edge.
- 2 pairs that **should** have been `conservation` (turkey↔greece christian, yemen↔israel jewish — both have documented edges) were also mislabeled `complement`. Rejected; cost the model posterior mass. A fair miss, honestly priced.
- 1 `definition` proposal (CBS vs Pew, israel-jewish 2020) failed the systematic-offset verifier — plausible but unproven; correctly rejected.

Verified edges materialized: 40 `concept:complement`, 8 `concept:conservation`, 2 `concept:definition` (`PHASE2B_LLM_EDGES.jsonl`). The §3 contract held end-to-end: proposals entered the ledger as claims, verifiers were the only promotion path, and the model now has a earned trust posterior sitting in the same ledger as ARDA and Pew.

## 6. What this changes

1. **Ledger corrections ship:** the weighted+routed posteriors (WJP −0.167, CBS +0.083, definition gaps in their own lanes) are the most defensible trust numbers the project has produced.
2. **Partial settlement stays dormant by arithmetic**, not by policy — it unlocks exactly when a co-variance edge survives FDR, which requires denser mid-century series.
3. **Next ingest priority is now quantitative:** anchors/observations 1930–1990 simultaneously unblock the co-variance positive control, conservation claims, and the shock-window calibration split. One ingest, three consumers.
4. **The proposer loop is production-shaped:** windowed, deterministic, schema-constrained, self-scoring. Scaling it means scaling candidates, not prompts.
