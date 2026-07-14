# Beacon schema & inventory conventions

**Date:** 14 July 2026  
**Branch:** `feature/event-beacons`  
**Companions:** `STRATEGY_EVENT_BEACONS.md`, `data/processed/beacons.jsonl`, `docs/beacon-inventories/`

---

## 1. `beacons.jsonl` record schema (v0)

One JSON object per line. Beacons are the **research-ops queue**; they are not yet `Event` rows. Promotion into `events.jsonl` requires polity membership + cited edges (see STRATEGY meta commentary).

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `beacon_id` | string | yes | Stable snake_case id |
| `title` | string | yes | Short display title |
| `period_label` | string | yes | Era label from STRATEGY §2 |
| `year_start` | int | yes | Inclusive |
| `year_end` | int \| null | yes | Inclusive; null = ongoing |
| `research_priority` | enum | yes | `very_high` \| `high` \| `medium_high` \| `medium` \| `low` |
| `video_role` | string | yes | Narrative beat for eventual mp4 |
| `demographic_significance` | string | yes | Why this is a movement beacon |
| `affected_polities` | string[] | yes | Best-effort modern/successor ids; may be empty for pre-modern |
| `linked_event_ids` | string[] | yes | Existing `events.jsonl` ids when already seeded |
| `status` | enum | yes | `stub` \| `inventory` \| `partial_ingest` \| `ingested` |
| `seed_references` | string[] | yes | Short citations from STRATEGY §3 (may be empty) |
| `inventory_path` | string \| null | no | Path under `docs/beacon-inventories/` |
| `notes` | string | no | Free text |

`status` transitions: `stub` → `inventory` (bibliography filed) → `partial_ingest` / `ingested` (processed data + BIBLIOGRAPHY row).

---

## 2. Source quality gate (v0 — learn as we build)

Inventories may list candidates that fail the gate; they must be marked `gate: reject` or `gate: caution` so they never silently enter the settlement tape.

### Accept (`gate: accept`)

- Peer-reviewed journal articles or university-press / established academic monographs
- IGO statistical products (UNHCR, UN DESA, UN WPP, World Bank) with a clear methodology note
- National statistical offices / census publications
- Primary legal instruments (treaties, official gazette tables) with a stable citation
- Datasets already in `data/sources/BIBLIOGRAPHY.md` with an honest ingest note

### Caution (`gate: caution`)

- Contested scholarly estimates used as *inputs only* (McCarthy-class; STRATEGY §6.7)
- Wikipedia / tertiary summaries used as **bootstrap** pointers (must name underlying table/source)
- Advocacy NGOs or think-tank briefs that publish numbers without replicable methods
- High-quality journalism with demographic tables (usable for narrative; weak as validation targets)

### Reject (`gate: reject`)

- Reddit, Quora, TikTok, Twitter/X threads, Facebook groups
- Anonymous or unsourced blogs / “listicle” history sites
- AI-generated pages with no primary citation trail
- Mirror sites / content farms reprinting tables without provenance
- Paywalled titles listed **only** by title with no bibliographic handle (ISBN/DOI/OCLC) — list under `needs_access` instead of inventing a URL

### Open PDF preference (ops rule)

DOI / Cambridge / JSTOR / publisher landing pages often need institutional login. For Conflux ingest we prefer **direct open PDF URLs** that a script can `GET` without cookies:

- Search with Google (or Bright Data SERP) queries ending in `filetype:pdf`.
- Accept: university repositories, Academia.edu/ResearchGate *direct* PDF when openly served, IGO `.pdf` attachments, national-stats PDFs, Internet Archive full-text PDFs, author-posted OA copies.
- Still apply the quality gate on the *work* (peer-reviewed / IGO / NSO). An open PDF of a solid monograph beats a paywalled DOI of the same title.
- Put every scrapeable link in an `## Open PDFs` section (see §3) so `scripts/download_beacon_pdfs.py` can fetch them into `data/raw/beacons/<beacon_id>/`.
- Keep DOI/ISBN as bibliographic handles in the candidate table; do **not** treat a DOI link as downloadable.

### Demographic usefulness filter

A source earns a slot in the inventory only if it offers at least one of:

1. Population totals or religion/ethnicity **shares** for a named polity-year (or bounded range)
2. Migration / refugee / exchange **volumes** with origin–destination (or clear unilateral stock)
3. Conversion / millet / census methodology that constrains how we should read (1) or (2)

Narrative-only works may appear under `context_only` with `gate: caution`.

---

## 3. Beacon inventory document format

Path: `docs/beacon-inventories/BEACON_<beacon_id>.md`

```markdown
# Beacon inventory — <title>

**beacon_id:** …
**Years:** …–…
**Priority:** …
**Status:** inventory
**Linked events:** …

## Candidate sources

| source_id (proposed) | citation | url / handle | years | data type | gate | demographic payload |
| --- | --- | --- | --- | --- | --- | --- |
| … | … | … | … | shares\|volumes\|totals\|methods | accept\|caution\|reject | one-line |

## Open PDFs

Machine-readable for `scripts/download_beacon_pdfs.py`. One bullet per file; URL must end in `.pdf` or clearly serve `application/pdf`.

- `proposed_source_id` — https://example.org/path/paper.pdf

## Already on the desk

Rows that already exist in BIBLIOGRAPHY.md / processed jsonl.

## Gaps / next ingest actions

- …
```

Proposed `source_id`s are **suggestions** until a BIBLIOGRAPHY row lands.

---

## 4. Index

See `docs/beacon-inventories/README.md` for the living table of all beacons and inventory status.
