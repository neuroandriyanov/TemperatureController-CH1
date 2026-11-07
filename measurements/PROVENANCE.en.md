[Русский](PROVENANCE.md) | **English**

# Provenance of the publication copy

`raw` contains saved measurement records from 6–7 November 2026. These are copies with workstation bindings removed: absolute local paths, COM numbers, USB identifiers, tokens and output directories. Numerical samples, time, configurations, validity flags, errors and gaps are preserved. Connection-role identifiers may replace port numbers. Preparatory and unsuccessful measurements are retained to explain diagnostics.

`source-manifest.json` contains the original pre-sanitization hash and published-copy hash for included measurement files. Sanitization changed JSON formatting and hashes; this does not mean readings changed. Correspondence, handoff/session files, personal Flash backups, USB device lists and private application settings are not included.

Photographs are actual frames, without AI generation, retouching of measured values or screen replacement. EXIF/IPTC and comments were removed from JPEGs, and text/EXIF chunks from PNGs; pixel data were not recalculated. Author overlays already present in the original bench frame remain. Only container authorship fields were changed in XLSX files; worksheets and formulas were unchanged. PDF, Gerber and STL technical contents were preserved.

Not every attachment from the original experiments is included. Fields in the original logs may mention unpublished images or service reports; those references do not prove file availability. Missing local attachments are listed in `omitted-attachments.json`. Retained image pairs are in `photos`, and primary numerical series in `raw`. An absolute path completely removed during sanitization is represented by `[local file path omitted]`.

Recalculated plots and statistics are placed in `derived` and `plots`. Four separately reviewed thermograms do not fill gaps in the main log: the derived record specifies the method, palette limitation and manual verification that no menu was present.
