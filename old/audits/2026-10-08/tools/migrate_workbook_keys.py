"""Update cleaned XLSX/BibTeX keys while preserving registry assignments.

Run: python update_citation_keys.py --directory bib_files/normalized-2026-10-08
The first migration requires --migrate-existing. Subsequent runs preserve keys.
Requires openpyxl>=3.1, bibtexparser>=2 and pylatexenc.
"""
import argparse
import csv
import json
import shutil
from copy import copy
from pathlib import Path

import bibtexparser
import openpyxl

from stable_citation_keys import POLICY, assign


def csv_sheet(path, sheet):
    with path.open('w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(sheet.values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--migrate-existing', action='store_true')
    args = parser.parse_args()
    base = args.directory
    source = base / 'library-cleaned.xlsx'
    rp = base / 'citation-key-registry.json'
    existing = json.loads(rp.read_text()) if rp.exists() else {}
    if args.migrate_existing and rp.exists():
        raise ValueError('Migration already recorded; rerun without --migrate-existing')
    wb = openpyxl.load_workbook(source, rich_text=True)
    sheet = wb['Bibliography']
    headers = [c.value for c in sheet[1]]
    key_col = headers.index('citation_key')
    rows = list(sheet.iter_rows(min_row=2))
    records = [{field: str(c.value) for field, c in zip(headers, row)
                if c.value is not None} for row in rows]
    old_keys = [r.get('citation_key', '') for r in records]
    populated_keys = [k for k in old_keys if k]
    if len(set(populated_keys)) != len(populated_keys):
        raise ValueError('Source contains duplicate keys')
    # Retired and merged aliases remain permanently unavailable for reuse.
    if not existing:
        reserved = set()
        for row in list(wb['Citation key map'].values)[1:]:
            for key in row[:2]:
                if key and key not in old_keys:
                    reserved.add(key)
        existing['reserved_keys'] = sorted(reserved)
    keys, registry = assign(records, existing, migrate=args.migrate_existing)
    mapping = dict(zip(old_keys, keys))
    changes = {old: new for old, new in mapping.items() if old != new}
    if not changes and rp.exists():
        print(json.dumps({'records': len(records), 'renamed': 0, 'registry_unchanged': True}))
        return
    snapshot = base / 'snapshots/library-cleaned-before-stable-keys.xlsx'
    if args.migrate_existing:
        if snapshot.exists():
            raise ValueError('Migration snapshot already exists')
        shutil.copy2(source, snapshot)
        shutil.copy2(base / 'library-cleaned.bib', snapshot.with_suffix('.bib'))
    preserved = [[(str(c.value) if c.value is not None else None, copy(c._style),
                   copy(c.comment)) for c in row] for row in rows]
    for row, record, key in zip(rows, records, keys):
        old = record.get('citation_key', '')
        row[key_col].value = key
        record['citation_key'] = key
        if old != key:
            wb['Change audit'].append([key, 'citation_key', old, key,
                                      'One-time migration to stable rule v1; assignment frozen in registry.',
                                      'citation-key-registry.json; citation-key-migration.csv'])
    # Preserve every historical before/after value and evidence sheet. Resolve
    # their legacy references through the map rather than rewriting history.
    keymap = wb['Citation key map']
    for row in keymap.iter_rows(min_row=2):
        if row[1].value in changes:
            row[1].value = changes[row[1].value]
            row[2].value = str(row[2].value or '') + '; stable_key_v1'
    known_old = {row[0].value for row in keymap.iter_rows(min_row=2)}
    for old, new in changes.items():
        if old not in known_old:
            keymap.append([old, new, 'stable_key_v1'])
    wb['Policy'].append([POLICY])
    wb['Change audit'].append(['LIBRARY', 'citation_key_policy',
                              'Row-derived title keys; FamilyYearShortTitle advice',
                              POLICY, 'User requested stable, sustainable citation keys.',
                              'stable_citation_keys.py; citation-key-registry.json'])
    control = {'citation_key', 'entry_type', 'flag'}
    bib = '\n\n'.join('@' + r['entry_type'] + '{' + r['citation_key'] + ',\n' +
                      ',\n'.join('  ' + f + ' = {' + r[f] + '}' for f in headers
                                 if f not in control and r.get(f)) + '\n}'
                      for r in records) + '\n'
    parsed = bibtexparser.parse_string(bib)
    assert not parsed.failed_blocks and len(parsed.entries) == len(records)
    exports = {e.key: e for e in parsed.entries}
    for record in records:
        e = exports[record['citation_key']]
        assert e.entry_type == record['entry_type']
        assert {f.key: f.value for f in e.fields} == {
            k: v for k, v in record.items() if k not in control}
    temp = source.with_name('stable-keys.tmp.xlsx')
    wb.save(temp)
    check = openpyxl.load_workbook(temp, rich_text=True)
    for row, saved, key in zip(check['Bibliography'].iter_rows(min_row=2), preserved, keys):
        for i, (cell, prior) in enumerate(zip(row, saved)):
            value = str(cell.value) if cell.value is not None else None
            assert value == (key if i == key_col else prior[0]), cell.coordinate
            assert copy(cell._style) == prior[1] and cell.comment == prior[2], cell.coordinate
    # Verify all other sheets' values and rich text are unchanged except audit,
    # policy and the key map, which deliberately gain migration entries.
    before = openpyxl.load_workbook(source, rich_text=True)
    for original_row, saved_row in zip(before['Bibliography'].iter_rows(min_row=2),
                                       check['Bibliography'].iter_rows(min_row=2)):
        for i, (original, saved) in enumerate(zip(original_row, saved_row)):
            if i != key_col:
                assert original.value == saved.value, saved.coordinate
    for name in before.sheetnames:
        if name in {'Bibliography', 'Change audit', 'Citation key map', 'Policy'}:
            continue
        assert list(before[name].values) == list(check[name].values), name
    temp.replace(source)
    (base / 'library-cleaned.bib').write_text(bib, encoding='utf-8')
    rp.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
    if args.migrate_existing:
        with (base / 'citation-key-migration.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['old_key', 'new_key'])
            writer.writerows(mapping.items())
    csv_sheet(base / 'citation-key-map.csv', wb['Citation key map'])
    csv_sheet(base / 'change-audit.csv', wb['Change audit'])
    with (base / 'normalization-policy.txt').open('a', encoding='utf-8') as f:
        f.write('\n' + POLICY + '\n')
    manifest_path = base / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['field_changes'] = wb['Change audit'].max_row - 1
    manifest['stable_citation_keys'] = {
        'rule_version': 1, 'records': len(records), 'renamed': len(changes),
        'registry': rp.name, 'migration_map': 'citation-key-migration.csv',
        'snapshot': str(snapshot), 'case_insensitive_unique': True,
        'non_key_values_styles_and_flags_preserved_verified': True,
        'bibtex_roundtrip_verified': True,
        'historical_references': 'Legacy keys retained; resolve through citation-key-map.csv',
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'records': len(records), 'renamed': len(changes),
                      'sample': list(changes.items())[:8]}, indent=2))


if __name__ == '__main__':
    main()
