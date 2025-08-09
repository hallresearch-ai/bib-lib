#!/usr/bin/env python3
"""
write_all.py — Convert a structured CSV of BibTeX entries into a single .bib file.

CSV expectations
- One row per reference.
- Columns:
    - entry_type      (e.g., article, book, misc, ...)
    - citation_key    (unique key per entry; REQUIRED and must be unique)
    - any other BibTeX fields (title, author, year, journal, howpublished, note, ...)

Behavior
- Validates that citation_key values are unique (fails if duplicates found).
- Skips empty fields when writing the entry.
- Preserves CSV column order for fields (except 'entry_type' and 'citation_key').
"""

### Imports and configs

from datetime import datetime
import logging
from pathlib import Path
import os
import pandas as pd
import sys
from typing import Iterable

CONTROL_COLS = {"entry_type", "citation_key"}

### Initialize logging

# console logging config
logger = logging.getLogger(__name__)                                    # init logger
logger.setLevel(logging.INFO)                                           # log level
sh = logging.StreamHandler()                                            # create console handler
sh.setLevel(logging.INFO)                                               # set level to debug
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                              "%Y/%m/%d %H:%M:%S")              # create formatter
sh.setFormatter(formatter)                                              # add formatter
logger.addHandler(sh)                                                   # add handler to logger

def is_nonempty(x) -> bool:

    if x is None:
        return False
    if pd.isna(x):
        return False
    s = str(x).strip()
    return s != ''

def brace_value(v: str) -> str:

    v = str(v)
    sv = v.strip()

    return "{" + v + "}"

def sanitize_field_name(name: str) -> str:
    """
    Keep typical BibTeX field names tidy:
    - lowercase
    - spaces -> underscore
    """
    return name.strip().lower().replace(" ", "_")

def row_to_bibtex(row: pd.Series, field_order: Iterable[str]) -> str:

    entry_type = (row.get('entry_type') or 'misc').strip()
    citation_key = str(row.get('citation_key', '')).strip()
    if not citation_key:
        raise ValueError("Row is missing required 'citation_key'.")

    # build field lines in the provided column order (excluding control cols)
    lines = []
    for col in field_order:
        if col in CONTROL_COLS:
            continue
        val = row.get(col)
        if is_nonempty(val):
            field = sanitize_field_name(col)
            lines.append(f'  {field} = {brace_value(val)}')

    inner = ',\n'.join(lines)
    return f'@{entry_type}{{{citation_key},\n{inner}\n}}\n'

def main():

    time_stamp = datetime.now().strftime("-%Y-%m-%d_%H%M")

    in_file = 'bib_files' + os.sep + 'lib.csv'
    out_file = 'bib_files' + os.sep + 'lib' + time_stamp + '.bib'

    in_path = Path(in_file).expanduser().resolve()
    out_path = Path(out_file).expanduser().resolve()

    if not in_path.is_file():
        logging.error(f"'{in_path}' is not a file.")
        sys.exit(1)

    # read as strings to preserve content verbatim (including leading zeros etc.)
    df = pd.read_csv(in_path, dtype=str, keep_default_na=True)
    N = df.shape[0]

    # basic schema checks
    missing_cols = [c for c in ('citation_key',) if c not in df.columns]
    if missing_cols:
        logging.error(f"CSV missing required column(s): {', '.join(missing_cols)}")
        sys.exit(1)

    # Check uniqueness of citation_key
    dups = df['citation_key'].astype(str).duplicated(keep=False)
    if dups.any():
        dup_keys = df.loc[dups, 'citation_key'].astype(str)
        sample = ", ".join(sorted(set(dup_keys))[:10])
        logging.error('Duplicate citation_key values found.')
        logging.info(f'Examples: {sample}')
        logging.info('Please ensure all citation_key values are unique.')
        sys.exit(1)

    # column order for fields (preserve CSV order)
    field_order = list(df.columns)

    # generate BibTeX
    entries = []
    for i, row in df.iterrows():
        try:
            entry = row_to_bibtex(row, field_order)
            logger.info('---------- ----------')
            logger.info(f'Writing entry {str(i+1)}/{N} ... ')
            logger.info(entry)
            entries.append(entry)
        except Exception as e:
            logging.error(f'Error in row {i}: {e}')
            sys.exit(1)

    # write out
    out_path.write_text('\n'.join(entries), encoding='utf-8')
    logger.info(f'Wrote {len(entries)} entries to {out_path}.')

if __name__ == "__main__":
    main()