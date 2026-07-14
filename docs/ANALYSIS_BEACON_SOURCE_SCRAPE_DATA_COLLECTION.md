# ANALYSIS — Beacon source scrape & data collection

**Date:** 14 July 2026  
**Branch:** `feature/event-beacons`  
**Scope:** First full pass of beacon inventory → open-PDF scrape → tranche-1 ingest  
**Companions:** `STRATEGY_EVENT_BEACONS.md`, `BEACON_INGEST_CONNASCENCE.md`, `REPORT_BEACON_TRANCHE1.md`, `docs/beacon-inventories/`

---

## 1. Verdict (short)

| Question | Answer |
| --- | --- |
| Did we meaningfully improve **data scarcity**? | **Yes for the shock / migration layer; no for the share-anchor desk.** The graph can now *see* modern refugee shocks. Religious-composition anchors are still ~92% Pew. |
| What time band did most sources use? | **Inventory midpoints split ~57% modern (≥1900) vs ~41% pre-1500.** What entered the graph is almost entirely **1923–2024**. |
| Did some go back centuries for demography-as-known? | **Yes, two different kinds:** (1) contemporary series written near the event (AJYB mid-century tables); (2) modern reconstructions that claim multi-century medieval conversion / settlement curves (Bulliet, Crusades/Mongol literature). Neither kind is on the share desk yet. |

Scraping many artifact types **widened the research queue** (86 PDFs, ~350 MB, all 14 beacons) but **did not yet diversify the validated observation desk**. Inventories ≠ ingest.

---

## 2. What the first scrape actually collected

### 2.1 Download pass (reported)

| Metric | Value |
| --- | ---: |
| URLs attempted (inventory Open PDF lists) | ~91 |
| Newly downloaded | 18 |
| Skipped (already on disk) | 68 |
| Failed | 5 |
| PDFs now on disk | **86** across **14** beacon folders |
| Approx. raw size | ~350 MB |

Failures (`data/raw/beacons/_failures.tsv`) are concentrated on **ReliefWeb attachment URLs returning HTML** (UNRWA bulletin, AFAD 2013, VASyR 2018, UNHCR Syria registered 2015) plus one institutional `cgi/viewcontent` HTML page (Borsch plague paper). The downloader correctly refused non-PDF content; those sources remain inventory-only.

### 2.2 Heterogeneity of artifacts (the scrape approach)

Open-PDF URLs are **not** one corpus. Host mix (unique-ish inventory mentions ≈81–92):

| Host class (approx.) | Count | Role for demography |
| --- | ---: | --- |
| University / open repos | ~20 | Articles, theses, working papers |
| Essay / mirror dumps (`almuslih.org`) | ~15 | Early Islam / conversion **narrative** PDFs — high volume, uneven table density |
| UN / humanitarian | ~13 | Stocks, methods notes, situation reports |
| Jewish population series | ~6 | AJYB / WJP historical tables (1948 beacon) |
| Internet Archive | ~3 | Digitized monographs |
| Academic press direct | ~2 | Often product pages; full PDF rare |
| Other | ~33 | Mixed gov, IDMC, local data portals |

**Implication:** One script (`download_beacon_pdfs.py`) over `## Open PDFs` is the right *ops* shape, but it papers over very different extractability:

- **Machine-ready:** UNHCR Population API (used in tranche-1) ≫ PDF tables.
- **Table-extractable with work:** AJYB PDFs, Labaki/MPRA, Karpat/Shaw scans, some IDMC/SCPR.
- **Context / methods only:** most early-Islamic and Crusades PDFs; Bulliet-class curves need hand digitization of published charts, not OCR of prose.
- **Fragile:** ReliefWeb deep links, DOI landing pages, institutional HTML wrappers.

Gate labels in candidate tables (where filled): **accept 28 / caution 22** — inventories already distinguish payload quality; the scrape did not.

---

## 3. Did we improve data scarcity?

### 3.1 Layers that moved

| Desk layer | Before beacons | After tranche-1 | Scarcity verdict |
| --- | ---: | ---: | --- |
| Events | 3 stubs | **5** (+Syria 2011, Lebanon 1975; Iran edge deepen) | Improved — shock calendar usable |
| Migration edges | 10 | **20** | Improved — first non-seed refugee volumes |
| OD observations | 0 | **140** rows (`unhcr_syria_refugee_stock_od.jsonl`, coo=SYR, 2011–2024) | Improved — but **stocks ≠ flows** |
| Share anchors | 438 | 438 (unchanged mix) | **Not improved** |
| Beacons status | inventory | **3** `partial_ingest` / **11** still `inventory` | Queue ≫ desk |

