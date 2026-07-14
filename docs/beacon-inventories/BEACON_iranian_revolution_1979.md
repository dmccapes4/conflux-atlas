# Beacon inventory — Iranian Revolution

**beacon_id:** `iranian_revolution_1979`  
**Years:** 1979–1985  
**Priority:** high  
**Status:** inventory  
**Linked events:** `iranian_revolution_1979` (stub in `events.jsonl`)

## Candidate sources

| source_id (proposed) | citation | url / handle | years | data type | gate | demographic payload |
| --- | --- | --- | --- | --- | --- | --- |
| `iran_sci_census_religion` | Statistical Center of Iran — Population & Housing Censuses (religion item) | https://irandataportal.syr.edu/census/ | 1976, 1986, 1996, 2006, 2011, 2016 | shares / totals | accept | Official religion self-ID; 1976→1986 minority-share collapse (Jewish ~60% drop per census tables) |
| `kamrava_minority_demographics` | Kamrava, Mehran — “Demographic Changes in Iran's Officially Recognized Religious Minority Populations since the Islamic Revolution” | https://doi.org/10.1163/156921002x00077 | 1970s–1990s | shares / methods | accept | Peer-reviewed synthesis: minority decline, urban concentration, higher emigration vs Muslims |
| `sanasarian_religious_minorities_2000` | Sanasarian, Eliz — *Religious Minorities in Iran* (Cambridge UP, 2000) | https://doi.org/10.1017/cbo9780511492259 | 1979–1999 | shares / context | accept | Armenian, Jewish, Zoroastrian, Baha'i legal status + population trends |
| `isdkandaryan_armenians_iran_2019` | Iskandaryan, A. — “Armenians in Iran” (*Global Caucasus Research Journal*) | GCHRJ PDF | 1978–1980s | volumes | accept | Post-revolution Armenian exodus waves; HIAS-facilitated emigration |
| `jewishdatabank_world_jewish_population` | AJYB / DellaPergola — World Jewish Population | https://www.jewishdatabank.org/ | 1970–2023 | totals | caution | Iran Jewish: **80,000** (1970) → **9,100** (2023 CJP) |
| `unhcr_population_api_iran_host` | UNHCR — refugee stock **in** Iran (mostly Afghan/Iraqi) | https://api.unhcr.org/population/v1/population/ | 1979–1985 | volumes | caution | Iran COA refugees 130k (1979) → 2.3M (1985) — **inbound**, not minority outflow |
| `abrahamian_history_modern_iran_2008` | Abrahamian, Ervand — *A History of Modern Iran* (Cambridge UP, 2008) | Cambridge Core | 1900–2000s | context | caution | Revolution political narrative; demographic tables sparse |
| `pew_iran_census_method` | Pew — Global Religious Change methodology (Iran census reliance) | Pew Research methodology page | 2010–2020 | methods | caution | Documents why SCI census is preferred over GAMAAN non-probability polls |

## Open PDFs

- `kamrava_minority_demographics` — https://www.gssrr.org/index.php/JournalOfBasicAndApplied/article/download/17091/6773/47022
- `sanasarian_religious_minorities_2000_frontmatter` — https://assets.cambridge.org/97805217/70736/frontmatter/9780521770736_frontmatter.pdf
- `sanasarian_ajiss_review` — https://www.ajis.org/index.php/ajiss/article/download/2049/1276/3264
- `isdkandaryan_armenians_iran_2019` — https://www.gchrj.net/wp-content/uploads/2024/12/10.Armenian_in_Iran_GCHRJ_3.1.pdf
- `iran_sci_census_form_1996` — https://unstats.un.org/unsd/demographic/sources/census/quest/IRN1996en.pdf
- `iran_sci_census_results_2011` — https://unstats.un.org/unsd/demographic-social/census/documents/Iran/Iran-2011-Census-Results.pdf

No OA full PDF for Abrahamian 2008 or Brill Kamrava (paywalled); substitute open synthesis + census forms above.

## Already on the desk

- Event stub `iranian_revolution_1979` linked to `iran_jewish_exodus_1979_85`
- WJP Iran 80k (1970) / 9.1k (2023); Pew Iran anchors 2010/2020
- UN DESA Iran-origin stocks from 1990 only; UNHCR Iran is host overlay

## Gaps / next ingest actions

- SCI census religion tables 1976 / 1986 / 1996 by province
- Iran→US / Iran→Israel Jewish flows from WJP + HIAS resettlement stats
- Sanasarian + Kamrava for non-Jewish minority edges (Baha'i confidence ≤ 0.35)
- Keep UNHCR Iran COA as host overlay, not revolution emigration
- Upgrade event with Israel-bound Jewish edge once ingested

**Skipped (REJECT):** Goodreads for Abrahamian; GAMAAN polls; Rasanah advocacy PDF; BBC/blog Baha'i headcounts; Reddit threads.
