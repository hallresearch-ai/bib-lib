# Workflow commands

Run these commands from the repository root. Dependencies are in
[requirements.txt](requirements.txt); the default data directory is `library/`,
resolved relative to the repository, independently of the current directory.

## Export and validate

```bash
python workflow/write_all.py
python workflow/library_workflow.py check
```

Export preserves existing keys, assigns blank keys, refreshes the canonical CSV
and BibTeX, and appends changes to `library/history/workflow-audit.jsonl`.
Unchanged runs leave files unchanged. Check validates without writing.

To adopt a downloaded bibliography tab:

```bash
python workflow/write_all.py --input /path/to/download.csv
```

The download remains untouched; the canonical CSV and BibTeX are updated.
`--output /path/to/output.bib` selects another export destination.
For a separate library, use `--directory` with the wrapper, or before the command
with `library_workflow.py`:

```bash
python workflow/library_workflow.py --directory /path/to/library export
```

That directory must include the cleaned CSV and its existing key registry.

## Import additions and replace existing records

```bash
python workflow/library_workflow.py import library/inbox/to_add_update.bib
python workflow/library_workflow.py import /path/to/reviewed-updates.bib --update
```

Only explicitly named files are read. There is no folder scanning or automatic
concatenation of historical libraries/audit tables. New imported records receive
stable keys; existing records match by their current key or a historical alias.

**--update replaces the whole record**, clearing fields absent from the import.
To change a few fields, edit the working CSV instead. Imports do not merge
duplicates automatically or restore deleted keys. Previously removed BibTeX
fields are omitted and listed in the workflow audit; other unknown fields are
rejected. CSV imports use cleaned column names.

## Optional commands

- `python workflow/parser.py input.bib --output library/inbox/staging.csv`
  converts one named BibTeX file to a cleaned staging CSV. Existing destinations
  are not overwritten.
- `python workflow/load_all_csv.py library/inbox/staging.csv` uses the same
  explicit import process.
- `python workflow/update_citation_keys.py` uses the export workflow to assign
  missing keys and synchronize outputs.
- `python workflow/library_workflow.py from-workbook input.xlsx --output output.csv`
  initializes a CSV from a cleaned Bibliography tab, refusing to overwrite an
  existing CSV. This is for a deliberate handoff, not routine maintenance.

## Checks and tests

```bash
python workflow/library_workflow.py check
python -m unittest discover -s workflow/tests -v
```

The workflow preserves text values, validates unique keys and flags, rejects
unsupported columns, and checks complete BibTeX value round-trip equality before
writing. Tests cover imports, updates, deletions, key collisions, repeat runs,
workbook handoff, and CLI entry points.

The [library README](../library/README.md) documents field and citation-key
conventions. One-time cleanup tools are archived in
[old/audits/2026-10-08/tools](../old/audits/2026-10-08/tools/README.md).
