# English translation package · 2026-11-07

The English edition contains complete adjacent translations of the authored public Markdown documents, desktop application instructions and API description, an English HTML overview, editable English BOM workbooks, translated knowledge-catalogue text and English measurement plots. Application UI source and control behaviour are outside this documentation release.

## Evidence retained

Original numerical logs, photographs, hardware PDFs, Gerbers, STL, XLSX source workbooks and `measurements/source-manifest.json` remain unchanged. Original knowledge-source documents retain their bytes and pinned commits. Exact evidence locators in `knowledge/index.en.json` and `knowledge/facts.en.json` intentionally retain the source language; IDs, values, evidence and status are unchanged. The English catalog points to the same authoritative source files.

Mutable navigation documents have reciprocal language links. Source documents pinned by the knowledge catalogue, generated register-map output and historical measurement documents keep their original bytes; their English sidecars link back, and the project README provides access to both editions. This avoids invalidating historical evidence solely to insert navigation.

The previous root checksum list is preserved as `docs/manifests/pre-english-2026-11-07.sha256`. It describes the earlier snapshot, including the former navigation text; it is not a checksum list for the updated package. The current `MANIFEST.sha256` is deliberately refreshed for the English release. Translation freshness is tracked independently in [translations.json](../translations.json), following [the workflow](TRANSLATIONS.en.md).

## Reproducing English plots

Install the existing analysis requirements, then run these offline scripts from the project root:

```sh
python measurements/analyze.en.py
python measurements/2026-11-07_heater_60c/scripts/plot_pid_runs.en.py
```

The English generator sidecars retain the original calculations and style, change display text, and write to `plots/en` and `derived/en`. Both derived JSON objects were compared with the Russian generator outputs and matched exactly, including null gaps and original data keys. Seven plots are available as PNG and SVG. The second-run overview for the website is `measurements/2026-11-07_heater_60c/plots/en/pid60_hold5_02.png`.

## Document and workbook checks

The two English XLSX derivatives preserve all **243 numeric cells and 30 formulas** from their original XML worksheets. The power-board total remains **3486**; no currency is inferred. Russian labels in the power BOM are translated, and the already English CPU BOM's worksheet tab is renamed `BOM`. Existing styles are retained, with a slightly wider unit-price column for its translated heading. Both rendered workbooks were reviewed.

All six control-schematic pages and the one power-schematic page were rendered and visually reviewed. Electrical labels and borders were already in Latin technical notation. The [English page and label guide](../hardware/LABELS.en.md) explains the Russian filenames, abbreviations and BOM distinctions; the PDFs themselves are unchanged.

The English HTML overview was checked in a headless browser at widths of **1440 px** and **390 px**. All four images loaded, the language link was present and there was no horizontal page overflow. Both rendered layouts were visually reviewed; the original CSS is unchanged. Local English Markdown/HTML links and Markdown anchors were checked, and `python scripts/knowledge.py --check` passed for **21 sources and 24 evidence records**.

The original package verification report remains historical. This translation work does not represent new flashing, physical measurements, hardware validation or a new check of absolute accuracy.
