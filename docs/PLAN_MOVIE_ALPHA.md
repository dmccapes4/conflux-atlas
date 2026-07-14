# PLAN — Alpha simulation movie (conversational)

**Date:** 14 July 2026  
**Status:** Planning revision (post first α spike)  
**Audience:** Us — lock scope before the next visual pass  
**Companions:** `movie-alpha/README.md`, `STRATEGY_EVENT_BEACONS.md`, `STRATEGY_V0.2.md` §5 (Phase 4 video)

---

## 0. How to read this

A back-and-forth. **You** = the brief (original ask + today’s map note). **Me** = pushback and a simpler alpha vision. Decisions we should treat as locked appear as **→ Decide**.

---

## 1. What you asked for

**You:** I want to show my parents the system — an **alpha** (version, not posterior) build of the simulation movie. Several views, toggled with tabs:

0. Tabs top-left. Timeline + slider + speed at the bottom. Views in the middle.  
1. **Map** — MENA + diaspora only; everyone else excluded. Country outlines encode distribution (R Muslim / G Christian / B Jewish), weighted until the palette is decent; thickness / concentric majority→middle→minority bands; outline bulges with volume correlated to velocity; migrations and other sensible indicators. Start here.  
2. **Data** — non-map, cold and honest; histograms/timelines behind cards.  
3. **Source weighting** — posteriors shifting; evidence-loop settlement.

**Flow:**

1. Intro to system + problem (map, sim not running until dialogue earns it; dummy settlement explained).  
2. System starts — still map; brief.  
3. Data view — everything explained; math when needed.  
4. Source weighting — live settlement; weights; partials; math.  
5. Map again — **slow around beacons**, describe event + movement, hope model aligns; resume; next beacon; repeat.  
6. Wrap — cool outro (countries going dark); findings + some data/math.

Feynman-style narration, suitable male voice. Use judgement. Rough is fine; cool visuals help. Very few humans will understand this system.

**Today’s add:** Alpha should stay **simple**. The whole explanation should take **at least ~3 minutes**. We need **stop and rewind for beacons**. Speed must be **easy to tune**. And we need an **actual map** — an image from the internet or the Google Maps screenshot I took — with overlays (borders, grey-out), not abstract blobs on a void.

---

## 2. Pushback — what the first spike got wrong

**Me:** The first `movie-alpha` spike proved the *shell* (tabs, scrubber, tour spine, TTS, exported frames). It did **not** honor the product you described for parents:

| Intent | Spike reality | Problem |
| --- | --- | --- |
| Geographic map | Abstract LAYOUT blobs | Parents don’t feel MENA; it looks like a toy graph |
| ~3+ min explanation | Tour can race if speed is high / TTS skips feel short | Need a **minimum runtime budget**, not just “a tour exists” |
| Stop / rewind beacons | Tour auto-lingers then continues | Need explicit **Pause at beacon / Resume / Scrub back** affordances |
| Simple alpha | Three dense views + Beta PDFs + particle arcs | Easy to overbuild; parents bounce |

**→ Decide:** Treat the spike as scaffolding. Next pass is a **visual + pacing rewrite**, not more features.

---

## 3. Vision for alpha (simple, showable)

**Me:** Alpha is a **guided desk demo**, not a research workstation and not a Netflix short.

### 3.1 One composition rule

First viewport = **map + narration + timeline**. Tabs exist, but the tour owns the camera. Data and Source weighting are **short, deliberate detours** (one scene each), then back to the map for the beacon walk. No dashboard clutter in the hero.

### 3.2 Real map, fake nothing geographic

**You:** Use a real basemap image (web or my screenshot); overlay borders and grey-out.

**Me:** Agreed on *real geography*. Pushback on **which** image:

- Your Google Maps screenshot is perfect as a **composition reference** (extent, beige MENA, green elsewhere). It is a poor **repo asset**: Google’s ToS generally block redistributing Maps screenshots inside a product, and labels/UI chrome fight our overlays.
- Prefer a **static open basemap** framed like your shot (N. Atlantic → India, N. Europe → Sahel): e.g. Natural Earth / similar public-domain raster, or a locally generated cartopy/geo plot we own. Crop and desaturate slightly so overlays read.
- Keep your screenshot in `docs/` or `movie-alpha/refs/` as **reference only** (not shipped in the player), unless we strip UI and accept “personal demo only / do not publish.”

**Overlays (alpha-simple):**

