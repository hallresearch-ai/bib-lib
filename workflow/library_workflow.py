"""Maintain the cleaned CSV library, its stable keys, and its BibTeX export."""
import argparse
import csv
import hashlib
import io
import json
import re
import tempfile
from pathlib import Path

import bibtexparser
import openpyxl

from stable_citation_keys import POLICY, assign

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRECTORY = ROOT / 'library'
FIELDS = (
    'abstract', 'archiveprefix', 'articleno', 'author', 'booktitle', 'citation_key',
    'date', 'day', 'doi', 'edition', 'editor', 'entry_type', 'eprint', 'howpublished',
    'institution', 'isbn', 'issn', 'issue_date', 'journal', 'location', 'month',
    'number', 'organization', 'pages', 'publisher', 'series', 'title', 'url',
    'volume', 'year', 'flag',
)
CONTROL_FIELDS = {'citation_key', 'entry_type', 'flag'}
REMOVED_FIELDS = {
    'file', 'issue', 'abstractnote', 'author1_email', 'author1_url', 'author2_email',
    'author2_url', 'bdsk-url-1', 'collection', 'contact', 'copyright', 'lccn', 'pdf',
    'pmcid', 'pmid', 'rights', 'annote', 'type', 'numpages', 'shorttitle', 'language',
    'keywords', 'address', 'urldate', 'note', 'primaryclass',
}


def flag_value(value):
    text = str(value or '').strip().upper()
    if text in {'', 'FALSE', '=FALSE()'}:
        return 'FALSE'
    if text in {'TRUE', '=TRUE()'}:
        return 'TRUE'
    raise ValueError(f'Invalid flag {value!r}; use TRUE or FALSE')


def normalize(record):
    unknown = set(record) - set(FIELDS)
    if unknown:
        raise ValueError('Unsupported columns: ' + ', '.join(sorted(unknown)))
    row = {f: str(record.get(f) or '') for f in FIELDS}
    for f in ('citation_key', 'entry_type'):
        row[f] = row[f].strip()
    row['entry_type'] = row['entry_type'].lower()
    row['flag'] = flag_value(row['flag'])
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', row['entry_type']):
        raise ValueError(f"Invalid or missing entry_type for {row['citation_key'] or row['title']!r}")
    if not row['title'].strip():
        raise ValueError(f"Missing title for {row['citation_key']!r}")
    return row


def read_csv(path, full_schema=True):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        if len(set(header)) != len(header):
            raise ValueError('Duplicate CSV column names')
        if set(header) - set(FIELDS):
            raise ValueError('Unsupported CSV columns: ' + ', '.join(sorted(set(header) - set(FIELDS))))
        if full_schema and set(header) != set(FIELDS):
            raise ValueError('Cleaned CSV must have all 31 columns; missing: ' +
                             ', '.join(sorted(set(FIELDS) - set(header))))
        records = []
        for line, raw in enumerate(reader, 2):
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f'CSV row {line} has the wrong number of cells')
            if not any(value.strip() for value in raw.values()):
                continue
            try:
                records.append(normalize(raw))
            except ValueError as error:
                raise ValueError(f'CSV row {line}: {error}') from error
    return records


def csv_text(records):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()


def parse_bib(text):
    library = bibtexparser.parse_string(text)
    if library.failed_blocks:
        raise ValueError(f'BibTeX parsing failed for {len(library.failed_blocks)} blocks')
    records = []
    seen = set()
    for entry in library.entries:
        if entry.key.casefold() in seen:
            raise ValueError(f'Duplicate BibTeX key: {entry.key}')
        seen.add(entry.key.casefold())
        values = {f.key.lower(): str(f.value) for f in entry.fields}
        if len(values) != len(entry.fields):
            raise ValueError(f'Duplicate fields in {entry.key}')
        records.append(dict(values, citation_key=entry.key, entry_type=entry.entry_type))
    return records


def bib_text(records):
    keys = [r['citation_key'] for r in records]
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', k) for k in keys):
        raise ValueError('Citation keys must be literal ASCII letters/digits and begin with a letter')
    if len({k.casefold() for k in keys}) != len(keys):
        raise ValueError('Citation keys must be unique ignoring case')
    text = '\n\n'.join('@' + r['entry_type'] + '{' + r['citation_key'] + ',\n' +
                       ',\n'.join('  ' + f + ' = {' + r[f] + '}' for f in FIELDS
                                  if f not in CONTROL_FIELDS and r[f]) + '\n}'
                       for r in records) + ('\n' if records else '')
    parsed = parse_bib(text)
    expected = [{f: v for f, v in r.items() if f != 'flag' and v} for r in records]
    if parsed != expected:
        raise ValueError('BibTeX round trip changed values; check braces or malformed fields')
    return text


