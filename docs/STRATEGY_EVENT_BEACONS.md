# STRATEGY — Events as Research Beacons for Knowledge-Base Expansion

**Date:** 14 July 2026  
**Status:** Design / research-ops  
**Purpose:** Define a strategy for using major historical events as focal points (“beacons”) to grow the knowledge base efficiently — especially religious-demographic movement data — for both the simulation video and long-term data quality.  
**Companions:** `STRATEGY_V0.2.md` §5 (video after the loop is worth filming), `DATA_SOURCES.md`, `SCHEMA.md` (Event / Edge), Phase 3 shock tagging (`connascence.tag_shock_claims`), `REPORT_BRIDGE_V2.md` (empire↔successor event-tape gap).  
**Ops artifacts:** `data/processed/beacons.jsonl`, `docs/BEACON_SCHEMA.md` (quality gate v0), `docs/beacon-inventories/`, `docs/BEACON_INGEST_CONNASCENCE.md` (ingest → full Phase 2b re-run).

---

## 1. Abstract: The Beacon Concept for Knowledge-Base Growth

In domains with sparse, heterogeneous historical data, uniform coverage across all time periods is inefficient and often impossible. The beacon strategy prioritizes well-studied historical events that involved significant demographic or religious movement. These events naturally attract concentrated scholarly attention — books, peer-reviewed papers, archival research, contemporary accounts, and quantitative studies — because they represent clear turning points.

By treating these events as research beacons, the project can:

- Focus ingestion and source discovery where high-quality material is most likely to exist.
- Rapidly increase data density and confidence around pivotal moments.
- Create natural anchors for the simulation video (clear narrative beats with visible movement).
- Use the existing graph structure (polities + migration edges + events) to surface “beacons-in-the-rough” — periods or sub-regions that show high interaction but currently lack strong sourcing.

This approach is modular and scalable. Each beacon can be researched somewhat independently while still contributing to the overall movement-vector and uncertainty model. It directly addresses data scarcity by following the existing light of scholarship rather than attempting to illuminate every dark corner equally.

---

## 2. Expanded Historical Beacon Timeline (Since Muhammad)

The simulation video should begin at minimum with the rise of Islam. Below is an expanded table of major beacon events with demographic or religious movement significance.

| Period | Year(s) | Beacon Event | Demographic / Religious Movement Significance | Video Narrative Role | Research Priority |
| --- | --- | --- | --- | --- | --- |
| Early Islamic | 610–632 | Prophethood of Muhammad & Unification of Arabia | Formation of early Muslim community; initial religious consolidation | Origin point for Islamic demographic expansion | Medium |
| Early Conquests | 632–661 | Rashidun Conquests (Arabia → Levant, Egypt, Persia) | Rapid territorial expansion; gradual religious shift in conquered regions | First major wave of Islamic demographic change | High |
| Umayyad Period | 661–750 | Umayyad Caliphate Expansion (to Spain & Central Asia) | Large-scale Arab settlement + conversion waves | Spread of Islam across three continents | High |
| Abbasid Era | 750–1258 | Abbasid Caliphate & Cultural Golden Age | Administrative integration; conversion acceleration in Persia & North Africa | Stabilization and deepening of Muslim majorities | Medium–High |
| Medieval | 1095–1291 | Crusades & Counter-Crusades | Temporary Christian polities in Levant; population displacements | Religious conflict and demographic flux in Levant | Medium |
| Late Medieval | 1258–1517 | Mongol Invasions + Mamluk Period | Destruction and recovery; shifts in urban populations | Major disruption and rebuilding phases | Medium |
| Early Modern | 1299–1683 | Rise & Expansion of Ottoman Empire | Turkish settlement in Anatolia & Balkans; millet system | Foundation of long-term multi-religious governance | High |
| Ottoman Peak | 1453–1683 | Conquest of Constantinople + Further Expansion | Major population movements and religious policy shifts | Symbolic and demographic turning point | High |
| 19th Century | 1800–1914 | Ottoman Tanzimat Reforms & Nationalist Stirrings | Emerging ethnic/religious nationalisms; early emigration | Slow erosion of millet system | Medium–High |
| WWI Collapse | 1914–1923 | Ottoman Defeat + Greco-Turkish Population Exchange | Massive directed population transfers | First large-scale modern engineered demographic change | Very High |
| Mid-20th Century | 1948–1951 | Arab-Israeli War + Jewish Exoduses from Arab Countries | Large-scale Jewish refugee movements out of MENA | Major redistribution of Jewish populations | Very High |
| Late 20th Century | 1975–1990 | Lebanese Civil War | Multi-sided displacement of Christians, Palestinians, and others | High local volatility and emigration | High |
| 1979 | 1979 | Iranian Revolution | Shift in religious governance + emigration of minorities | Major internal religious-political realignment | High |
| 21st Century | 2011–present | Syrian Civil War & Regional Refugee Crisis | Millions displaced across MENA and into Europe | Contemporary high-volume movement | Very High |

