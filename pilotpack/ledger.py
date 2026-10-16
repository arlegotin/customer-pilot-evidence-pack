"""Transactional, insert-only canonical evidence with portable content identity."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .schema import JsonObject, Packet, ValidationError


_TABLES = ('sources', 'arms', 'source_parents', 'tasks', 'assignments', 'attempts',
           'outcomes', 'outcome_results', 'attempt_results', 'diagnostics')
_RECORDS = ('sources', 'tasks', 'assignments', 'outcomes', 'attempts', 'diagnostics')
_IDENTITIES = dict(sources='source_id', tasks='task_id', assignments='assignment_id',
                   outcomes='assignment_id', attempts='attempt_id')
_DDL = '''
CREATE TABLE sources(source_id TEXT PRIMARY KEY NOT NULL, payload TEXT NOT NULL);
CREATE TABLE arms(arm_id TEXT PRIMARY KEY NOT NULL, payload TEXT NOT NULL);
CREATE TABLE source_parents(source_id TEXT NOT NULL REFERENCES sources(source_id),
 parent_id TEXT NOT NULL REFERENCES sources(source_id), position INTEGER NOT NULL CHECK(position>=0),
 PRIMARY KEY(source_id,position));
CREATE TABLE tasks(task_id TEXT PRIMARY KEY NOT NULL, source_id TEXT NOT NULL REFERENCES sources(source_id), payload TEXT NOT NULL);
CREATE TABLE assignments(assignment_id TEXT PRIMARY KEY NOT NULL,
 task_id TEXT NOT NULL REFERENCES tasks(task_id), arm_id TEXT NOT NULL REFERENCES arms(arm_id),
 settings_id TEXT NOT NULL REFERENCES arms(arm_id), source_id TEXT NOT NULL REFERENCES sources(source_id),
 payload TEXT NOT NULL, UNIQUE(task_id,arm_id));
CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY NOT NULL,
 assignment_id TEXT NOT NULL REFERENCES assignments(assignment_id),
 attempt_index INTEGER NOT NULL CHECK(typeof(attempt_index)='integer' AND attempt_index>=1),
 source_id TEXT NOT NULL REFERENCES sources(source_id), payload TEXT NOT NULL,
 UNIQUE(assignment_id,attempt_index), UNIQUE(assignment_id,attempt_id));
CREATE TABLE outcomes(assignment_id TEXT PRIMARY KEY NOT NULL REFERENCES assignments(assignment_id),
 selected_attempt_id TEXT, source_id TEXT NOT NULL REFERENCES sources(source_id), payload TEXT NOT NULL,
 FOREIGN KEY(assignment_id,selected_attempt_id) REFERENCES attempts(assignment_id,attempt_id));
CREATE TABLE outcome_results(assignment_id TEXT NOT NULL REFERENCES outcomes(assignment_id),
 rank INTEGER NOT NULL CHECK(typeof(rank)='integer' AND rank>=1), payload TEXT NOT NULL,
 PRIMARY KEY(assignment_id,rank));
CREATE TABLE attempt_results(attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
 rank INTEGER NOT NULL CHECK(typeof(rank)='integer' AND rank>=1), payload TEXT NOT NULL,
 PRIMARY KEY(attempt_id,rank));
CREATE TABLE diagnostics(payload TEXT NOT NULL);
'''


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _error(message, code='INVALID_LEDGER'):
    return ValidationError([dict(code=code, severity='error', scope='ledger', source_refs=[], message='ledger: ' + message)])


def _connect(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


def _insert(connection, table, values):
    connection.execute(f'INSERT INTO {table} VALUES ({",".join("?" for _ in values)})', values)


def create_ledger(packet: Packet, db_path: Path) -> None:
    """Publish a complete ledger once; any import failure leaves no destination."""
    db_path = Path(db_path)
    if os.path.lexists(db_path):
        raise _error('destination already exists', 'LEDGER_EXISTS')
    temporary = None
    try:
        descriptor, name = tempfile.mkstemp(prefix='.' + db_path.name + '-', dir=db_path.parent)
        os.close(descriptor)
        temporary = Path(name)
        with closing(sqlite3.connect(temporary)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.executescript(_DDL)
            connection.execute('BEGIN')
            for row in packet.sources:
                _insert(connection, 'sources', (row['source_id'], _json(row)))
            for arm_id, settings in packet.protocol['arms'].items():
                _insert(connection, 'arms', (arm_id, _json(settings)))
            for row in packet.sources:
                for position, parent in enumerate(row['parents']):
                    _insert(connection, 'source_parents', (row['source_id'], parent, position))
            for name in ('tasks', 'assignments', 'attempts', 'outcomes'):
                for row in getattr(packet, name):
                    source_id = row['source_ref'].split('#', 1)[0]
                    identity = row[_IDENTITIES[name]]
                    if name == 'tasks':
                        values = (identity, source_id, _json(row))
                    elif name == 'assignments':
                        values = (identity, row['task_id'], row['arm_id'], row['settings_id'], source_id, _json(row))
                    elif name == 'attempts':
                        values = (identity, row['assignment_id'], row['attempt_index'], source_id, _json(row))
                    else:
                        values = (identity, row['selected_attempt_id'], source_id, _json(row))
                    _insert(connection, name, values)
                    if name in ('attempts', 'outcomes'):
                        result_table = 'attempt_results' if name == 'attempts' else 'outcome_results'
                        for rank, result in enumerate(row['results'], 1):
                            if type(result['rank']) is not int or result['rank'] != rank:
                                raise _error('noncontiguous result rank')
                            _insert(connection, result_table, (identity, rank, _json(result)))
            for row in packet.diagnostics:
                _insert(connection, 'diagnostics', (_json(row),))
            # Compare independent SQL counts to every input collection; no skipping/deduplication.
            for name in _RECORDS:
                count = connection.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                if count != len(getattr(packet, name)):
                    raise _error('source/canonical row count mismatch: ' + name)
            for name, owner in (('attempt_results', 'attempts'), ('outcome_results', 'outcomes')):
                count = connection.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                if count != sum(len(row['results']) for row in getattr(packet, owner)):
                    raise _error('result count mismatch: ' + name)
            for table in _TABLES:
                for operation in ('UPDATE', 'DELETE'):
                    connection.execute(f'''CREATE TRIGGER {table}_no_{operation.lower()}
                        BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable evidence'); END''')
                # REPLACE may delete without DELETE triggers when recursive triggers are off.
                # Guard every unique index (including primary/alternate keys) and hidden rowid.
                conflicts = ['rowid=NEW.rowid']
                indexes = list(connection.execute(f'PRAGMA index_list({table})'))
                for index in indexes:
                    if index[2]:  # UNIQUE; current schema has only ordinary column indexes.
                        columns = [row[2] for row in connection.execute(f'PRAGMA index_info("{index[1]}")')]
                        conflicts.append('(' + ' AND '.join(f'{column}=NEW.{column}' for column in columns) + ')')
                match = ' OR '.join(conflicts)
                connection.execute(f'''CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table}
                    WHEN EXISTS(SELECT 1 FROM {table} WHERE {match})
                    BEGIN SELECT RAISE(ABORT,'immutable evidence'); END''')
            connection.commit()
        # Atomic no-clobber publication; a competing creator cannot overwrite evidence.
        os.link(temporary, db_path)
    except ValidationError:
        raise
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as error:
        raise _error(str(error)) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_records(db_path: Path) -> dict[str, tuple[JsonObject, ...]]:
    """Return canonical records, with result lists read in their stored rank order."""
    try:
        with closing(_connect(Path(db_path))) as connection:
            records = {}
            for name in _RECORDS:
                rows = [json.loads(r[0]) for r in connection.execute(f'SELECT payload FROM {name}')]
                if name in ('outcomes', 'attempts'):
                    table = 'outcome_results' if name == 'outcomes' else 'attempt_results'
                    key = _IDENTITIES[name]
                    for row in rows:
                        row['results'] = [json.loads(r[0]) for r in connection.execute(
                            f'SELECT payload FROM {table} WHERE {key}=? ORDER BY rank', (row[key],))]
                records[name] = tuple(sorted(rows, key=(lambda row: row[_IDENTITIES[name]]) if name in _IDENTITIES else _json))
            return records
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
        raise _error(str(error)) from error


def normalized_digest(db_path: Path) -> str:
    """Hash all evidence columns, independent of SQLite layout or insertion order."""
    try:
        with closing(_connect(Path(db_path))) as connection:
            normalized = {}
            for table in _TABLES:
                cursor = connection.execute(f'SELECT * FROM {table}')
                columns = tuple(d[0] for d in cursor.description)
                rows = []
                for row in cursor:
                    rows.append({key: json.loads(value) if key == 'payload' else value
                                 for key, value in zip(columns, row)})
                normalized[table] = sorted(rows, key=_json)
            return hashlib.sha256((_json(normalized) + '\n').encode('utf-8')).hexdigest()
    except (OSError, sqlite3.Error, ValueError, TypeError) as error:
        raise _error(str(error)) from error


def verify_ledger(db_path: Path, expected_digest: str) -> None:
    """Reject damaged or changed normalized evidence against a frozen digest."""
    try:
        with closing(_connect(Path(db_path))) as connection:
            if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise _error('SQLite integrity check failed', 'LEDGER_INTEGRITY_MISMATCH')
            if connection.execute('PRAGMA foreign_key_check').fetchall():
                raise _error('foreign key check failed', 'LEDGER_INTEGRITY_MISMATCH')
        if normalized_digest(db_path) != expected_digest:
            raise _error('normalized digest differs', 'LEDGER_INTEGRITY_MISMATCH')
    except sqlite3.Error as error:
        raise _error(str(error), 'LEDGER_INTEGRITY_MISMATCH') from error
