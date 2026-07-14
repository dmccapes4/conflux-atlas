# REPORT — Phase 1 Scorecard (Movement Vectors & Retrieval)

**Date:** 14 July 2026  
**Protocol:** leave-one-polity-out (`conflux/scorecard.py`)  
**Artifact:** `data-validation-reports/PHASE1_SCORECARD.json`  
**Cohort:** demo polities from `ConfluxModel` · groups `muslim` / `christian` / `jewish`  
**Catalog size:** 147 inter-anchor transitions · fair-tape `n_scored=69` (transitions where all four policies produced a prediction)

## 1. Result (honest)

| Policy | Accuracy | Coverage | n_scored |
| --- | ---: | ---: | ---: |
| **majority** (train modal direction) | **0.797** | 1.000 | 69 |
| persistence (repeat previous) | 0.768 | 0.735 | 69 |
| reversion (flip previous) | 0.754 | 0.735 | 69 |
| hash_mode (origin place-hash bucket) | 0.725 | 0.701 | 69 |

**`hash_mode` does not beat the dumb baselines on this tape.** Majority wins; persistence is second. That is a Phase 1 *result*, not a test failure — the contracts only require a well-formed scorecard with no leakage.

## 2. Why this is unsurprising (and useful)

- **Sparsity.** Demo anchors are mostly 1900/1950/2000 + Pew 2010/2020 (~4–5 snapshots/polity). Place buckets are thin; `min_bucket_n=2` already abstains on ~30% of hash lookups.
- **Class imbalance.** Many group series are near-flat (muslim-dominant polities). Majority/persistence ride that imbalance; a place hash that often abstains cannot.
- **Fair tape shrinks N.** First transitions per polity×group always abstain for reversion/persistence, so accuracy is scored on 69/147 rows — wide error bars either way.
- **Contrast with ptv-embed-lab.** There, dense LOINC series made place-conditioned hashing beat reversion by ~3–4 points. Demography is not there yet.

## 3. What Phase 1 *did* ship

- `conflux/movement.py` — decade-scaled bins, inter-anchor events (no annual interpolation), place vectors, cosine top-k, hash outcome table.
- `conflux/scorecard.py` — LOPO evaluation, four policies, honest abstention/coverage, JSON report writer.
- Spec clarification: `origin_hash` uses **prior** delta (or `na`), not this transition's delta — otherwise hash_mode encodes the label it predicts.
- Gates: `make test-phase1` (62 passed) and `make test` (Phase 0+1) green.

## 4. Next (not claimed here)

- Richer overlays / denser modern windows before re-running the scorecard as a research bet.
- Confidence-weighted retrieval ablation (`place_vector(weighted=True)`) — infrastructure is ready; not scored in this report.
- Phase 2 trust ledger can settle these policies against future census rounds.

## 5. Reproduce

```bash
make test-phase1
.venv/bin/python scripts/run_phase1_scorecard.py
# → data-validation-reports/PHASE1_SCORECARD.json
```
