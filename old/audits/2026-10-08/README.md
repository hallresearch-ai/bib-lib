# October 2026 cleanup archive

This folder holds the one-time cleanup history, separate from the active library.

- `library-cleaned.xlsx`: reviewed workbook at the CSV handoff, including its
  historical audit sheets. It is not refreshed by current CSV commands.
- `library-flagged*.xlsx`: manual-review extracts and proposed fixes.
- `change-audit.csv`, `review.csv`, verification tables, JSON/JSONL evidence,
  decisions, and `normalization-policy.txt`: historical cleanup records.
- `citation-key-migration.csv` and `citation-key-map.csv`: legacy-key lookups.
- `manifest.json`: historical provenance and verification results.
- `inputs/`: source BibTeX/workbooks, URL approval sheet, and initial audit report.
- `snapshots/`: original copies from the cleanup; preserve their recorded bytes.
- [tools/](tools/README.md): one-time audit and migration scripts.

Downloaded source PDFs/HTML and extracted text remain local in
`h2o-year-sources/` and `proposed-fixes-sources/`; they are ignored by Git.
Source URLs, decisions, and proposed-fix indexes are retained in version control.

## Locating paths in historical records

Original path strings in audit logs, manifests, snapshots, and scripts remain
unchanged to preserve provenance. Their present locations are:

| Original location | Present location |
| --- | --- |
| `bib_files/normalized-2026-10-08/library-cleaned.csv` | `library/library-cleaned.csv` |
| `bib_files/normalized-2026-10-08/library-cleaned.bib` | `library/library-cleaned.bib` |
| `bib_files/normalized-2026-10-08/citation-key-registry.json` | `library/citation-key-registry.json` |
| `bib_files/normalized-2026-10-08/workflow-audit.jsonl` | `library/history/workflow-audit.jsonl` |
| Other `bib_files/normalized-2026-10-08/` artifacts | This folder, with the same names |
| `bib_files/to_add_update.bib` | `library/inbox/to_add_update.bib` |
| Other top-level `bib_files/` source files | `inputs/` |
| `bib_files/old/` | `old/libraries/` |
| `scripts/audit_2026_10_08/` | `tools/` |
| `prompt/` | `old/prompts/` |
| Root workflow scripts and requirements | `workflow/` |
| `tests/` | `workflow/tests/` |

Temporary research paths such as `/tmp/...` refer to original session caches;
some are no longer available. Consult recorded URLs and decisions for evidence.
