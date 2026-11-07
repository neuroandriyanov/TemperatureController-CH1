# Local source format

[Русский](FORMAT.md) | **English**

`schema_version: 1.0`, `project_id: temperaturecontroller_ch1`, `bundle_format: local-hashed-sources-1`.

The main `sources`, `hardware_versions`, `components`, `connections` collections serve the same purposes as the NeuroAndriyanov project catalog. An additional `facts.json` stores software and experimental facts; this is a local-package extension, not a claim of compatibility with an existing server importer.

Sources: id, title, kind, repository, commit, path, url, sha256, accessed_at, notes. In the published package, repository contains `owner/name`, commit is the full SHA of the commit containing the source, and url is a permanent GitHub link to that file. Relative path and sha256 allow the local copy to be checked without a network. The source commit may predate the current HEAD: it fixes the exact document version checked. When changing a source, update its hash, commit and link together after reviewing dependent facts.

Facts: id, statement, value, unit, status, evidence[{source_id, locator}], notes. A null value means there is no result. `document_confirmed` requires evidence; reasons for other statuses are in notes. `locator` is checked as an existing phrase/symbol in the text source; citation meaning and completeness are additionally reviewed by a human/AI.

Until a complete netlist is independently checked, `connections` remains empty. Signal functions are described as facts based on HARDWARE.md and source code, without invented component/pin numbers. Hardware versions distinguish original documentation from the modified bench device.
