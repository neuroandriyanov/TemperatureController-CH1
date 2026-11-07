# Knowledge base · Temperature Controller CH1

[Русский](README.md) | **English**

English entry point for NeuroEngineer: [index.en.json](index.en.json), with translated source titles and notes. It collects hardware versions, sources with SHA-256 and separate verifiable facts in [facts.en.json](facts.en.json). Its format is close to the knowledge bases of other NeuroAndriyanov projects; it was not automatically imported into the live website. The original [index.json](index.json) and [facts.json](facts.json) remain the inputs to the existing verification script.

Reading order: [architecture](ARCHITECTURE.en.md) → [protocol](../firmware/docs/PROTOCOL.en.md) → [hardware limitations](../firmware/docs/HARDWARE.en.md) → [experiments](../measurements/README.en.md) → [open questions](OPEN_QUESTIONS.en.md).

Statuses:

- `document_confirmed`: the fact is explicitly present in the cited document/code/record. For a laboratory result, this confirms the particular series, not universal accuracy.
- `needs_verification`: there is evidence or a hypothesis, but physical/independent verification is required.
- `unknown`: no data is available; the value remains `null`.

Each fact contains a source and locator. Locators reference a symbol, exact phrase or JSON field. Checksums are checked by `python scripts/knowledge.py --check`. If a source is deliberately changed, catalog `--refresh` is a separate action after reviewing dependent facts.

The catalog specifies repository `neuroandriyanov/TemperatureController-CH1`, a specific commit of the source package and permanent file links. `path` remains relative to the project root, so SHA-256 verification works offline. To connect it to the website, configure its permitted project_id and adapt the local `facts` extension following [FORMAT.en.md](FORMAT.en.md); publishing the repository does not itself enable website import.

English documents are translation sidecars. The original Russian source files, exact locators and pinned commit links remain the provenance authority; translations do not replace the source evidence.
