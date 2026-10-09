# bib-lib

Update [library/library-cleaned.csv](library/library-cleaned.csv), then generate
[library/library-cleaned.bib](library/library-cleaned.bib). Existing citation keys
stay fixed.

## 1. Set up

Run these commands from the repository root (Python 3.10 or later):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r workflow/requirements.txt
```

## 2. Edit or import records

Edit the working CSV locally, or edit it in the
[Google Sheet](https://docs.google.com/spreadsheets/d/1D2wzFolo1nkxmbdTPNE84XIV4MrpkRGdofcLQhvnf-8/edit)
and download the bibliography tab. Keep all columns as plain text and preserve
existing citation keys. Leave new keys blank.
See [library format](library/README.md) for field conventions.

For additions, put reviewed entries in `library/inbox/to_add_update.bib` and run:

```bash
python workflow/library_workflow.py import library/inbox/to_add_update.bib
```

Clear that pending file only after reviewing the imported records.
For replacing existing records, see [update options](workflow/README.md).

## 3. Export and check

After local CSV edits:

```bash
python workflow/write_all.py
python workflow/library_workflow.py check
```

To adopt a downloaded sheet, use
`python workflow/write_all.py --input /path/to/downloaded-library.csv`,
then run the same check. This updates the working CSV and BibTeX.

## 4. Review and commit

```bash
python -m unittest discover -s workflow/tests -v
git status --short
git diff -- library
git add library
git diff --cached --check
git diff --cached
git commit -m "Update library"
```

The library folder includes the CSV, BibTeX, key registry, and updated history.
Stage workflow or documentation changes separately when needed, and review all
existing staged changes before committing.

## Where things live

- [library/](library/README.md): current CSV, BibTeX, and key registry;
  `inbox/` holds pending imports and `history/` holds the ongoing change log.
- [workflow/](workflow/README.md): commands, dependencies, and tests.
- [old/](old/README.md): historical libraries, reviewed workbooks, audit evidence,
  snapshots, one-time tools, and prompts.