1. **Basemap** full bleed under the stage.  
2. **Grey-out mask** — everything outside MENA ∪ diaspora nodes at ~60–80% dim (Europe outside France/UK/Greece/Germany, deep Africa, Central Asia, etc.). Diaspora can be small “callout chips” or inset dots, not a second world map.  
3. **Borders** — thin strokes for in-scope countries only (GeoJSON join on `polity_id` / ISO). Out-of-scope borders stay in the photo but under the grey veil.  
4. **Fill / outline encoding** — keep your RGB idea, but **simpler than triple concentric art**:  
   - Fill opacity ∝ confidence or pop (pick one).  
   - Stroke color = gamma-weighted (M,C,J) → RGB.  
   - Optional single inner ring for #2 religion if share > ~15% — skip three-band sculpture for alpha.  
5. **Velocity** — subtle stroke pulse or scale jitter; don’t balloon countries into illegibility.  
6. **Migrations** — arcs only for **active** edges in the current year window; one color family; no particle fireworks required for alpha.

**→ Decide:** Basemap = open/static asset framed like the screenshot. Screenshot = reference. Grey-out + borders + RGB strokes = the whole map language for α.

### 3.3 Time & control (this is half the demo)

**You:** ≥ ~3 minutes to explain; stop/rewind beacons; speed easy to tune.

**Me:**

| Control | Alpha behavior |
| --- | --- |
| Speed | Discrete presets only: **0.5× / 1× / 2× / 4×** (big buttons, not a buried `<select>`) |
| Play / Pause | Always visible; Space works |
| Timeline scrub | Always works — even mid-tour (tour becomes “free scrub” until Resume tour) |
| Beacon stops | Tour **auto-pauses** at each beacon year; UI shows **Continue** + **Replay beacon** (rewinds ~5–10y and re-narrates) |
| Minimum length | Script timed for **≥ 3:00 at 1× with voice on**; if muted, still gate beacon Continues so a silent watch isn’t a 40s blur |
| Pre-1900 beacons | Narrate as “library, not desk” or skip in the timed walk — don’t fake medieval fills on a 1900+ numeric map |

Beacon set for the timed walk (keep short): **1923 → 1948 → 1975 → 1979 → 2011** (five stops). That’s enough drama for parents.

**→ Decide:** Beacon = hard pause with Continue / Replay. Speed = four presets. Script budget ≥ 3 minutes at 1×.

### 3.4 Tabs — keep three, starve two

**You:** Map / Data / Source weighting.

**Me:** Keep all three so the *idea* of the system shows. Starve complexity:

- **Map** — 70% of runtime.  
- **Data** — one screen: 6–8 featured polity cards (not all 28), click one → one histogram + one timeline. Math in one collapsible line.  
- **Sources** — one screen: 4–5 trust bars + one settlement step animation (not a full Phase 2b tape replay). Math: α,β update in one box.

**→ Decide:** No fourth tab. No PortalGC. No pre-modern share animation in alpha.

### 3.5 Narration

**You:** Lightweight Feynman-style, male voice.

**Me:** Keep Web Speech for α (zero API keys, works offline-ish). Prefer male English voice when the browser offers one. Script in short turns (≤ 2 sentences per beat) so parents can breathe. Optional later: bake a single recorded VO track — out of alpha scope.

---

## 4. Suggested runtime spine (~3–5 min at 1×)

| # | Wall clock (1×) | View | Beat |
| --- | ---: | --- | --- |
| 1 | 0:00–0:45 | Map (frozen) | Problem: sparse demography, nobody keeps score; show grey-out + RGB legend |
| 2 | 0:45–1:05 | Map | Dummy settlement in words (hit/miss → Beta); still frozen |
| 3 | 1:05–1:25 | Map | Start clock; play 1900→~1920 at 2× then return to 1× |
| 4 | 1:25–1:50 | Data | Cold cards; open one example; one equation |
| 5 | 1:50–2:20 | Sources | Two–three settlements; bars move; back to map |
| 6 | 2:20–4:20 | Map | Five beacon pauses (Continue-gated); arcs + short blurb each |
| 7 | 4:20–4:50 | Map | Outro grey → dark; three findings lines |

Times are soft; **Continue gates** guarantee we don’t under-run if someone reads slowly.

---

## 5. Conversation: cool vs simple

**You:** Cool visuals go a long way; few humans will understand the system.

**Me:** Cool = **readable geography + intentional motion**, not shader flex.

Ship for alpha:

- Basemap parallax-free, full bleed  
- Grey-out breathe in during intro  
- Arc draw-on when an edge activates  
- Beacon halo on affected polities  
- Outro: in-scope fills desaturate to charcoal  