Anchor primary-source mix is still:

- **Pew Global Religious Composition 2010/2020:** ~91.8%
- **hand_seed_v0:** ~8.2%

So the North Star scarcity problem — sparse, heterogeneous **religious shares and pre-1975 movement** — is **not** fixed by this pass. What we fixed is the earlier Phase 2b failure mode: **0 shock-window claims** because events did not contact the 2000–2020 policy tape. After tranche-1 + contact tagging: **63** shock claims; calm vs shock majority hit **0.672 vs 0.481** (see `REPORT_BEACON_TRANCHE1.md`).

### 3.2 Honest ratio: scrapes vs graph

| Artifact | Count | On evidence desk? |
| --- | ---: | --- |
| Open PDF URL mentions | ~92 | No (raw) |
| PDFs on disk | 86 | No until extraction + BIBLIOGRAPHY |
| Candidate table rows with year annotations | ~79 | Research queue |
| `source_id`s actually on edges/events | 7 families | Yes |
| Beacons with any graphish link from Open PDFs | **3** (Syria, Lebanon, 1948 WJP/AJYB path) | Partial |

**Conclusion:** The scrape **meaningfully improved scarcity for refugee-shock validation and conservation probes**. It **did not** meaningfully improve scarcity for composition anchors or for the 11 pre-modern / Ottoman beacons. Treating “86 PDFs downloaded” as “data densified” would oversell the pass.

---

## 4. Time bands: beacons vs sources vs graph

### 4.1 Beacon periods (strategy timeline)

| End-year band | Beacons |
| --- | --- |
| Pre-1500 | 5 — Muhammad → Abbasid, Crusades |
| 1500–1799 | 3 — Mongol/Mamluk, Ottoman rise/peak |
| 1914–1974 | 3 — Tanzimat, 1923 exchange, 1948 exodus |
| 1975–present | 3 — Lebanon, Iran 1979, Syria |

Beacon **coverage intent** is millennial. Scrape coverage followed that intent (every folder has PDFs).

### 4.2 Inventory candidate “years” columns

From year-annotated candidate rows (~46–79 depending on parse strictness):

- Earliest cited start ≈ **1050**; latest end ≈ **2024**.
- Midpoint by century (coarse): **1900s (~29)** and **2000s (~17)** dominate among modern rows; **1100s–1300s** dominate among medieval rows (~14+11+…).
- Midpoint ≥1900 ≈ **majority of annotated modern-leaning rows**; midpoints **&lt;1500** are a large minority (~40% of the cleaner midpoint sample).

Long spans (≥100 years) are almost all **event-window spans** (e.g. Crusades 1095–1291, Mongol manpower 1219–1335), not “census continuous series.” One modern policy brief spans **1865–2020** (Lebanon migration context).

### 4.3 What the graph actually uses (time)

| Graph object | Year band in use |
| --- | --- |
| Edges `year_start` | **1920s, 1940s, 1950s, 1970s, 2010s** only |
| Syria OD | **2011–2024** |
| Share anchors by decade | Heavily **2010 / 2020**; thin 1900/1950/2000 hand seeds |

**Most sources that *matter to the current tape* are late 20th / early 21st century operational demography** (UNHCR, Labaki 1975–77, WJP/AJYB mid-century). Medieval and early-Islamic PDFs sit in `data/raw/beacons/` as a **second queue**, not as desk density.

---

## 5. Centuries of context and “demography as known at writing”

Three distinct patterns show up in inventories. Conflating them would mis-state confidence.

### 5.1 Contemporary-as-of-writing (near-event snapshots)

Examples: AJYB world Jewish population tables (**1940 / 1946 / 1949**), early postwar baselines for the 1948 beacon. These are **period demography as published then** — valuable for cut-year validation and for not back-projecting Pew.

Tranche-1 deepened Iran→Israel via WJP-linked paths; AJYB PDFs are on disk for further table extract, not yet share anchors.

### 5.2 Modern reconstruction of multi-century processes

