# Beacon inventory — Abbasid Caliphate & Cultural Golden Age

**beacon_id:** `abbasid_conversion_750_1258`  
**Years:** 750–1258  
**Priority:** medium_high  
**Status:** inventory  
**Linked events:** (none)

## Candidate sources

| source_id (proposed) | citation | url / handle | years | data type | gate | demographic payload |
| --- | --- | --- | --- | --- | --- | --- |
| `bulliet_1979_conversion_medieval` | Bulliet, R. W. *Conversion to Islam in the Medieval Period: An Essay in Quantitative History*. Harvard UP, 1979. ISBN 9780674170353; DOI [10.4159/harvard.9780674732810](https://doi.org/10.4159/harvard.9780674732810) | https://doi.org/10.4159/harvard.9780674732810 | 750–1258 (regional curves) | methods, shares | accept | S-curve conversion models from Muslim-name frequencies in biographical dictionaries; regional chapters on Iran, Iraq, Egypt/Tunisia, Syria |
| `bulliet_1970_jesho_quant_bio` | Bulliet, R. W. "A Quantitative Approach to Medieval Muslim Biographical Dictionaries." *JESHO* 13:1 (1970), 195–211. DOI [10.1163/156852070X00123](https://doi.org/10.1163/156852070X00123) | https://doi.org/10.1163/156852070X00123 | 7th–12th c. (method seed) | methods | accept | Foundational onomastic/biographical-dictionary method underlying later conversion curves; elite traffic-flow proxy for Nishapur |
| `bulliet_2017_conversion_curve_revisited` | Bulliet, R. W. "The Conversion Curve Revisited." In *Islamisation: Comparative Perspectives from History*, Edinburgh UP, 2017. DOI [10.3366/edinburgh/9781474417129.003.0004](https://doi.org/10.3366/edinburgh/9781474417129.003.0004) | https://doi.org/10.3366/edinburgh/9781474417129.003.0004 | 750–1258 | methods, shares | accept | Revisits 1979 logistic curves; defends and refines name-frequency methodology for medieval Islamization |
| `brett_2017_berber_islamisation` | Brett, M. "Conversion of the Berbers to Islam/Islamisation of the Berbers." In Peacock (ed.), *Islamisation: Comparative Perspectives from History*. Edinburgh UP, 2017. DOI [10.1515/9781474417136-013](https://doi.org/10.1515/9781474417136-013) | https://doi.org/10.1515/9781474417136-013 | 7th–15th c. (N. Africa focus) | methods | accept | Frames Berber Islamisation as incremental assimilation; questions collective-conversion model — constrains North Africa share timing |
| `goitein_1967_mediterranean_society_v1` | Goitein, S. D. *A Mediterranean Society*, Vol. I: *Economic Foundations*. UC Press, 1967/1999. ISBN 9780520221581; hdl [2027/heb.00888](https://hdl.handle.net/2027/heb.00888) | https://www.ucpress.edu/books/a-mediterranean-society-volume-i/paper | 969–1258 (Fatimid/Abbasid Egypt) | totals, methods | accept | Cairo Geniza document-base proxy for urban population, trade networks, and minority-community scale under Abbasid/Fatimid rule |
| `lapidus_2014_history_islamic_societies` | Lapidus, I. M. *A History of Islamic Societies*, 3rd ed. Cambridge UP, 2014. ISBN 9780521732970 | Cambridge UP product page | 750–1258 | context_only | caution | Narrative on multi-century conversion tempo and dhimmī policy; modern Muslim-% tables are not period anchors |
| `kennedy_2022_prophet_caliphates` | Kennedy, H. *The Prophet and the Age of the Caliphates*, 4th ed. Routledge, 2022. ISBN 9781032314549 | Routledge product page | 750–1050 | context_only | caution | Jizya disincentive and slow post-conquest Islamisation; no regional share curves — policy context only |
| `morony_1984_iraq_after_conquest` | Morony, M. G. *Iraq After the Muslim Conquest*. Princeton UP, 1984. ISBN 9780691053952 | https://archive.org/details/iraqaftermuslimc0000moro | 634–c.850 (Iraq baseline) | shares, methods | caution | Ethnoreligious community taxonomy for Iraq; mostly pre-Abbasid but sets Iraq conversion baseline |

## Open PDFs

- `fentress_2012_islamizing_berber_lifestyles` — https://medievalworlds.net/0xc1aa5572%200x003d894d.pdf
- `bulliet_conversion_social_change_lecture` — https://edwebcontent.ed.ac.uk/sites/default/files/imports/fileManager/Conversion%20and%20Social%20Change%20%20in%20Early%20Islamic%20Iran.pdf
- `wood_christians_middle_east_600_1000` — https://almuslih.org/wp-content/uploads/2024/11/Wood-P-%E2%80%93-Christians-in-the-Middle-East-600-1000.pdf
- `fenwick_2023_conquest_to_conversion_north_africa` — https://discovery.ucl.ac.uk/id/eprint/10167594/1/04%2BFenwick%2BFinal%2Bonline%2Bversion%2BMarch%2B22%2B2023.pdf

No open full-text PDF found for Bulliet 1979 monograph / JESHO 1970 / 2017 chapter, or Brett 2017.

## Already on the desk

- Seed references in `beacons.jsonl`: Bulliet (1979), Lapidus — not yet in `BIBLIOGRAPHY.md` or processed jsonl.
- No ingested conversion-curve rows or polity-year share anchors for this beacon.

## Gaps / next ingest actions

- Digitize Bulliet (1979) regional S-curves (Iran, Iraq, Egypt, Syria) as separate claim families with explicit onomastic-method metadata.
- Add North Africa branch via Brett (2017); do not merge with Bulliet curves without region tags.
- Crosswalk Goitein Geniza urban proxies to `egypt` polity-year rows (Fustat/Cairo, 10th–13th c.).
- Flag Lapidus/Kennedy as narrative context only — not validation targets for share claims.

**Skipped (REJECT):** Brewminate listicle on medieval Holy Land demography; unauthorized dokumen.pub mirror of *Islamisation* volume.
