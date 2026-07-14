# STRATEGY — Connascence for the Evidence Graph (Phase 2b)

**Date:** 14 July 2026  
**Status:** Design. Supersedes the spitball axis definitions discussed pre-draft; informed by the Phase 2.5 PortalGC findings (`REPORT_PHASE2_5_SOURCES_PORTALGC.md`).  
**Naming:** PortalGC was Phase 2a in retrospect; this enrichment program is **Phase 2b**.  
**Lineage:** FullMetalPacket (typed edges) → ptv-embed-lab (5-axis connascence, partial settlement) → provenance-engine (edge-weight vocabulary). We reuse the vocabulary, not the prior definitions — those were tuned to codebases and patient graphs, not to a multi-source evidence desk.

---

## 1. The admission rule

**An edge type exists only if it changes a decision made by a named consumer.**

Phase 2.5 proved the cost of ignoring this: PortalGC classification tracked graph *position*, not evidential quality. Every edge added without a consumer doesn't just do nothing — it actively distorts the one component that reads topology. So each axis below names its consumer, its computation, and its failure mode. No axis is admitted for completeness.

The organizing idea: connascence in an evidence graph encodes **shared fate** —

| Shared fate | Axis |
| --- | --- |
| would be **wrong together** (shared error modes) | STRUCTURAL |
| are **bound by accounting** (definitional coupling) | CONCEPTUAL |
| **move together** (shared drivers) | CO_VARIANCE |
| happened **under the same shock** | TEMPORAL |
| merely measured together | CO_OCCURRENCE — retired |

---

## 2. The axes, redefined

### 2.1 STRUCTURAL — shared methodology (consumer: corroboration independence)

**Rejected definition:** "same source." Same-source edges weld high-volume sources (ARDA: 700+ observations) into degree cliques that PortalGC keeps on frequency alone — volume laundered into keep-worthiness. Worse than useless.

**Adopted definition:** two observations whose sources share a **method family**, from a hand-curated registry (7 sources; a table, not a model):

| Method family | Sources |
| --- | --- |
| census/registry | `cbs_population_madaf`, `ottoman_demographics_wiki` (official census tables) |
| survey self-ID | `arab_barometer` |
| demographic synthesis | `pew_global_religious_composition_2010_2020`, `jewishdatabank_world_jewish_population` |
| WCD-derived | `arda_national_profiles_2005` |
| scholarly estimate | `mccarthy_armenian_pop_ottoman` (Karpat when extracted) |

**Consumer — inverted from the naive reading.** Structural edges never strengthen KEEP. They **discount corroboration independence**: a same-family settlement carries weight 0.5, cross-family 1.0 (graded settlement — fractional Beta bumps, the ARGYLE pattern from nakatomi). Rationale: sources sharing a derivation pipeline share error modes; their agreement is partially self-agreement. Today the ledger treats every distinct `source_id` as independent — this is its largest known bias after the tolerance fix.

**Failure mode:** over-splitting the registry until nothing is same-family (discount never fires) or under-splitting (everything discounted). Registry changes are reviewed like schema changes.

### 2.2 CONCEPTUAL — definitional coupling (consumer: conservation claims + settlement discounts)

**Rejected definition:** "they're all demographic changes." An edge that connects everything discriminates nothing.

**Adopted definition — three deterministic sub-kinds:**

1. **Complement** (`concept:complement`): observations of *different groups, same polity-year*. Shares sum to ~1; one group up forces the rest down. Pure accounting.
2. **Conservation** (`concept:conservation`): observations of the *same group across two polities joined by a migration edge* (from `edges.jsonl`). Egypt-jewish decline should reappear in Israel-jewish growth, within edge volume bands.
3. **Definition overlap** (`concept:definition`): same nominal group measured under different definitions — WJP core-Jewish vs Pew jewish, CBS Arab→muslim proxy vs Pew muslim. Systematic offset expected.

**Consumers:**

