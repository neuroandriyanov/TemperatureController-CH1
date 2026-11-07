[Русский](TRANSLATION.md) | **English**

# Publishing in Russian and English

Russian is the source language for new material. Publish the Russian version immediately, then add its English translation alongside it: `README.md` → `README.en.md`, `guide.txt` → `guide.en.txt`, `index.html` → `index.en.html`. Directory names, commands, protocols and source data remain shared.

1. Add or update the Russian document and its source material.
2. Run `python tools/i18n.py status`: `pending` means new material without a translation, `stale` means the Russian source changed after translation, and `unreviewed` means the translation itself changed.
3. Translate the complete document, including tables, captions, alt text and links. Link to English versions of neighboring documents. Preserve values, units, limitations, uncertainty and the context of unsuccessful experiments.
4. Review the specific pair and record it: `python tools/i18n.py record docs/QUICKSTART.md docs/QUICKSTART.en.md`. This command confirms only the listed pairs. It neither translates text nor confirms other material.
5. Check the bundle: `python tools/i18n.py check`. A pending or stale translation does not block publishing Russian material; a broken registered pair needs correction. Before announcing a complete English update, run `python tools/i18n.py check --strict`.

`i18n/manifest.json` stores SHA-256 hashes of both versions. Do not automatically replace old hashes after a source changes: first read and update the translation. Stable filenames identify corresponding versions, while hashes detect changes. The complete pair list is in the manifest's `entries` section.

## Plots, tables and primary data

English plots use `.en.svg` and `.en.png` suffixes. For a new or updated Russian plot, extend the dictionary in `scripts/localize_plots.py`, then run it. The script changes only SVG text and verifies unchanged attributes and geometry. PNG output requires Pillow and either Inkscape or CairoSVG. `python scripts/localize_plots.py --svg-only` needs neither extra renderer. Check label legibility after generation and explicitly record the reviewed pairs.

English BOMs are next to the original XLSX files with `.en.xlsx` suffixes. Translate headings and descriptions while retaining values, formulas, component designators and formatting. Original prices belong to the source BOM and are not updated by translation.

Photographs and thermograms are primary evidence. They are not retouched: instrument readings and original screen annotations remain intact, with explanations and alt text translated separately. “Нет данных” means “No data”; “Нет температуры” means “No temperature”. Original schematic PDFs already contain English title blocks and technical identifiers, so both languages use them without duplication.

Firmware, executable code, Modbus addresses, CLI/API identifiers, logs, measurement JSON/CSV, Gerber/STL and original licenses are shared. Desktop application interfaces retain their existing presentation; English instructions explain Russian control labels. The knowledge base has `index.en.json` and `facts.en.json`: descriptions are translated while exact evidence references, identifiers, statuses and numerical values are preserved.

## Historical evidence

`MANIFEST.sha256` records the historical bundle and is not rewritten for translation. Russian `firmware/docs/HARDWARE.md`, `firmware/docs/PROTOCOL.md`, `hardware/README.md`, `docs/VALIDATION.md` and `knowledge/OPEN_QUESTIONS.md` retain the bytes pinned by the knowledge base. Generated `firmware/docs/REGISTERS.md` is also not edited manually. Their English versions are adjacent and accessible from the [English README](../README.en.md) and translation manifest. The separate `i18n/manifest.json` tracks the translation state.

Original evidence and register-map checks: `python scripts/knowledge.py --check` and `python firmware/scripts/register_map.py --check`. Translation does not establish new hardware tests or alter the conclusions of existing experiments.
