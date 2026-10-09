"""Import explicitly named CSV/BibTeX files into library-cleaned.csv.

No directory scanning: historical libraries and audit CSVs are never inputs.
"""
import argparse
import json
from pathlib import Path

from library_workflow import DEFAULT_DIRECTORY, import_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='+', type=Path)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument('--update', action='store_true')
    args = parser.parse_args()
    try:
        result = import_records(args.sources, args.directory, args.update)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
