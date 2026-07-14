# Beacon inventories

Living index of research inventories for each row in `data/processed/beacons.jsonl`.  
Schema & quality gate: [`docs/BEACON_SCHEMA.md`](../BEACON_SCHEMA.md). Strategy: [`docs/STRATEGY_EVENT_BEACONS.md`](../STRATEGY_EVENT_BEACONS.md).

| Priority | beacon_id | Years | Inventory | Status |
| --- | --- | --- | --- | --- |
| very_high | `greco_turkish_exchange_1914_1923` | 1914–1923 | [BEACON_…](BEACON_greco_turkish_exchange_1914_1923.md) | inventory |
| very_high | `arab_israeli_jewish_exodus_1948_1951` | 1948–1951 | [BEACON_…](BEACON_arab_israeli_jewish_exodus_1948_1951.md) | inventory |
| very_high | `syrian_civil_war_refugees_2011_present` | 2011– | [BEACON_…](BEACON_syrian_civil_war_refugees_2011_present.md) | inventory |
| high | `rashidun_conquests_632_661` | 632–661 | [BEACON_…](BEACON_rashidun_conquests_632_661.md) | inventory |
| high | `umayyad_expansion_661_750` | 661–750 | [BEACON_…](BEACON_umayyad_expansion_661_750.md) | inventory |
| high | `ottoman_rise_1299_1683` | 1299–1683 | [BEACON_…](BEACON_ottoman_rise_1299_1683.md) | inventory |
| high | `ottoman_peak_1453_1683` | 1453–1683 | [BEACON_…](BEACON_ottoman_peak_1453_1683.md) | inventory |
| high | `lebanese_civil_war_1975_1990` | 1975–1990 | [BEACON_…](BEACON_lebanese_civil_war_1975_1990.md) | inventory |
| high | `iranian_revolution_1979` | 1979–1985 | [BEACON_…](BEACON_iranian_revolution_1979.md) | inventory |
| medium_high | `abbasid_conversion_750_1258` | 750–1258 | [BEACON_…](BEACON_abbasid_conversion_750_1258.md) | inventory |
| medium_high | `ottoman_tanzimat_1800_1914` | 1800–1914 | [BEACON_…](BEACON_ottoman_tanzimat_1800_1914.md) | inventory |
| medium | `muhammad_arabia_unification_610_632` | 610–632 | [BEACON_…](BEACON_muhammad_arabia_unification_610_632.md) | inventory |
| medium | `crusades_1095_1291` | 1095–1291 | [BEACON_…](BEACON_crusades_1095_1291.md) | inventory |
| medium | `mongol_mamluk_1258_1517` | 1258–1517 | [BEACON_…](BEACON_mongol_mamluk_1258_1517.md) | inventory |

Inventories are bibliographies + demographic usefulness notes — **not** ingested data. Promotion still requires BIBLIOGRAPHY rows and processed jsonl.

**Open PDFs:** each inventory should grow an `## Open PDFs` section (direct `.pdf` links, no DOI landings). Fetch with:

```bash
.venv/bin/python scripts/download_beacon_pdfs.py --continue
.venv/bin/python scripts/download_beacon_pdfs.py --continue --insecure   # TLS quirks
# or: make beacon-pdfs
```

`--continue` skips files already on disk and keeps going after 403/HTML/SSL failures (writes `data/raw/beacons/_failures.tsv`). Files land in `data/raw/beacons/<beacon_id>/`.
