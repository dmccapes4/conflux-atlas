# Shape of the Data

*Generated 2026-07-14T10:22:47.439670+00:00. Phase 0 Paper A Figure 1 precursor.*

## Demo-slice anchor density

| polity_id | n | years | gaps (years) | max_gap | conf min–max |
| --- | ---: | --- | --- | ---: | --- |
| `egypt` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.45–0.85 |
| `turkey` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.35–0.92 |
| `israel` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.40–0.92 |
| `lebanon` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.35–0.85 |
| `syria` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.35–0.85 |
| `iraq` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.35–0.85 |
| `iran` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.40–0.85 |
| `saudi_arabia` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.30–0.85 |
| `morocco` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.40–0.85 |
| `yemen` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.35–0.85 |
| `france` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.60–0.92 |
| `united_states` | 5 | [1900, 1950, 2000, 2010, 2020] | 50, 50, 10, 10 | 50 | 0.70–0.92 |

Full anchors.jsonl: **438** rows across **201** polities; year span 1900–2020.

## Missingness notes

- Pre-2010 religion shares for most polities are hand seeds (1900/1950/2000) + Pew 2010/2020.
- Greece is an edge endpoint only (1923 exchange), not a seeded share series.
- Overlay series (WPP/OWID/WJP/DESA) are separate files — see `make verify-all`.

See also `docs/INTER_ANCHOR_VELOCITY.md`.
