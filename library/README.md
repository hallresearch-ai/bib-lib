# Central library

| File or folder | Purpose |
| --- | --- |
| [library-cleaned.csv](library-cleaned.csv) | Canonical working sheet; replaces combined.csv |
| [library-cleaned.bib](library-cleaned.bib) | Generated BibTeX for manuscripts |
| [citation-key-registry.json](citation-key-registry.json) | Permanent citation-key assignments and aliases |
| [inbox/](inbox/) | Pending additions and reviewed imports |
| [history/](history/) | Ongoing workflow audit log |

The reviewed XLSX and original cleanup evidence are in
[old/audits/2026-10-08](../old/audits/2026-10-08/README.md).
That workbook is a historical snapshot; CSV commands do not update it.

## Editing conventions

Keep all 31 headers. Import spreadsheet columns as **plain text** to preserve
ISBN leading zeros, report numbers, dates, and keys. Sort rows freely.
Missing values stay empty; literal `NA` remains literal text.

- `entry_type` and `title` are required.
- Preserve assigned `citation_key` values. Leave a new key blank for assignment
  on export; never use a row-number formula.
- Personal authors use `Family, Given`, joined by `and`.
- Corporate authors use braces, for example
  `{National Institute of Standards and Technology}`.
- Retain title braces protecting capitalization, such as `{AI}`.
- `year` is a publication year, not an access year; undated records stay blank.
- `flag` is TRUE/FALSE for manual issue tracking. CSV has no red formatting,
  and flag is never exported to BibTeX.

To delete a record, remove its CSV row and export. Its registered key stays
reserved. Keep the registry with the CSV and commit registry changes with the
CSV and BibTeX.

## Citation keys

The rule is **LeadNameYearShortTitle**: first author's surname (including
particles), publication year, and the first three significant title words.
Braced organizations use three significant name words; missing authors fall
back to the first editor, institution/organization, then Anon. Undated works
use `nd`. LaTeX and Latin accents become ASCII. Collisions receive deterministic
hash suffixes. Once assigned, keys remain fixed through sorting, metadata
corrections, deletion, and later collisions.

The exact rule is in [stable_citation_keys.py](../workflow/stable_citation_keys.py).
For manuscripts using old keys, consult the
[migration map](../old/audits/2026-10-08/citation-key-migration.csv).
Historical audit references resolve through the
[full key map](../old/audits/2026-10-08/citation-key-map.csv).

## History

[history/workflow-audit.jsonl](history/workflow-audit.jsonl) records the CSV
handoff and imports/exports that change output files, with content hashes and
bibliographic changes. Historical entries retain their original paths; use
the [archive relocation guide](../old/audits/2026-10-08/README.md) to locate them.

Export checks structure and lossless conversion. It does not externally verify
names, titles, dates, or URLs.
