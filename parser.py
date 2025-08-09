#!/usr/bin/env python3

"""
parser.py — Read BibTeX into a pandas DataFrame (bibtexparser required).

Usage
-----
# From a file:
df = bibtex_to_dataframe('references.bib')

# From a string:
df = bibtex_to_dataframe(bibtex_text, from_string=True)

# Save:
df.to_csv('references.csv', index=False)
"""

### Imports and configs

import logging
import os
from typing import Any, Dict, List, Optional, Union
import pandas as pd

import bibtexparser
from bibtexparser.bparser import BibTexParser

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

def bibtex_to_dataframe(
    source: Union[str, bytes],
    *,
    from_string: bool = False,
    include_string: bool = False,
    include_preamble: bool = False,
    include_comment: bool = False,
    preserve_case: bool = True,
    interpolate_strings: bool = True,
    common_strings: bool = True,
) -> pd.DataFrame:

    """
    Parse BibTeX into a pandas DataFrame using bibtexparser.

    Parameters
    ----------
    source : path or raw BibTeX (when from_string=True)
    from_string : treat `source` as raw BibTeX text
    include_string : include this entry type
    include_preamble : include this entry type
    include_comment : include this entry type
    preserve_case : keep field names' original case (default lowercases)
    interpolate_strings : expand @string macros in values
    common_strings : load bibtexparser's common strings (months, etc.)

    Returns
    -------
    pd.DataFrame with columns: entry_type, citation_key, and one column per field seen.

    """

    parser = BibTexParser(common_strings=common_strings)
    parser.interpolate_strings = interpolate_strings
    parser.ignore_nonstandard_types = False  # keep all types in entry

    db = None
    if from_string:
        text = source if isinstance(source, str) else source.decode('utf-8', errors='replace')
        db = bibtexparser.loads(text, parser=parser)
    else:
        with open(source, 'r', encoding='utf-8') as f:
            db = bibtexparser.load(f, parser=parser)

    # decide which structural entries to keep
    allowed_structurals = set()
    if include_string:   allowed_structurals.add("string")
    if include_preamble: allowed_structurals.add("preamble")
    if include_comment:  allowed_structurals.add("comment")

    rows: List[Dict[str, Any]] = []
    all_fields = set()

    for e in db.entries:
        entry_type = e.get("ENTRYTYPE", "")
        et_lower = entry_type.lower()

        # skip structural entries unless requested
        if et_lower in {"string", "preamble", "comment"} and et_lower not in allowed_structurals:
            continue

        citation_key = e.get("ID", "")
        row: Dict[str, Any] = {
            "entry_type": entry_type if preserve_case else et_lower,
            "citation_key": citation_key,
        }

        for k, v in e.items():
            if k in ("ENTRYTYPE", "ID"):
                continue
            field_name = k if preserve_case else k.lower()
            row[field_name] = v
            all_fields.add(field_name)

        rows.append(row)

    # ensure consistent column order: entry_type, citation_key, then sorted fields
    cols = ["entry_type", "citation_key"] + sorted(all_fields)

    # ensure consistent columns across entries
    normalized_rows = [{c: r.get(c) for c in cols} for r in rows]

    return pd.DataFrame(normalized_rows, columns=cols)

### main

def main():

    data_dir = 'bib_files'

    for filename in os.listdir(data_dir):
        if filename.lower().endswith('.bib'):
            bib_path = os.path.join(data_dir, filename)
            logger.info(f'Processing {bib_path} ...')
            try:
                df = bibtex_to_dataframe(bib_path)
                csv_name = os.path.splitext(filename)[0] + '.csv'
                csv_path = os.path.join(data_dir, csv_name)
                df.to_csv(csv_path, index=False)
                logger.info(f'Saved CSV to {csv_path}')
            except Exception as e:
                logger.info('Failed to process {bib_path}: {e}')

if __name__ == "__main__":
    main()