def write_changed(path, text):
    """Validate before calling; atomically replace only files with changed bytes."""
    path = Path(path)
    data = text.encode('utf-8')
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name,
                                     suffix='.tmp', delete=False) as f:
        temp = Path(f.name)
        f.write(data)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return True


def registry_at(directory):
    path = Path(directory) / 'citation-key-registry.json'
    if not path.exists():
        raise ValueError(f'Missing {path}; restore the registry rather than recreating existing assignments')
    registry = json.loads(path.read_text(encoding='utf-8'))
    if registry.get('schema_version') != 1:
        raise ValueError('Unsupported citation-key registry version')
    return registry


def delta(old, new):
    before = {r['citation_key']: r for r in old}
    after = {r['citation_key']: r for r in new}
    changes = []
    for key in sorted(before.keys() | after.keys()):
        if key not in before:
            changes.append(dict(citation_key=key, action='added', after=after[key]))
        elif key not in after:
            changes.append(dict(citation_key=key, action='deleted', before=before[key]))
        else:
            fields = {f: {'before': before[key].get(f, ''), 'after': after[key].get(f, '')}
                      for f in FIELDS if before[key].get(f, '') != after[key].get(f, '')}
            if fields:
                changes.append(dict(citation_key=key, action='updated', fields=fields))
    return changes


