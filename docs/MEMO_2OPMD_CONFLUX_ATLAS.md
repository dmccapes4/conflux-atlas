# MEMO — What Conflux Atlas Means for 2OPMD / ptv-embed-lab

**Date:** 14 July 2026
**From:** the conflux-atlas build
**To:** the ptv-embed-lab / 2ndOpinionMD workstream
**Companion:** `RESEARCH_FINDINGS_20260714.md` (the math and the numbers), `REFLECTION_CROSS_DOMAIN_LOOP.md` (why this project exists at all)

---

## Abstract (in the spirit of Feynman)

Suppose you want to know how many people of each religion lived in Egypt in 1880. Nobody can tell you. There are a few old censuses, some scholars who argue with each other, and long stretches of years where nobody counted anything. So you do the only honest thing: you write down every claim anyone made, *who* made it, and you keep score. When two independent counters agree, you trust both a little more. When they agree because they copied each other, that shouldn't count — so you check for that too. When you have to guess what happened between two counts, you draw a band instead of a line, and you make the band exactly as wide as your ignorance.

Then you test yourself. You cover up the answers you already have, pretend it's 1975, make predictions with bands, and check how often reality lands inside them. We said our bands would catch the answer 80% of the time. The first time we checked, they caught it 59% of the time. That's a fact about us, not about Egypt, and it's the most useful kind of fact — so we wrote it down and went looking for the reason.

The reason was a surprise. We expected to be most wrong where we knew least — the big empty stretches between censuses. We were actually most wrong where we knew *most*: where several sources counted the same place in the same year and disagreed with each other about what "counting" means. Our bands treated a nearby measurement as the truth, when really every measurement carries a built-in fuzz — about as much fuzz as fourteen years of real demographic change, it turns out, once we measured it. Add that fuzz to the bands and the test comes back 85% against a stated 80%. The gaps were never the problem. The disagreement about definitions was.

One more thing. We let a small language model help classify how pieces of evidence relate — but only through a gate that checks every answer against arithmetic, only choosing from lists we wrote, with "I don't know" always allowed and free. Scored this way, it was right 97.9% of the time, and every one of its mistakes was caught before it touched the ledger. The trick isn't a smarter model. The trick is never letting anyone — source, algorithm, or model — into the books without a scorecard.

Why does a medical-records company care about Ottoman censuses? Because a patient's chart is the same problem wearing different clothes: sparse, irregular observations from sources that disagree about definitions, long gaps you're tempted to interpolate through, sudden shocks, and nobody keeping score of who tends to be right. We built the scorekeeping machine in a domain where the data is public and the stakes are low. It works. Now we know exactly what to carry home.

---

## 1. Context: why this system was built

Conflux-atlas started as an unblocking exercise. The ptv-embed-lab work (patient-trajectory vectors over MIMIC-IV) had stalled on questions that were hard to see clearly through the medical domain's noise: is the node-vector-hash idea predictive or just descriptive? Is connascence classification signal or ceremony? What does honest uncertainty look like over sparse, irregular time series?

Demographics offered the same mathematical shape with public data and legible ground truth: polities as nodes, migration as edges, share series as trajectories, censuses as encounters, scholarly disputes as inter-source noise, wars and revolutions as shocks. Every major subsystem was a deliberate port from the 2OPMD constellation:

| Conflux-atlas subsystem | Lineage |
| --- | --- |
| Beta-Bernoulli trust posteriors, settlement-only learning | **nakatomi** (settle on outcomes, never on promises) |
| Place-hash / place-vector movement space | **ptv-embed-lab** (node vector hashes over code space) |
| Typed connascence edges | **FullMetalPacket** → ptv-embed-lab (5-axis connascence) |
| PortalGC graph governance experiment | **PortalVision / provenance-engine** |
| Verifier-gated LLM proposer with its own posterior | ptv-embed-lab enrichment loop, hardened |

The build took roughly one day of wall-clock across Phases 0–3 plus the expanded experimentation program and the bridge repair. Everything below is measured, not hoped (see the findings doc for the arithmetic).

## 2. The five findings that transfer

### 2.1 The nugget: dense data fails differently than sparse data

**The single most important export.** We assumed calibration would decay with distance from the nearest anchor. It was *inverted*: 0.495 coverage at 1–5-year gaps vs 0.922 at 26–50-year gaps (stated 0.80). Where multiple sources are dense, the residual error is *definitional disagreement between sources* — measured at σ ≈ 0.015–0.046 share points, which equals ~1.4 decades of real demographic movement. One additive noise floor (`half = z·√(nugget² + (σ·gap)²)`), estimated from cross-source spreads rather than tuned, fixed the whole curve (0.851 overall).

**For ptv-embed-lab:** a patient's chart is *exactly* this. Two labs, two sites, two coding cultures stating "the same" observation carry an inter-source nugget — LOINC mappings, unit conventions, ICD coding habits, self-report vs EHR. Any interpolation or trajectory band through dense multi-source patient data that prices inter-source noise at zero will be *overconfident precisely where the record looks richest* — e.g., around hospitalizations, where sources multiply. The nugget is directly estimable in MIMIC: same patient, same LOINC, near-same time, different sources → sd(diff)/√2. For the wellness-score study, the journaling-vs-EHR nugget is the calibration constant for filling gaps between EHR pulls with patient journals — measurable from overlap windows where both exist.

### 2.2 Pre-registration + proper scoring rules changed our conclusions, twice