Examples: Bulliet conversion S-curves (7th–13th c. regional chapters), Crusades settlement / subject-Muslim literature spanning **~200 years**, Mongol manpower / Black Death urban recovery papers. Authors write in the **20th–21st century** about demography **of** earlier centuries. That is **not** “as known at time of writing in 750 CE”; it is quantitative history with method-family risk (onomastics, archaeology, fiscal proxies).

Inventories already flag Lapidus/Kennedy-style narratives as **`context_only`** — modern Muslim-% tables in those books must not become Abbasid-era anchors.

### 5.3 Long context for a short shock

Labaki / Lebanon migration briefs and some Ottoman Tanzimat materials use **decades-to-century** backdrops to explain a **1975–90** or **19th-c.** pulse. Useful for edge confidence notes; dangerous if treated as continuous share series without year tags.

**Answer to the user’s question:** yes — especially pre-modern beacons and conversion literature — sources routinely claim **century-scale** demographic stories. Almost none of that century-scale material has been promoted to `anchors.jsonl`. The scrape collected the library; it did not yet collect the numbers.

---

## 6. Scraping approach across artifacts — what worked / what didn’t

| Approach | Worked? | Note |
| --- | --- | --- |
| Parallel agent inventory → `## Open PDFs` | Partially | Filled all 14 beacons; early-Islamic lists lean on one mirror host |
| Bulk PDF download with `--continue` | Yes | Idempotent; failure TSV; 86 files |
| Prefer open PDF over DOI/paywall | Correct for ops | Missed best methods papers (Bulliet monograph still not open) |
| UNHCR API beside PDFs | **Best ROI** | 140 OD rows without PDF OCR |
| Treat PDF folder as ingest | No | Connascence plan correctly forbids PDF→graph |
| Uniform extract pipeline | Not attempted | Would fail: scans vs born-digital vs prose vs API |

**Recommendation:** keep the heterogeneous **discovery** scrape, but **split ingest tracks**:

1. **API / tabular** (UNHCR, future HDX/IDMC CSV) — first.  
2. **Born-digital table PDFs** (AJYB, Labaki, situation reports) — second.  
3. **OCR forge** (Karpat/Shaw) — third.  
4. **Conversion-curve digitization** (Bulliet charts) — separate claim family, never mixed into Pew validation.  
5. **Narrative PDFs** — BIBLIOGRAPHY + event context only unless a table is explicit.

---

## 7. Scarcity scorecard (this pass)

| Scarcity problem | Status after pass |
| --- | --- |
| No shock events contacting 2010s policy tape | **Improved** |
| No refugee OD series | **Improved** (Syria stocks) |
| Thin migration edges | **Somewhat improved** (×2 edges; still tiny) |
| Pre-1975 composition anchors | **Unchanged** |
| Medieval / early Islamic quantitative shares | **Unchanged** (PDFs queued) |
| Empire↔successor event tape for bridge | **Unchanged** (Ottoman PDFs not extracted) |
| Over-reliance on Pew for validation | **Unchanged** (~92%) |

Net: this was a **successful research-ops and modern-shock ingest pass**, not a **desk-wide scarcity cure**. The beacon idea is working as designed — light follows scholarship — but promotion from raw to graph is the bottleneck, not URL discovery.

---

## 8. Suggested next measurements

When the next scrape/ingest pass lands, update this file with:

1. **Extract rate:** PDFs on disk → new `source_id`s in BIBLIOGRAPHY → rows in anchors/edges.  
2. **Temporal desk histogram:** share of anchors with `year &lt; 1975` and `year &lt; 1500`.  
3. **Host-quality mix:** % of new rows from UN/API vs almuslih-class mirrors.  
4. **Phase 2b / Phase 3 deltas** tied to new claim families (not just more Syria hosts).

---

## 9. Reproduce the counts in this note

```bash
# PDF haul
find data/raw/beacons -name '*.pdf' | wc -l
du -sh data/raw/beacons

# Graph
wc -l data/processed/{events,edges,anchors,unhcr_syria_refugee_stock_od}.jsonl

# Failures
column -t -s $'\t' data/raw/beacons/_failures.tsv
```

Tranche-1 narrative and Phase 2b numbers: `docs/REPORT_BEACON_TRANCHE1.md`.
