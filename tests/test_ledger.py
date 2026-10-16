"""Transactional evidence preservation and tamper detection through real SQLite."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from support import canonical_records
from pilotpack.schema import Packet, ValidationError
from pilotpack.ledger import create_ledger, read_records, normalized_digest, verify_ledger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet = Packet(**canonical_records(self.root))
        self.db = self.root / 'ledger.sqlite'

    def test_preserves_all_records_and_rank_order_without_invented_attempts(self):
        values = deepcopy(self.packet.outcomes)
        values[0]['results'].append(dict(rank=2, url='https://example.org/second', title='second', snippet='', returned_ids={}))
        packet = replace(self.packet, outcomes=values)
        create_ledger(packet, self.db)
        actual = read_records(self.db)
        self.assertEqual(set(actual), {'sources', 'tasks', 'assignments', 'outcomes', 'attempts', 'diagnostics'})
        for name in actual:
            self.assertCountEqual(actual[name], getattr(packet, name))
        self.assertEqual(actual['outcomes'][0]['results'][1]['url'], 'https://example.org/second')
        self.assertEqual(len(actual['attempts']), 1)
        verify_ledger(self.db, normalized_digest(self.db))

    def test_reordered_equivalent_inputs_have_same_digest(self):
        create_ledger(self.packet, self.db)
        other = self.root / 'other.sqlite'
        create_ledger(replace(self.packet, **{n: tuple(reversed(getattr(self.packet, n)))
                      for n in ('sources', 'tasks', 'assignments', 'outcomes', 'attempts', 'diagnostics')}), other)
        self.assertEqual(normalized_digest(self.db), normalized_digest(other))

    def test_existing_database_bytes_untouched(self):
        create_ledger(self.packet, self.db)
        before = self.db.read_bytes()
        with self.assertRaises(ValidationError):
            create_ledger(self.packet, self.db)
        self.assertEqual(before, self.db.read_bytes())

    def assert_import_rejected(self, **changes):
        with self.assertRaises(ValidationError) as raised:
            create_ledger(replace(self.packet, **changes), self.db)
        self.assertTrue(raised.exception.diagnostics)
        self.assertFalse(self.db.exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['packet'])

    def test_duplicate_logical_assignment_is_rejected(self):
        duplicate = dict(self.packet.assignments[0], assignment_id='duplicate')
        self.assert_import_rejected(assignments=self.packet.assignments + (duplicate,))

    def test_duplicate_attempt_index_is_rejected(self):
        duplicate = dict(self.packet.attempts[0], attempt_id='request2')
        self.assert_import_rejected(attempts=self.packet.attempts + (duplicate,))

    def test_last_row_invalid_rolls_back_entire_import(self):
        invalid = dict(self.packet.attempts[0], attempt_id='orphan', assignment_id='absent')
        self.assert_import_rejected(attempts=self.packet.attempts + (invalid,))

    def test_orphan_task_source_and_selected_attempt_are_rejected(self):
        for name, field, value in [('assignments', 'task_id', 'absent'), ('tasks', 'source_ref', 'absent#$'),
                                   ('outcomes', 'selected_attempt_id', 'absent'),
                                   ('outcomes', 'selected_attempt_id', 'request1')]:
            rows = deepcopy(getattr(self.packet, name))
            rows[-1][field] = value
            with self.subTest(name=name, field=field, value=value):
                self.assert_import_rejected(**{name: rows})

    def test_duplicate_and_noncontiguous_result_ranks_are_rejected(self):
        for rank in (1, 3):
            rows = deepcopy(self.packet.outcomes)
            rows[0]['results'].append(dict(rows[0]['results'][0], rank=rank))
            with self.subTest(rank=rank):
                self.assert_import_rejected(outcomes=rows)

    def test_update_delete_and_replace_rejected_for_every_evidence_table(self):
        child = dict(self.packet.sources[0], source_id='derived', parents=['src'])
        create_ledger(replace(self.packet, sources=self.packet.sources + (child,)), self.db)
        with sqlite3.connect(self.db) as connection:
            tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                column = connection.execute(f'PRAGMA table_info({table})').fetchone()[1]
                statements = [f'UPDATE {table} SET {column}={column}', f'DELETE FROM {table}']
                if table != 'diagnostics':  # No logical key to replace; a new diagnostic may append.
                    statements.append(f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}')
                for sql in statements:
                    with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(sql)

    def test_review_alternate_unique_replacements_are_rejected(self):
        create_ledger(self.packet, self.db)
        digest = normalized_digest(self.db)
        statements = [
            "INSERT OR REPLACE INTO assignments SELECT 'replacement',task_id,arm_id,settings_id,source_id,payload FROM assignments WHERE assignment_id='a:t1'",
            "INSERT OR REPLACE INTO attempts SELECT 'replacement',assignment_id,attempt_index,source_id,payload FROM attempts WHERE attempt_id='request1'",
        ]
        with sqlite3.connect(self.db) as connection:
            connection.execute('PRAGMA recursive_triggers=OFF')
            for sql in statements:
                with self.subTest(sql=sql):
                    try:
                        with self.assertRaises(sqlite3.IntegrityError):
                            connection.execute(sql)
                    finally:
                        connection.rollback()
        self.assertEqual(normalized_digest(self.db), digest)

    def test_review_explicit_rowid_replacements_are_rejected_in_every_table(self):
        child = dict(self.packet.sources[0], source_id='derived', parents=['src'])
        create_ledger(replace(self.packet, sources=self.packet.sources + (child,)), self.db)
        digest = normalized_digest(self.db)
        with sqlite3.connect(self.db) as connection:
            connection.execute('PRAGMA recursive_triggers=OFF')
            tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                info = list(connection.execute(f'PRAGMA table_info({table})'))
                # Give every declared primary/unique key fresh values, isolating rowid collision.
                columns = [r[1] for r in info]
                values = list(connection.execute(f'SELECT rowid,* FROM {table} LIMIT 1').fetchone())
                for index, column in enumerate(columns, 1):
                    if column == 'payload':
                        values[index] = '{}'
                    elif info[index - 1][2] == 'INTEGER':
                        values[index] = 900
                    else:
                        values[index] = 'new:' + column
                for alias in ('rowid', '_rowid_', 'oid'):
                    sql = f'INSERT OR REPLACE INTO {table}({alias},{",".join(columns)}) VALUES ({",".join("?" for _ in values)})'
                    with self.subTest(table=table, alias=alias):
                        try:
                            with self.assertRaises(sqlite3.IntegrityError):
                                connection.execute(sql, values)
                        finally:
                            connection.rollback()
        self.assertEqual(normalized_digest(self.db), digest)

    def test_review_fresh_rows_and_duplicate_diagnostics_can_append(self):
        create_ledger(self.packet, self.db)
        original = normalized_digest(self.db)
        with sqlite3.connect(self.db) as connection:
            connection.execute('PRAGMA recursive_triggers=OFF')
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute("INSERT INTO sources SELECT 'appended',payload FROM sources LIMIT 1")
            connection.execute('INSERT INTO diagnostics SELECT payload FROM diagnostics LIMIT 1')
            connection.execute("INSERT INTO diagnostics(rowid,payload) VALUES(100,'{}')")
            connection.execute("INSERT INTO diagnostics(payload) VALUES('{}')")
        records = read_records(self.db)
        self.assertEqual(len(records['sources']), 2)
        self.assertEqual(len(records['diagnostics']), 4)
        self.assertNotEqual(normalized_digest(self.db), original)

    def test_tampered_json_and_relational_columns_are_detected(self):
        create_ledger(self.packet, self.db)
        digest = normalized_digest(self.db)
        for sql in ("UPDATE tasks SET payload=replace(payload, 'same text', 'changed text')",
                    "UPDATE assignments SET settings_id='a' WHERE settings_id='b'",
                    "UPDATE outcome_results SET rank=9 WHERE assignment_id='a:t1'",
                    "UPDATE outcome_results SET payload=replace(payload, 'arxiv.org', 'example.org')"):
            with self.subTest(sql=sql):
                copy = self.root / 'tamper.sqlite'
                copy.write_bytes(self.db.read_bytes())
                with sqlite3.connect(copy) as connection:
                    triggers = list(connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))
                    for (trigger,) in triggers:
                        connection.execute(f'DROP TRIGGER {trigger}')
                    connection.execute(sql)
                with self.assertRaises(ValidationError):
                    verify_ledger(copy, digest)
                copy.unlink()

    def test_missing_database_is_not_created_by_read_or_verify(self):
        for operation in (read_records, normalized_digest, lambda p: verify_ledger(p, '0' * 64)):
            with self.subTest(operation=operation), self.assertRaises(ValidationError):
                operation(self.db)
            self.assertFalse(self.db.exists())


if __name__ == '__main__':
    unittest.main()