def publish(directory, records, registry, operation, check=False, csv_path=None,
            bib_path=None, previous=None, details=None):
    directory = Path(directory)
    csv_path = Path(csv_path or directory / 'library-cleaned.csv')
    bib_path = Path(bib_path or directory / 'library-cleaned.bib')
    registry_path = directory / 'citation-key-registry.json'
    for path in (csv_path, bib_path, registry_path):
        if path.resolve() in {p.resolve() for p in (csv_path, bib_path, registry_path) if p != path}:
            raise ValueError('CSV, BibTeX, and registry paths must be distinct')
    text = bib_text(records)  # Validate every value before writing any file.
    contents = {
        csv_path: csv_text(records),
        bib_path: text,
        registry_path: json.dumps(registry, ensure_ascii=False, indent=2) + '\n',
    }
    changed = [str(p) for p, content in contents.items()
               if not p.exists() or p.read_bytes() != content.encode('utf-8')]
    if check:
        if changed:
            raise ValueError('Files are out of sync; run export: ' + ', '.join(changed))
        return {'records': len(records), 'flagged': sum(r['flag'] == 'TRUE' for r in records),
                'verified': True, 'changed_files': []}
    if not changed:
        return {'records': len(records), 'changed_files': []}
    if previous is None:
        previous = parse_bib(bib_path.read_text(encoding='utf-8')) if bib_path.exists() else []
        # BibTeX deliberately excludes flags; compare against current flags to
        # avoid logging every FALSE value as a bibliographic correction.
        flags = {r['citation_key']: r['flag'] for r in records}
        previous = [dict(r, flag=flags.get(r['citation_key'], 'FALSE')) for r in previous]
    event = {'operation': operation, 'records': len(records),
             'csv_sha256': hashlib.sha256(contents[csv_path].encode()).hexdigest(),
             'bib_sha256': hashlib.sha256(text.encode()).hexdigest(),
             'changes': delta(previous, records), 'details': details or {}}
    log = directory / 'history/workflow-audit.jsonl'
    history = log.read_text(encoding='utf-8') if log.exists() else ''
    for path, content in contents.items():
        write_changed(path, content)
    write_changed(log, history + json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')
    return {'records': len(records), 'changed_files': changed,
            'record_changes': len(event['changes'])}


def export_library(directory=DEFAULT_DIRECTORY, csv_path=None, bib_path=None, check=False):
    directory = Path(directory)
    if csv_path and bib_path and Path(csv_path).resolve() == Path(bib_path).resolve():
        raise ValueError('Input CSV and output BibTeX paths must be distinct')
    records = read_csv(csv_path or directory / 'library-cleaned.csv')
    registry = registry_at(directory)
    keys, registry = assign(records, registry)
    for record, key in zip(records, keys):
        record['citation_key'] = key
    return publish(directory, records, registry, 'export', check=check,
                   bib_path=bib_path, details={'source_csv': str(csv_path or directory / 'library-cleaned.csv')})


def from_workbook(workbook, output):
    output = Path(output)
    if output.exists():
        raise ValueError(f'{output} already exists; workbook import cannot overwrite the working CSV')
    wb = openpyxl.load_workbook(workbook, rich_text=True)
    sheet = wb['Bibliography']
    headers = [c.value for c in sheet[1]]
    if len(headers) != len(set(headers)) or set(headers) != set(FIELDS):
        raise ValueError('Workbook must have the 31 cleaned Bibliography columns')
    records = []
    for row in sheet.iter_rows(min_row=2):
        if all(c.value is None for c in row):
            continue
        raw = {f: str(c.value) if c.value is not None else '' for f, c in zip(headers, row)}
        for f, cell in zip(headers, row):
            if cell.data_type == 'f' and f != 'flag':
                raise ValueError(f'Formula in {cell.coordinate}; use literal metadata and citation keys')
        records.append(normalize(raw))
    bib_text(records)
    write_changed(output, csv_text(records))
    return {'records': len(records), 'output': str(output)}


def import_records(paths, directory=DEFAULT_DIRECTORY, update=False):
    directory = Path(directory)
    original = read_csv(directory / 'library-cleaned.csv')
    records = [dict(r) for r in original]
    registry = registry_at(directory)
    aliases = {a.casefold(): e['key'] for e in registry['entries']
               for a in [e['key']] + e['aliases']}
    reserved = {k.casefold() for k in registry['reserved_keys']}
    current = {r['citation_key']: i for i, r in enumerate(records)}
    ignored = set()
    incoming = []
    for path in paths:
        path = Path(path)
        if path.suffix.lower() == '.bib':
            raw = parse_bib(path.read_text(encoding='utf-8'))
            for row in raw:
                omitted = set(row) & REMOVED_FIELDS
                ignored.update(omitted)
                incoming.append(normalize({f: v for f, v in row.items() if f not in omitted}))
        elif path.suffix.lower() == '.csv':
            incoming.extend(read_csv(path, full_schema=False))
        else:
            raise ValueError(f'Import requires an explicitly named .bib or .csv: {path}')
    touched = set()
    for row in incoming:
        old = row['citation_key']
        key = aliases.get(old.casefold(), old)
        if key and key.casefold() in touched:
            raise ValueError(f'Multiple imported records use key {key}')
        if key:
            touched.add(key.casefold())
        if key in current:
            if not update:
                raise ValueError(f'{old} already exists; use --update to replace this record explicitly')
            row['citation_key'] = key
            records[current[key]] = row
        elif old.casefold() in aliases or old.casefold() in reserved:
            raise ValueError(f'{old} is retired; do not restore a deleted record implicitly')
        else:
            records.append(row)
            if old:
                current[old] = len(records) - 1
    keys, registry = assign(records, registry, migrate=True)
    for row, key in zip(records, keys):
        row['citation_key'] = key
    return publish(directory, records, registry, 'import', previous=original,
                   details={'sources': [str(p) for p in paths], 'update': update,
                            'omitted_removed_fields': sorted(ignored)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIRECTORY)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('export', 'check'):
        command = commands.add_parser(name)
        command.add_argument('--input', type=Path, help='Downloaded cleaned CSV; defaults to library-cleaned.csv')
        command.add_argument('--output', type=Path, help='BibTeX destination; defaults to library-cleaned.bib')
    importer = commands.add_parser('import', help='Import only explicitly named files')
    importer.add_argument('sources', nargs='+', type=Path)
    importer.add_argument('--update', action='store_true', help='Replace a complete existing record by its stable key or alias')
    bootstrap = commands.add_parser('from-workbook', help='Create an initial CSV without overwriting existing CSVs')
    bootstrap.add_argument('workbook', type=Path)
    bootstrap.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'from-workbook':
            result = from_workbook(args.workbook, args.output)
        elif args.command == 'import':
            result = import_records(args.sources, args.directory, args.update)
        else:
            result = export_library(args.directory, args.input, args.output, args.command == 'check')
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
