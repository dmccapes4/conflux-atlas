# Conflux Atlas

A `pygame` year-step simulation of **religious demographics, governance, and migration** across the Middle East, North Africa, and diaspora nodes — from early Israelite/Jerusalem eras (~1000 BCE) to the present.

**Conflux** = where populations, faiths, and polity borders meet. Every node and edge carries a **confidence** score; sparse pre-modern estimates stay visibly uncertain until events or better sources raise them.

```
sources ──▶ snapshots (polity × year) ──▶ interpolate ──▶ live graph
event log ──▶ migration edges ──▶ confidence decay / reset
                    │
              pygame: nodes = polities, edges = flows
```

Sibling spirit to [`ogre-work-intelligence`](../ogre-work-intelligence): same viz/stack instincts (pygame + graph), different domain (historical demography, not work-item GC).

## Status

**Demo slice live:** 12 hand-seeded polities (1900/1950/2000) + Pew 2010/2020, 10 migration edges, pygame year scrubber (`hold` anchors + fading edges).

## Quick start

```bash
./run.sh                 # GUI scrubber at 1900
./run.sh --year 1948 --play
./run.sh --smoke         # no GUI — print year views
```

**Keys:** Space play/pause · ←/→ year · Shift+←/→ decade · `[` `]` speed · **D** event-deltas · click node · Esc quit

Node size = population · color = dominant religion · opacity = confidence · arrows = migration edges.

## MakefileBook

```bash
make help          # targets
make verify-all    # data infrastructure → data-validation-reports/VERIFY_*.md
make phase0-reports  # docs/SHAPE_OF_THE_DATA.md + INTER_ANCHOR_VELOCITY.md
make test          # Phase 0 pytest gate (offline)
make test-network  # opt-in live URL probes
make smoke         # same as ./run.sh --smoke
```

## Layout

```
conflux-atlas/
├── conflux/           # Python package (sim, model, viz)
├── data/
│   ├── raw/           # untouched downloads (Pew, UN, Ottoman tables, …)
│   ├── processed/     # normalized JSONL / parquet snapshots + edges
│   └── sources/       # BIBLIOGRAPHY.md + per-source notes
├── docs/              # design notes, schema, era playbooks
├── scripts/           # ingest / normalize helpers
└── README.md
```

## Scope (v0)

| Layer | Start here |
| --- | --- |
| Core polities | Israel/Palestine, Lebanon, Syria, Jordan, Egypt, Iraq, Iran, Turkey, Saudi Arabia |
| North Africa | Morocco, Algeria, Tunisia, Libya |
| Diaspora | France, UK, US (Jewish + Muslim + Christian inflows as relevant) |
| Religions | Muslim, Jewish, Christian, Other/Unaffiliated (expand later: Druze, Yezidi, …) |
| Time | Discrete years; 5–10y steps optional for pre-1800 |

Dynamic historical polities (Judea, Umayyad Caliphate, Ottoman vilayets) come after modern nodes render cleanly.

## License / stance

Objective, sourced, confidence-flagged. No advocacy framing in the engine — citations and uncertainty are the product.
