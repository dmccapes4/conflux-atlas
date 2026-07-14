# Review of the planning brief (Grok)

## What to keep

1. **Confidence as a first-class field** — Correct for this domain. Pre-1800 religious shares are scholarly ranges, not census counts. The sim should *show* uncertainty (alpha, hatch, or confidence ring), not hide it behind smooth charts.
2. **Graph model: polity nodes + migration edges + event triggers** — Right shape. Matches how the history actually moves (conquest → outflow → diaspora node growth).
3. **Ottoman millet / refugee mixing** — Worth modeling explicitly. Not “everyone blended”; communal boundaries + large Muslim refugee inflows + elite conversion/integration. Edge types should distinguish *forced migration*, *settlement policy*, *conversion wave*, and *elite integration*.
4. **Phased time** — Start 1800→present, then backfill. Do not try to ship 1000 BCE→2026 in one data pass.
5. **Source stack** — Pew (2010/2020 composition), UN/World Bank totals, Ottoman census tables, then academic syntheses for earlier eras. Sensible priority order.

## What to change or tighten

1. **Do not store one JSON blob per `country_year` as the source of truth.** Prefer:
   - **Anchors**: sparse, cited snapshots (`polity`, `year`, shares, pop, `confidence`, `source_id`)
   - **Events**: discrete triggers with migration deltas
   - **Runtime state**: interpolated from anchors between events  
   Yearly materialization is a *view*, not the archive.
2. **Separate identity layers.** A node should carry:
   - `polity_id` (may rename/split/merge over time)
   - `geo_region_id` (more stable geography)
   - `regime` / government type as its own time series  
   Collapsing “Israel_2026” into the id makes lineage and Ottoman→successor transitions painful.
3. **Fractions + absolute population.** Always keep `total_population` and shares that sum to ~1; never only percentages. Migration edges need absolute volumes.
4. **“Active groups” (PLO, MB, IRGC, …)** — Defer. They are influence overlays, not demographic state. V1 = demography + migration + events. Political orgs as node tags come after the population graph is honest.
5. **Rodney Stark / popular syntheses** — Use cautiously; prefer Cambridge histories, Lapidus, Ottoman demographic specialists, and primary census tables for anything that drives numbers.
6. **Wikipedia as ingest, not authority.** Fine as a bootstrap for Ottoman tables; every row needs a path to a citable secondary/primary source before confidence > ~0.5.
7. **Linear interpolation of religious shares** — Often wrong across conquest/conversion eras. Prefer: hold last anchor until an event; event applies a documented delta; optional smooth only inside calm windows with low confidence.

## Feasibility verdict

**Feasible as a pygame atlas** if scoped like OGrE: one honest loop, visible uncertainty, incremental data.  
**Not feasible** as a single “complete” 3000-year accurate demography dump. The project wins by making sparsity and confidence legible, not by pretending annual ancient precision.

## Naming

**Conflux Atlas** — streams (migrations, conversions, refugee flows) meeting at polity nodes; atlas = inspectable geographic/temporal surface.
