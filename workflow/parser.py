"""Convert one explicitly named BibTeX file to a staging CSV in cleaned format.

For routine additions, library_workflow.py import accepts BibTeX directly.
"""
import argparse
from pathlib import Path

from library_workflow import REMOVED_FIELDS, csv_text, normalize, parse_bib, write_changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError(f'{args.output} already exists; choose a new staging file')
        raw = parse_bib(args.source.read_text(encoding='utf-8'))
        ignored = sorted({f for row in raw for f in row if f in REMOVED_FIELDS})
        rows = [normalize({f: v for f, v in row.items() if f not in REMOVED_FIELDS}) for row in raw]
        write_changed(args.output, csv_text(rows))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(f'Wrote {len(rows)} records to {args.output}')
    if ignored:
        print('Omitted previously removed fields: ' + ', '.join(ignored))


if __name__ == '__main__':
    main()