Cut for alpha:

- Particle swarms  
- Triple nested religion rings  
- Live Beta PDF plotting  
- Auto-racing through beacons without Continue  

Understanding comes from **pausing on a real country people recognize** (Egypt, Israel, Syria, Turkey) while one sentence lands — not from more math panels.

---

## 6. Build plan (next implementation pass)

1. **Basemap asset** — acquire open raster (or generate); frame like the reference screenshot; store under `movie-alpha/assets/basemap.webp` (+ LICENSE note).  
2. **GeoJSON slice** — MENA + diaspora polygons; id map to `polity_id`.  
3. **Map rewrite** — canvas/SVG overlay: grey-out, borders, RGB strokes, active arcs; drop abstract LAYOUT as primary (keep LAYOUT only as fallback label anchors if needed).  
4. **Transport UX** — speed presets, beacon Continue / Replay, tour scrub = pause tour.  
5. **Script timing** — rewrite `tour.js` copy to ≥3 min; gate beacons.  
6. **Starve Data/Sources** — featured subset; shorter settlement demo.  
7. **Parents dry-run** — watch once muted, once with voice; fix anything that needs a PhD.

Out of scope for this plan: mp4 export, recorded VO, Leaflet/Mapbox tiles, medieval beacon fills, mobile polish.

---

## 7. Open questions (answer before coding the map)

1. **Publishability:** Is this parents-only (Google crop OK locally), or will it live on GitHub / a talk? → drives basemap choice.  
2. **Diaspora:** On-map dots in Europe/NA vs side legend only?  
3. **Palestine / labels:** Display name policy on the basemap overlay (match desk `palestinian_territories`).  
4. **Default speed for the tour:** 1× with voice, or 1× map + slightly faster between beacons?

---

## 8. One-line contract

**Alpha movie = real map, grey-out, RGB borders, three thin tabs, ≥3 minutes of Feynman voice, hard stops at five beacons with rewind — nothing else until parents understand the desk.**

---

## 9. Decisions taken (implementation pass — 14 July 2026)

Answers to §7, plus deviations from the draft where the draft was over- or under-specified. This section is the build record; the sections above stay as the conversation that produced it.

1. **Publishability → open data only.** The repo is public on GitHub, so the Google screenshot never ships. Basemap is **rendered live from a Natural Earth 50m countries slice** (public domain) rather than a raster image: `scripts/build_movie_basemap.py` clips/quantizes the GeoJSON to the reference frame (N. Atlantic → India, N. Europe → Sahel) and writes `movie-alpha/assets/world_frame.json`. This beats a `.webp` on every axis — we own it, it scales with the canvas, borders/fills/grey-out are all the same geometry, and there is no license text beyond "Natural Earth, public domain."
2. **Diaspora → polygons in frame, chips off frame.** France, UK, Germany, Greece are real polygons inside the frame like everyone else. United States and Canada sit outside the frame and become **callout chips** on the Atlantic edge (label + RGB dot + arc terminus) — no second world map, per §3.2.
3. **Palestine / labels →** join on Natural Earth codes (`ADM0_A3`/`ISO_A3_EH`, which handle NE's `-99` and `PSX`/`SAH` quirks), display the desk's names (`Palestinian Territories`, `Western Sahara`).
4. **Default speed → 1×**, presets **0.5× / 1× / 2× / 4×** as big buttons (the old 0.35–5× `<select>` is gone). The tour manages its own pacing between beacons and restores the user's preset when it ends.
5. **Concentric rings → cut entirely** (draft already leaned this way). The gamma-weighted RGB stroke encodes the full M/C/J mix; a second religion ring added geometry-inset complexity for no comprehension gain. Fill opacity encodes **confidence** (the draft's "confidence or pop — pick one": population already drives label size and arcs, confidence is the honest thing to show fading between anchors).
6. **Scrub-during-tour → pause + resume, not abort.** The tour is now a **beat queue**: scrubbing or pressing Pause tour freezes it at the current beat ("free scrub"), and **Resume tour** continues from that beat. Beacons are hard gates: auto-pause with **Continue** and **Replay beacon** (rewind ~8 years, re-approach, re-narrate). A silent watch cannot under-run 3 minutes because five Continue gates require clicks.
7. **Velocity → stroke pulse only.** Outline width breathes with share velocity + |net migration|; countries never balloon (illegibility rule from §3.2.5).
8. **Particles → cut.** Arcs draw on with a progress sweep when an edge activates; no particle swarms in alpha.
