"""Export library-cleaned.csv to validated BibTeX, preserving stable keys."""
import argparse
import json
from pathlib import Path

from library_workflow import DEFAULT_DIRECTORY, export_library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true', help='Validate without writing files')
    args = parser.parse_args()
    try:
        result = export_library(args.directory, args.input, args.output, args.check)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
