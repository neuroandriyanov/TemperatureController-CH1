[Русский](FORMAT.md) | **English**

# Local source format

`schema_version: 1.0`, `project_id: temperaturecontroller_ch1`, `bundle_format: local-hashed-sources-1`.

The main `sources`, `hardware_versions`, `components` and `connections` collections serve the same purposes as in the NeuroAndriyanov project catalog. The additional `facts.json` file stores software and experimental facts; this is a local-package extension, not a claim of compatibility with an existing server importer.

Sources: id, title, kind, repository, commit, path, url, sha256, accessed_at, notes. In the published set, repository contains `owner/name`, commit is the full SHA of the commit containing the source, and url is a permanent GitHub link to that file. A relative path and sha256 allow offline verification of the local copy. A source commit may precede the current HEAD: it pins the reviewed document version. After changing a source, update its hash, commit and link together, after reviewing dependent facts.

Facts: id, statement, value, unit, status, evidence[{source_id, locator}], notes. A null value means that there is no result. `document_confirmed` requires evidence; for other statuses the reason is given in notes. The `locator` is checked as an existing phrase or symbol in the text source; a person or AI must additionally review the meaning and completeness of the citation.

Until a complete netlist has been independently checked, `connections` remains empty. Signal assignments are described as facts based on HARDWARE.md and source code, without invented component or pin numbers. Hardware versions distinguish the original documentation from the modified bench unit.
