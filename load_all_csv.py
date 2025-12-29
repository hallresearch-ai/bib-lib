"""
load_all_csvs.py — Concatenate all CSVs in a directory and sort by 'title'.

Notes:
- Reads all *.csv in the given directory (non-recursive).
- Uses outer/union of columns; missing values are left blank.
- Sorts case-insensitively by 'title' if present; otherwise leaves order as-is.
"""

### Imports and configs

import logging
import os
import pandas as pd
from pathlib import Path
import sys

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

def main():

    data_dir = 'bib_files'
    dir_path = Path(data_dir).expanduser().resolve()

    csv_files = sorted(p for p in dir_path.iterdir() if p.suffix.lower() == ".csv")
    if not csv_files:
        logger.info(f'No .csv files found in {data_dir}')
        sys.exit(0)

    frames = []
    for p in csv_files:
        try:
            # read as strings to avoid dtype conflicts across files (bibliographic data works well as text)
            df = pd.read_csv(p, dtype=str, keep_default_na=True)
            frames.append(df)
            logger.info(f'Loaded: {p.name}  ({df.shape[0]} rows, {df.shape[1]} cols).')
        except Exception as e:
            logger.info(f'Skipping {p.name}: {e}')

    combined = pd.concat(frames, axis=0, ignore_index=True, sort=True)

    # Sort by 'title' if available (case-insensitive), placing missing titles at the end
    if 'title' in combined.columns:
        # ensure string type for sorting; NaNs handled separately via na_position
        combined['title'] = combined['title'].astype('string')
        combined = combined.sort_values(
            by='title',
            key=lambda s: s.str.lower(),
            na_position='last',
            kind="mergesort"  # stable
        )
    else:
        logger.info("Warning: 'title' column not found — output will not be sorted by title.")

    out_path = data_dir + os.sep + 'combined.csv'
    combined.to_csv(out_path, index=False)
    logger.info(f'Saved combined CSV: {out_path}  ({combined.shape[0]} rows, {combined.shape[1]} cols).')

if __name__ == "__main__":
    main()