---

## 3. Beacon References Table

This table links each major beacon to key scholarly or primary sources. These serve as starting points for targeted research and ingestion.

| Beacon Event | Key Scholarly Artifacts / References |
| --- | --- |
| Rashidun & Umayyad Conquests | Hugh Kennedy — *The Great Arab Conquests* (2007); Fred Donner — *The Early Islamic Conquests* (1981) |
| Abbasid Period & Conversion | Richard Bulliet — *Conversion to Islam in the Medieval Period* (1979); Ira Lapidus — *A History of Islamic Societies* |
| Ottoman Empire & Millet System | Kemal Karpat — *Ottoman Population 1830–1914* (1985); Stanford Shaw — *History of the Ottoman Empire and Modern Turkey* |
| Greco-Turkish Population Exchange (1923) | Renée Hirschon (ed.) — *Crossing the Aegean* (2003); Lausanne Treaty records; studies on refugee integration |
| 1948–1951 Jewish Exoduses | Norman Stillman — *The Jews of Arab Lands in Modern Times* (1991); Esther Meir-Glitzenstein — *Zionism in an Arab Country* (Iraq); Jewish Agency / Israeli archival studies |
| Lebanese Civil War (1975–1990) | Robert Fisk — *Pity the Nation* (1990); Kamal Salibi — *A House of Many Mansions*; academic volumes on sectarian demographics |
| Iranian Revolution (1979) | Ervand Abrahamian — *A History of Modern Iran* (2008); demographic studies on post-revolutionary emigration |
| Syrian Civil War & Refugee Crisis | UNHCR reports; Syrian Center for Policy Research volumes; papers on demographic impact in Lebanon and Jordan |

These references can seed targeted source hunting and improve confidence estimates around each beacon period.

---

## 4. Graph Analysis to Discover Beacons-in-the-Rough

The current graph structure (polities as nodes, migration edges, and event triggers) is well-suited for identifying promising new beacons.

### High-potential techniques

- **Event density & temporal clustering.** Identify periods with unusually high numbers of migration edges or event triggers within short time windows. These clusters often indicate moments of significant change that scholars have studied intensively.
- **High centrality nodes during specific eras.** Polities with high betweenness or degree centrality in certain decades (e.g. Lebanon in the 1970s–80s, Anatolia during Ottoman expansion) are likely to have rich secondary literature.
- **Low-confidence + high-connectivity areas.** Subgraphs where many edges connect to nodes with currently low confidence scores are “beacons-in-the-rough” — significant movement, weak sourcing. High marginal value for ingest.
- **Community detection on time-sliced graphs.** Community detection on graphs filtered by era (e.g. 1900–1950 vs 1950–2000). Communities that appear or dissolve around certain periods often correspond to well-documented realignments.
- **Shock propagation analysis.** Events that affect many downstream nodes (high out-degree in the event-impact graph) are natural beacons. The Syrian Civil War and 1948–51 exoduses are current examples.

### Recommended next step

1. **Beacon inventories (in progress on `feature/event-beacons`)** — per-beacon bibliographies under `docs/beacon-inventories/` against the quality gate in `docs/BEACON_SCHEMA.md`; queue in `data/processed/beacons.jsonl`.
2. **Beacons-in-the-rough script** — read-only ranking from `edges.jsonl` + `events.jsonl` → `data-validation-reports/BEACON_CANDIDATES.json` (high activity × low trust × missing event coverage).