- **A new claim family, `conservation:*`** — when both ends of a migration edge have observations bracketing the edge window, claim that origin loss ≈ destination gain within the edge's volume band; settle deterministically. This makes cross-polity accounting errors *findable* and gives migration edges their first settlement tape.
- **Definitional discount in corroboration:** `concept:definition` pairs must not settle under plain level tolerance (CJP is deliberately narrower than Pew's jewish bucket). Either widen tolerance by a per-pair offset learned from history, or exclude and track as their own hypothesis (`definition_gap:wjp_vs_pew`).

**Failure mode:** treating definitional offsets as source failures (they'd unfairly drain trust) — this axis exists precisely to route those disagreements away from `source_trust:*`.

### 2.3 CO_VARIANCE — co-movement of series (consumer: hypotheses + partial settlement)

The highest-value axis, as suspected — with one trap that must be engineered out.

**Definition:** two (polity, group) series whose movement events **agree in direction across overlapping windows** beyond a null model. Computed from the Phase 1 catalog, no LLM:

- Pair transitions from the two series whose `[year_from, year_to]` windows overlap.
- Require ≥ 3 overlapping pairs and at least one series non-flat in each pair (flat-dominant series "co-vary" trivially — the Phase 1 class-imbalance lesson).
- Score sign agreement among moving pairs against the directional base rate (binomial); admit the edge above threshold, strength = agreement rate. The base rate must be **stratified by place-hash bucket**, not global — see §6.2.

**The trap:** complement pairs **anti-covary by arithmetic** (muslim vs christian in one polity). Any pair already joined by `concept:complement` is excluded from co-variance discovery — otherwise we rediscover accounting and call it dynamics.

**Consumers, in value order:**

1. **Hypothesis generation.** A co-movement *cluster* (≥ 3 series, same window, same direction) is a machine-generated hypothesis: "shared driver here." Jewish series across MENA 1948–1972 should reproduce as the canonical positive control.
2. **Partial settlement** — the ptv-embed-lab idea, finally landing: a pending claim on series A receives a *fractional* Beta bump (weight = co-variance strength × a global partial-settlement coefficient ≤ 0.25) when strongly co-varying series B settles. Capped so partial evidence can never outweigh direct settlement; every partial bump recorded in the ledger with its provenance.
3. **Shock detection** for Phase 3: sudden cluster-wide movement = regime marker.

**Failure mode:** partial settlement double-counting (A settles B partially, B settles A partially, repeat). Rule: partial bumps flow only from *directly settled* claims, never from partially settled ones — one hop, no cascades.

### 2.4 TEMPORAL — event-window membership (consumer: shock gating)

Succession edges (already in the portal graph) stay as weak topology. The *useful* temporal edge is new: **transition → documented Event** whose window overlaps (`events.jsonl`: Lausanne 1923, 1948 war, Iran 1979 — growing).

**Consumer:** **shock gating.** Policy claims on event-window transitions get `meta.shock=true`; calibration reports split calm/shock. Expectations: persistence should degrade during shocks, hash_mode's silence becomes explicable, and Phase 3 backtests can be scored both ways. Later: policies may *abstain* during known shocks — abstention is already first-class.

**Failure mode:** none serious — deterministic, cheap, and additive.

### 2.5 CO_OCCURRENCE — retired

The settlement system already exhaustively enumerates multi-source same-timeline pairs; "measured together" is the ledger with less information. Existing portal-graph edges remain for topology; no new ones are created and no consumer reads them. Removing an axis that costs more than it informs is a result of this analysis, not an omission.

---

## 3. The LLM's place — heuristic management infrastructure

**Criterion (project rule):** the model is used only where a judgment is *needed*, *constrained enough to be near-deterministic under structured inference*, and *checkable afterward*. Everything in §2 that could be computed was computed — registry, complements, conservation, co-variance math, event windows are all deterministic. That leaves exactly two jobs:

| Job | Input window | Output schema | Deterministic verifier |
| --- | --- | --- | --- |
| **Event attribution** | one co-variance cluster (series ids, window, direction) + the closed list of documented events | `{"cluster_id": …, "event_id": <known id or null>, "rationale": <1 sentence>}` | cluster window overlaps event year ±5; a migration edge consistent with the direction exists |
| **Conceptual-coupling proposals** | batched node metadata + source notes (10–20 pairs/window) | `{"pair": [obs_a, obs_b], "kind": "complement"\|"conservation"\|"definition"\|null}` | complement: same polity-year; conservation: migration edge exists; definition: systematic signed offset in history |

**Protocol (the "management" in heuristic management infrastructure):**

1. **Model:** `qwen3:8b` (first choice) or `llama3.1:8b-instruct` via local Ollama; temperature 0; JSON-schema-constrained output; malformed output rejected and retried once, then dropped.
2. **Windowed batches:** fixed-size windows over clusters/pairs; each window's prompt contains only that window's metadata plus the closed vocabulary — no open-ended context.
3. **Proposals are claims, never edges.** Every accepted output is recorded in the TrustStore under `llm_proposer:<model>`, settled by the deterministic verifier (or by later corroboration for definition proposals). **The model earns a trust posterior like any other source.** A proposer whose posterior sinks below 0.5 gets its pending proposals frozen.
4. **No direct writes.** Edges materialize only after verifier pass. The LLM can propose; only arithmetic can promote.

This is the same settlement discipline applied to the heuristic engine itself — the loop that keeps score now keeps score on its own helper.

---

## 4. What PortalGC gets (and doesn't)

Enriched edges flow into the portal graph as topology (CO_VARIANCE strength, conceptual couplings), which should make the REVIEW queue *smarter* — uncorroborated nodes inside strong co-variance clusters are more interesting to a human than isolated ones. The Phase 2.5 verdicts stand unchanged: **report-only, REVIEW-queue use, never trust signal, never data selection.** No same-source or same-method cliques are ever written into the portal graph (§2.1 rejected definition) — structural connascence lives in the *ledger weights*, not the topology.

---

## 5. Implementation order (each step has a consumer on day one)

1. **Method registry + graded corroboration weights** (§2.1) — one table, one multiplier in `settle_corroboration_claims`; immediately re-run the Phase 2.5 ledger and diff posteriors. *(Expected: AB and Pew barely move; ARDA may move once WCD self-similarity is discounted… in either direction — that's the point.)*
2. **Complement + definition edges and the definitional routing fix** (§2.2) — stops CJP-vs-Pew disagreements draining `source_trust:*`.
3. **Co-variance discovery with complement exclusion + bucket-stratified null model** (§2.3, §6.2), using place-vector similarity as the candidate shortlist (§6.3) — validate against the 1948–1972 Jewish-series positive control before any consumer reads it.
4. **Event-window tagging + calm/shock calibration split** (§2.4) — small; unblocks Phase 3 scoring design.
5. **Conservation claims** (§2.2) — needs 3's machinery for window pairing.
6. **Partial settlement** (§2.3, coefficient ≤ 0.25, one-hop rule) — only after 3 is validated.
7. **LLM proposer** (§3) — last, because everything before it is its verifier infrastructure.

Tests to pin at each step: registry totality (every source has exactly one family); discount arithmetic (same-family bump = 0.5); complement exclusion in co-variance; null-model floor (shuffled series admit ~0 edges); one-hop partial settlement (no cascades); LLM proposals never materialize edges without verifier pass; proposer posterior exists and moves only via settlement.

---

## 6. Place-hash vectors and connascence

The place-hash machinery exists (Phase 1, `conflux/movement.py`): `place_hash` discretizes a transition's origin into `level|delta|gap|vol`, `place_vector` embeds it in a 32-dim L2-normalized space, `cosine_topk` retrieves neighbors. The question: is representation similarity a connascence axis — possibly even STRUCTURAL, since the nodes represent movement?

### 6.1 Verdict: not an edge axis, and not structural

**Not structural.** STRUCTURAL (§2.1) means *shared measurement pipeline* — two observations that would be wrong together because they were *produced* the same way. Place-hash similarity means *similar measured content* — two transitions that landed in the same region of movement space. Christian decline in 1960s Egypt and a trace-share drift in 1990s Morocco can share a bucket with zero shared error mode, zero shared driver, zero accounting bond. Confusing "represented alike" with "coupled" is the representation/mechanism error, and it matters here because the two demand opposite treatments: shared pipeline *discounts* corroboration; similar content is at most a *hint* that coupling might exist.

**Not an edge axis at all**, on the §1 admission rule:

1. **No shared fate.** Similarity is symmetric, dense, and mechanism-free. Every axis in §2 answers "why would these be wrong/move together?"; similarity answers "do these look alike?" — a different question with a different consumer (retrieval), which `cosine_topk` already serves at query time.
2. **It would recreate the degree-clique failure at its worst.** The movement catalog is dominated by the flat class (the Phase 1 imbalance result). Materializing similarity edges welds the flat-majority region of movement space into one megaclique — the same volume-laundering that disqualified same-source STRUCTURAL, but bigger.
3. **Similarity is recomputable; edges are commitments.** A persisted similarity edge goes stale the moment bin thresholds or vector features change; `cosine_topk` over the current catalog never does. Persist mechanism, recompute resemblance.

### 6.2 Legitimate role 1: stratified null model for co-variance

Two series in the same place-hash bucket (both `minority|down|decade|drift`, say) have an elevated *prior* probability of sign agreement — declining regimes agree with declining regimes. A global base rate would let co-variance discovery "discover" this and mint edges that mean only *both are declining series*. So the §2.3 null model conditions on bucket: sign agreement must beat the **within-bucket** base rate, not the global one. The hash doesn't create edges — it makes the edges that do get created mean something beyond regime co-membership. This is the hash working *against* spurious connascence, its most valuable job here.

### 6.3 Legitimate role 2: candidate generation for co-variance discovery

Pairwise co-variance discovery is O(n²) in series count. `cosine_topk` over mean place-vectors per (polity, group) series shortlists candidates cheaply — same propose/verify pattern as the LLM (§3): **similarity proposes, co-movement arithmetic promotes, and only the arithmetic materializes an edge.** At the current series count this is an optimization, not a necessity; it becomes load-bearing when the polity/group roster grows (Phase 3 scale).

### 6.4 The kernel of truth in "similarity is structural": connascence of algorithm

Classic software connascence includes *connascence of algorithm* — components that must agree on an algorithm change together. The analogue is real: every `origin_hash` and `place_vector` is downstream of one binning/embedding pipeline. If `_FLAT` or a bin edge moves, **all** hashes and vectors change together — a genuine shared fate, but a *global* one, coupling every derived node to the pipeline version rather than nodes to each other. Global dependencies are provenance, not pairwise topology: stamp derived artifacts (catalog rows, co-variance edges, hash-mode claims) with a `repr_version` (e.g. `place_hash_v1`), and treat a version bump like a schema change — settled claims keep the version they settled under; consumers never mix versions. O(1) fields instead of O(n²) edges that all say the same thing.

### 6.5 Summary

| Proposed use | Admitted? | Form |
| --- | --- | --- |
| Similarity as STRUCTURAL edges | No — represented-alike ≠ produced-alike | — |
| Similarity as any persistent edge axis | No — dense, mechanism-free, flat-class megaclique | — |
| Bucket-stratified null for CO_VARIANCE | **Yes** | conditioning term in §2.3 discovery |
| Candidate shortlist for CO_VARIANCE | **Yes** | query-time `cosine_topk`, propose-only |
| Connascence of algorithm (pipeline coupling) | **Yes** | `repr_version` provenance field, not edges |

---

## 7. Bottom line

Four of five axes survive, none with their naive definitions. Structural inverts (discount, don't bind). Conceptual sharpens (accounting, not theme). Co-variance is the prize and needs a complement exclusion plus a bucket-stratified null to be real. Temporal earns its keep through shock gating. Co-occurrence retires. Place-hash similarity is not connascence — it is the *instrument* that keeps co-variance honest (stratified null, candidate shortlist) plus a provenance version stamp, never topology. The LLM gets two narrow, verifier-backed jobs and a trust posterior of its own — heuristics managed, not trusted.
