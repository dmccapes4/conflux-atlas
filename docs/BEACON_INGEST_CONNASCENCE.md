# Beacon ingest → graph → connascence (readiness)

**Date:** 14 July 2026  
**Branch:** `feature/event-beacons`  
**Status:** Ops plan — inventories + open PDFs are **not** yet on the evidence desk  
**Companions:** `STRATEGY_EVENT_BEACONS.md`, `BEACON_SCHEMA.md`, `STRATEGY_CONNASCENCE.md`, `scripts/run_phase2b_connascence.py`

---

## 1. Verdict: re-run the full timeline

**Yes — after material ingest, re-run the whole deterministic Phase 2b tape** (`scripts/run_phase2b_connascence.py` / whatever `make` target wraps it), not a “delta-only” patch.

Connascence is a **global** consumer:

| Layer | Why a partial re-run lies |
| --- | --- |
| Weighted corroboration | New sources change independence discounts and posteriors for *neighbors*, not only the new rows |
| Complement / co-variance / shuffle | Edge set and null floors are desk-wide |
| Shock tagging | New `events.jsonl` windows re-label calm/shock for claims that already existed |
| Conservation | Migration edges interact with the fuller event/edge graph |

Keeping old `PHASE2B_*.json` beside a half-updated desk would compare apples to oranges. Treat the next Phase 2b artifacts as a **new epoch** (timestamp or note in the report), and re-run Phase 3 backtest/bridge afterward so calm/shock and shock-widening see the same tape.

**Optional / later:** LLM enrichment (`run_llm_enrichment.py`) — expensive; do **not** block the deterministic re-run on it. Re-propose only after the new desk is stable.

**Do not** “ingest” PDFs straight into connascence. PDFs are raw; the graph only eats validated `Anchor` / `MigrationEdge` / `Event` / observation rows + BIBLIOGRAPHY `source_id`s.

---

## 2. What we have vs what the graph needs

| Ready now | Still required before connascence can see it |
| --- | --- |
| `data/processed/beacons.jsonl` (14 beacons, status `inventory`) | Promotion: `beacon_id` → `event_id` (+ polity membership, including empire↔successor map) |
| `docs/beacon-inventories/BEACON_*.md` + `## Open PDFs` | BIBLIOGRAPHY rows for every `source_id` that enters processed data |
| `data/raw/beacons/<beacon_id>/*.pdf` (~86 files) | Table extraction → shares / volumes (OCR forge for hard scans) |
| Quality gate v0 (accept / caution / reject) | `load_observation_desk` / edge seeders taught about new files |

Inventories are a **research queue**, not an ingest format.

---

## 3. Ingest order (material, then tape)

Follow STRATEGY priority for *data* payoff, not video chronology:

1. **Syria 2011–** — UNHCR COO×COA refetch / HDX; IDMC IDP; SCPR as caution; seed `syrian_civil_war_2011` event  
2. **Lebanon 1975–90** — Labaki/Tabar destination volumes; Verdeil internal displacement; UNRWA stock series; new event  
3. **Deepen 1923 / 1948 / 1979** — upgrade existing event stubs + edge volumes from Lausanne/ELSTAT/WJP/SCI (no duplicate event ids)  
4. **Ottoman Tanzimat / peak** — Karpat full PDF already downloaded; Shaw census; empire↔successor shock map  
5. **Pre-modern beacons** — only as separate claim families (conversion curves, urban estimates); do **not** mix into Pew-class share validation

Per beacon, the promotion triad is unchanged:

1. `events.jsonl` row (polities + effects)  
2. cited edges and/or share anchors  
3. BIBLIOGRAPHY + gate tag (`accept` / `caution`; McCarthy-class never validation)

---

## 4. Re-run recipe (once step 3 has landed rows)

```bash
# Deterministic evidence graph + connascence (full desk)
.venv/bin/python scripts/run_phase2b_connascence.py

# Shock-aware forecast / bridge (same event tape)
make phase3-backtest
make phase3-bridge   # or bridge_v2 if that is the active entrypoint

make test            # contracts must stay green
```

Archive or rename prior `PHASE2B_*` if you need a before/after diff; do not silently overwrite without a report note.

---

## 5. Definition of ready (checklist)

- [x] BIBLIOGRAPHY rows for first tranche sources (Syria/Lebanon/1923/1948/1979 + Karpat/Shaw PDFs noted)
- [x] ≥1 new or upgraded `Event` with `affected_polities` (`syrian_civil_war_2011`, `lebanese_civil_war_1975`; Iran deepened)
- [x] ≥1 new migration edge / OD series (`unhcr_syria_refugee_stock_od.jsonl` + Labaki edges)
- [x] Loaders / seeds (`make beacon-tranche1`); Phase 2b uses `tag_shock_claims_contact`
- [x] Full Phase 2b re-run — **63** policy claims in shock windows (was 0)
- [x] Phase 3 backtest/bridge re-run (forecast baselines unchanged; bridge still undercalibrated)
- [ ] OCR/table extract Karpat/Shaw/SCPR into share anchors (next tranche)
- [ ] LLM enrichment re-propose (optional; after desk stable)

Reproduce:

```bash
make beacon-tranche1
make phase2b
make phase3-backtest && make phase3-bridge
```


---

## 6. What not to do

- Auto-mint events from inventory filenames or PDF downloads  
- Dump medieval conversion PDFs into the 1975-cut validation mix  
- Re-run only `tag_shock_claims` on the old ledger and call it done  
- Treat ReliefWeb HTML failures in `_failures.tsv` as ingested sources