Create a simple analysis script that:

1. Takes the current `edges.jsonl` + `events.jsonl`.
2. Computes basic temporal centrality and clustering metrics.
3. Outputs a ranked list of “under-sourced but high-activity” periods for targeted research.

This gives a data-driven path to the next tier of beacons beyond the obvious major events.

---

## Meta commentary (Grok)

**The strategy is right; the tape is what makes it load-bearing.** Conflux already treats events as first-class schema (`Event` with `affected_polities`, edge-linked `migration_burst` / `confidence_reset`), and Phase 3’s calm/shock split and Bridge v2 shock widening both *consume* that tape. Today the live catalog is three hand-seeded triggers — Lausanne 1923, 1948 war/exodus umbrella, Iran 1979 — which matches three of the “Very High / High” beacons above and leaves everything else as aspiration. So this document is not a new subsystem; it is an **ingest and research-ops priority queue** for the component the rest of the stack already knows how to use.

**Beacons should map 1:1 onto `event_id`s, not onto vibes.** Each row in §2 that we actually work should land as: (a) an `events.jsonl` record with explicit polity membership (including empire-era ids or a membership map — Bridge v2 already flagged that `ottoman_empire` gets no shock windows because successors hold the tags), (b) one or more volume/share edges with citations, (c) bibliography entries tied to the references in §3. Without that triad, a “beacon” stays a narrative chapter title and cannot bump trust, widen bands, or appear as a scrubber pause.

**Priority order for the next ingest tranche (not the video).** Video still waits on STRATEGY’s rule: film after the loop is worth filming. For *data* payoff against current machinery, prefer beacons that densify the modern settlement window and fix known holes:

1. **Syrian Civil War / regional refugee crisis** — Very High; UNHCR already on the desk as stock data; strongest path to contemporary high-volume edges and a real calm/shock contrast (Phase 3’s calm bin was empty partly because the event catalog is thin relative to 1975→2010 windows).
2. **Lebanese Civil War** — High; fills the 1975–1990 gap the backtest windows already overlap; high local volatility is exactly what shock tags are for.
3. **Deepen 1923 / 1948 / 1979** — already present as stubs; Hirschon, Stillman, Abrahamian et al. should upgrade volumes and confidence, not invent parallel event ids.
4. **Ottoman peak / Tanzimat** — High for the bridge and Karpat-era story; needs empire↔successor polity mapping so shock widening and beacon research hit the same nodes.
5. **Early Islamic → Abbasid / Crusades** — Medium for the *video origin story*; Low near-term for falsifiable share forecasts unless we accept conversion curves (Bulliet-style) as a separate claim family with honest uncertainty. Do not pretend medieval conversion estimates are the same object as Pew share anchors.

**“Beacons-in-the-rough” is the part that fits this codebase best.** Centrality and community detection are fine, but the highest-leverage ranking for *this* project is closer to what PortalGC and the trust ledger already measure: **high edge activity × low source trust / low anchor confidence × missing `event_id` coverage**. That is “scholarship should exist here; we haven’t ingested it” in the same units the settlement loop already speaks. The recommended script should emit that ranking into `data-validation-reports/` (e.g. `BEACON_CANDIDATES.json`) and stay read-only — discovery, not auto-minting events.

**One caution.** Beacons concentrate attention where literature is loud. Contested or politicized episodes (1948, Armenian/Ottoman counts, Syrian war figures) are exactly where STRATEGY’s rule already bites: McCarthy-class sources stay confidence-capped inputs, never validation targets. A beacon research push must widen *cited* density and bands, not launder one loud narrative into the settlement tape. Follow the light of scholarship; do not treat brightness as truth.

**Bottom line.** Adopt §2 as the narrative and ingest roadmap; implement §4’s ranking script next; grow `events.jsonl` beacon-by-beacon with polity membership and edges before expanding the video timeline backward to 610. The machinery is ready for a denser event tape — the beacon list is how we choose which darkness to light first.