The Winkler interval score (width + 2/α per miss) as primary metric, frozen before running, did real work: (a) the shock split showed shock-window forecasts *cover better but score worse* — wide bands catch outcomes and pay for it; coverage alone would have concluded the opposite; (b) the first candidate policy (analog retrieval) "beat all baselines" under the frozen rule, and the paired bootstrap CI [−0.113, +0.184] spans zero — both facts are on the record without either softening the other.

**For ptv-embed-lab / the RISE paper:** wellness-score forecasting must publish its scoring rule and success criterion before touching the tape, and the primary metric must charge for band width, or the study will drift toward absurdly wide "always right" intervals. Also budget for the leakage class we hit: selection and confirmation tapes that share realized outcomes (our cut-sweep tapes shared 2005–2020 target rows; we switched to a hash-split by series — for patients, split by patient, never by time alone).

### 2.3 The node-vector-hash idea just won its first pre-registered comparison

Analog retrieval — origin-context place vectors, cosine top-k cross-series neighbors, forecast bands from neighbor-outcome quantiles, fixed hyperparameters — beat persistence/reversion/AR1 on the primary metric on a held-out series half (IS 0.415 vs 0.426/0.482/1.000). Not yet statistically resolved at n = 64, but this is the first time the "similar places move similarly" mechanism outperformed autoregressive baselines under a frozen rule in *any* of our domains.

**For ptv-embed-lab:** this is the direct analog of "patients whose trajectories rhyme have rhyming futures." The design details that made it honest transfer as-is: origin-context vectors must exclude outcome features (or the query encodes its own answer), neighbors must exclude the query patient, and abstention below a neighbor floor is free. MIMIC's 980-graph cohort has orders of magnitude more series than our 485 — the CI that wouldn't resolve at n = 64 will resolve there.

### 2.4 Discovery loops need controls or they lie

Raw α = 0.05 co-variance admission produced 4 edges on real data — and **20 on shuffled data**. BH-FDR: 0 survivors either way. We shipped the two-tier design (strict tier for settlement: empty and honest; hypothesis tier for review/LLM input) instead of shipping noise. Same lesson from the permutation control on forecasts (shuffled outcomes worsen scores ×1.2–1.4 — bands are series-specific, not vacuously wide).

**For ptv-embed-lab:** the diagnosis↔lab↔med co-variance mining (LOINC/ICD/RxNorm co-movement) is running the *same statistical race* with far more candidate pairs — millions, not 3,852. Without stratified nulls, FDR, and a shuffle control in the pipeline itself, the co-variance layer will mint fictional physiology at scale. The MIMIC advantage: n per pair is large enough for the strict tier to be non-empty, which unlocks the partial-settlement mechanism that conflux built but (honestly) never fired.

### 2.5 The LLM belongs inside the ledger, not above it

Constrained to closed vocabularies, schema-forced JSON, deterministic decoding, verifier-gated promotion, free abstention, and a trust posterior of its own: qwen3:8b scored 0.979 over 467 trials (full population), 0 malformed windows, every error caught pre-ledger. Its measured failure mode is ontology confusion (mislabeling coupling *kinds*), not fabrication. Operationally: one loaded model, per-request system prompts (no Modelfile), ~17 s/call, 11 minutes for the full population.

**For ptv-embed-lab:** the clinical enrichment loop (event attribution for care episodes, coupling proposals between code series) should be a scored proposer in the same ledger as the data sources — with the extra dividend that the posterior is per-model and per-job, so swapping models becomes an empirical question the ledger answers.

## 3. What this de-risks for the wellness-score program

The proposed study — wellness score tracked over a ~10k population with Epic feeding EHRs, journaling filling the gaps — now has a full dress rehearsal:

1. **Gap-filling with calibrated bands** is demonstrated end-to-end: fit dynamics on the dense window, backfill with quadrature widths (nugget + gap term + shock multiplier), validate by anchor-drop LOO — with the curve *measured* (282 held-out points across 37 series), not asserted. The mp4's uncertainty shading falls out of the band product mechanically (4,592 rows shipped here).
2. **Shock handling** has a working contact rule: events widen bands only for the entities they touch (admissions/med-changes for patients; wars for polities). The degenerate version (every event widens everything) was measured, caught, and fixed.
3. **Source scorekeeping** works with graded weights: same-family discounts and definition-gap routing moved trust numbers in interpretable directions. Epic-vs-journal-vs-claims is the same three-lane problem as census-vs-survey-vs-registry.
4. **The evaluation harness is portable**: pre-registration block, Winkler scoring, Wilson intervals, climatology floors, permutation controls, hash-split selection/confirmation — all of it is domain-agnostic code sitting in `conflux/experiments.py` waiting to be lifted.

## 4. What conflux still owes us

Honest ledger of what did *not* transfer-proof today: the strict co-variance tier is empty (data density, not math — MIMIC won't have this problem); the same-polity historical bridge lane is n = 3 (the E8 ingest is queued); the analog win needs a bigger n to resolve; and PortalGC's attractor geometry showed no correlation with evidential quality here — a genuine null worth remembering before wiring Lorenz dynamics into anything clinical.

## 5. The loop, closed

nakatomi taught settlement-only learning. FullMetalPacket taught typed edges. PortalVision taught simulation and governance. ptv-embed-lab posed the trajectory question and got stuck. Conflux-atlas — built in a day on public data — returned the answers: *the hash-retrieval mechanism can win pre-registered comparisons; connascence earns its keep as settlement routing, not decoration; uncertainty must be widest where sources disagree, not where data is absent; and every participant in the system, silicon included, plays under the same scorecard.*

That last sentence is the company. 2OPMD's product thesis has always been that a second opinion is only worth what its track record says it's worth. We now have a working machine that operationalizes exactly that — and a checklist, with measured constants, for rebuilding it over patients.
