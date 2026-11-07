[Русский](README.md) | **English**

# Knowledge base · Temperature Controller CH1

Entry point for the engineering assistant: [index.en.json](index.en.json). It contains hardware versions, sources with SHA-256 hashes, and individual verifiable facts in [facts.en.json](facts.en.json). The format is close to the knowledge bases of other NeuroAndriyanov projects; no automatic import into the live website was performed.

English labels are a presentation companion to the [original catalog](index.json). Evidence locators, source paths, commit links, hashes, IDs, statuses and values remain exactly as recorded in the original Russian evidence set.

Reading order: [architecture](ARCHITECTURE.en.md) → [protocol](../firmware/docs/PROTOCOL.en.md) → [hardware limitations](../firmware/docs/HARDWARE.en.md) → [experiments](../measurements/README.en.md) → [open questions](OPEN_QUESTIONS.en.md).

Statuses:

- `document_confirmed`: the fact is explicitly present in the specified document, code or record. For a laboratory result, this confirms the particular series, not universal accuracy.
- `needs_verification`: there is evidence or a hypothesis, but physical or independent verification is required.
- `unknown`: no data; the value remains `null`.

Every fact has a source and locator. Locators refer to a symbol, exact phrase or JSON field. Check hashes with `python scripts/knowledge.py --check`. If a source is deliberately changed, update the catalog using `--refresh` separately, after reviewing the dependent facts.

The catalog specifies repository `neuroandriyanov/TemperatureController-CH1`, a particular commit of the original package, and permanent file links. `path` remains relative to the project root, so SHA-256 verification also works offline. To connect the project to the website, configure its permitted project_id and adapt the local `facts` extension according to [FORMAT.en.md](FORMAT.en.md); publishing the repository does not itself enable website import.
