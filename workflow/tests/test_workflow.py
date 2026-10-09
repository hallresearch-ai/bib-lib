import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Direct script commands and unittest discovery use the same workflow modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

from library_workflow import (
    FIELDS, ROOT, bib_text, csv_text, export_library, from_workbook,
    import_records, normalize, parse_bib, publish, read_csv,
)
from stable_citation_keys import assign


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        record = normalize({'citation_key': 'legacy', 'entry_type': 'book',
                            'author': 'Hall, Patrick', 'title': 'Machine learning',
                            'year': '2020', 'isbn': '0123456789', 'abstract': 'NA',
                            'number': '001', 'flag': 'FALSE'})
        keys, self.registry = assign([record], {}, migrate=True)
        record['citation_key'] = keys[0]
        self.key = keys[0]
        self.record = record
        publish(self.base, [record], self.registry, 'initialization')

    def snapshot(self):
        return {str(p.relative_to(self.base)): p.read_bytes()
                for p in self.base.rglob('*') if p.is_file()}

    def incoming(self, text, name='incoming.bib'):
        p = self.base / name
        p.write_text(text)
        return p

    def test_text_and_flags_round_trip_and_repeat_run(self):
        csvfile = self.base / 'library-cleaned.csv'
        rows = read_csv(csvfile)
        self.assertEqual(rows[0]['isbn'], '0123456789')
        self.assertEqual(rows[0]['abstract'], 'NA')
        self.assertEqual(rows[0]['number'], '001')
        self.assertNotIn('flag', parse_bib(bib_text(rows))[0])
        before = self.snapshot()
        export_library(self.base)
        export_library(self.base, check=True)
        self.assertEqual(before, self.snapshot())

    def test_workbook_handoff_preserves_rich_text_and_formula_flags(self):
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = 'Bibliography'
        sheet.append(list(FIELDS))
        row = dict(self.record, author=CellRichText(TextBlock(InlineFont(color='000000'),
                                                           'Hall, Patrick')), flag='=FALSE()')
        sheet.append([row[f] for f in FIELDS])
        path = self.base / 'reviewed.xlsx'
        output = self.base / 'handoff.csv'
        wb.save(path)
        original = path.read_bytes()
        from_workbook(path, output)
        self.assertEqual(read_csv(output), [self.record])
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            from_workbook(path, output)

    def test_sorting_and_metadata_corrections_preserve_keys(self):
        source = self.incoming('@book{new,author={Hall, Patrick},title={Other work},year={2021}}')
        import_records([source], self.base)
        rows = read_csv(self.base / 'library-cleaned.csv')
        original_keys = [r['citation_key'] for r in rows]
        rows[0]['title'] = 'Completely corrected title'
        rows[0]['year'] = '2026'
        (self.base / 'library-cleaned.csv').write_text(csv_text(rows[::-1]))
        export_library(self.base)
        saved = read_csv(self.base / 'library-cleaned.csv')
        self.assertEqual([r['citation_key'] for r in saved], original_keys[::-1])
        self.assertEqual(saved[-1]['citation_key'], self.key)

    def test_alias_update_requires_explicit_update(self):
        source = self.incoming('@book{legacy,author={Hall, Patrick},title={Updated book},year={2024},note={obsolete}}')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            import_records([source], self.base)
        self.assertEqual(before, self.snapshot())
        result = import_records([source], self.base, update=True)
        self.assertEqual(result['records'], 1)
        row = read_csv(self.base / 'library-cleaned.csv')[0]
        self.assertEqual(row['citation_key'], self.key)
        self.assertEqual(row['title'], 'Updated book')
        self.assertNotIn('note', parse_bib((self.base / 'library-cleaned.bib').read_text())[0])

    def test_collision_order_independent_and_existing_key_frozen(self):
        a = dict(self.record, citation_key='', doi='10.1234/one')
        b = dict(self.record, citation_key='', doi='10.1234/two')
        keys, _ = assign([a, b], {}, migrate=True)
        reversed_keys, _ = assign([b, a], {}, migrate=True)
        self.assertEqual(keys, reversed_keys[::-1])
        self.assertNotEqual(keys[0], keys[1])
        saved, _ = assign([self.record, a], self.registry)
        self.assertEqual(saved[0], self.key)
        self.assertNotEqual(saved[0], saved[1])

    def test_multiple_blank_keys_get_distinct_assignments(self):
        rows = [self.record, normalize({'entry_type': 'misc', 'title': 'One new work'}),
                normalize({'entry_type': 'misc', 'title': 'Another new work'})]
        (self.base / 'library-cleaned.csv').write_text(csv_text(rows))
        export_library(self.base)
        saved = read_csv(self.base / 'library-cleaned.csv')
        self.assertEqual(len({r['citation_key'] for r in saved}), 3)
        before = self.snapshot()
        export_library(self.base)
        self.assertEqual(before, self.snapshot())

    def test_deletion_reserves_key_and_import_cannot_restore_it(self):
        (self.base / 'library-cleaned.csv').write_text(csv_text([]))
        export_library(self.base)
        registry = json.loads((self.base / 'citation-key-registry.json').read_text())
        self.assertEqual(registry['entries'][0]['key'], self.key)
        source = self.incoming('@book{legacy,title={Machine learning},year={2020}}')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'retired'):
            import_records([source], self.base)
        self.assertEqual(before, self.snapshot())
        source.write_text('@book{LEGACY,title={Machine learning},year={2020}}')
        with self.assertRaisesRegex(ValueError, 'retired'):
            import_records([source], self.base)

    def test_invalid_rows_fail_before_writing(self):
        for bad in ('bad flag', '=TRUE(1)'):
            with self.assertRaisesRegex(ValueError, 'Invalid flag'):
                normalize(dict(self.record, flag=bad))
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            normalize(dict(self.record, unwanted='field'))
        with self.assertRaises(ValueError):
            bib_text([dict(self.record, title='Unbalanced {title')])
        (self.base / 'library-cleaned.csv').write_text(csv_text([self.record, self.record]))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            export_library(self.base)
        self.assertEqual(before, self.snapshot())

    def test_downloaded_sheet_becomes_canonical(self):
        downloaded = self.base / 'download.csv'
        downloaded.write_text(csv_text([dict(self.record, title='Edited online')]))
        before_download = downloaded.read_bytes()
        export_library(self.base, csv_path=downloaded)
        self.assertEqual(read_csv(self.base / 'library-cleaned.csv')[0]['title'], 'Edited online')
        self.assertEqual(downloaded.read_bytes(), before_download)
        export_library(self.base, check=True)

    def test_explicit_import_does_not_read_other_csvs(self):
        self.incoming('citation_key,detail\nincorrect,audit finding\n', 'audit.csv')
        source = self.incoming('@misc{new,title={New resource},author={{Example Institute}}}')
        import_records([source], self.base)
        self.assertEqual(len(read_csv(self.base / 'library-cleaned.csv')), 2)

    def test_check_detects_drift_without_writing(self):
        bib = self.base / 'library-cleaned.bib'
        bib.write_text(bib.read_text().replace('Machine learning', 'Wrong title'))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'out of sync'):
            export_library(self.base, check=True)
        self.assertEqual(before, self.snapshot())

    def test_cli_wrappers(self):
        for script in ('write_all.py', 'update_citation_keys.py'):
            result = subprocess.run([sys.executable, str(ROOT / 'workflow' / script), '--directory', str(self.base), '--check'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, str(ROOT / 'workflow/load_all_csv.py')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


class ActualLibraryTests(unittest.TestCase):
    def test_current_library_is_synchronized(self):
        base = ROOT / 'library'
        if not (base / 'library-cleaned.csv').exists():
            self.skipTest('Working CSV has not been initialized')
        rows = read_csv(base / 'library-cleaned.csv')
        self.assertGreater(len(rows), 0)
        self.assertTrue(all(r['flag'] in {'TRUE', 'FALSE'} for r in rows))
        export_library(base, check=True)

    def test_default_command_works_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(ROOT / 'workflow/library_workflow.py'), 'check'],
                                    cwd=temp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['verified'])


if __name__ == '__main__':
    unittest.main()
