# Provenance of the publication copy

[Русский](PROVENANCE.md) | **English**

`raw` contains saved measurement records from November 6–7, 2026. These are copies with workstation bindings removed: absolute local paths, COM numbers, USB identifiers, tokens and output directories. Numerical readings, timestamps, configurations, validity flags, errors and gaps are retained. Connection-role identifiers may replace port numbers. Preparatory and unsuccessful measurements are retained to explain diagnosis.

`source-manifest.json` contains the pre-sanitization source-file hash and the published-copy hash for included measurement files. Sanitization changed JSON formatting and hashes; that does not mean readings were changed. Correspondence, handoff/session files, personal Flash backups, USB device inventories and private application settings are not included.

Photographs are real frames, without AI generation, retouching of measured values or screen replacement. EXIF/IPTC and comments were removed from JPEGs, and text/EXIF chunks from PNGs; pixel data was not recalculated. Author overlays already present in original bench frames were retained. In the original XLSX publication copies, only container authorship fields were changed; sheets and formulas were unchanged. PDF, Gerber and STL technical content was retained unchanged.

Not every attachment from the original experiments is included. Original log fields may mention unpublished snapshots/internal reports; such references do not establish file availability. Missing local attachments are listed in `omitted-attachments.json`. Retained pairs are under `photos`; primary numerical series are under `raw`. An absolute path entirely removed during sanitization is represented by `[local file path omitted]`.

Recalculated plots and statistics go into `derived` and `plots`. Four separately reviewed thermograms do not fill gaps in the main log: the derived record specifies the method, palette limitation and manual verification that no menu was present.

English translations and plots are separately named derivatives. They do not modify the Russian publication records or the original numerical series.
