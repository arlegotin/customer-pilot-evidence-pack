"""Strict version-one canonical records; decoding never invents evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Packet:
    root: Path
    manifest: JsonObject
    protocol: JsonObject
    sources: tuple[JsonObject, ...]
    tasks: tuple[JsonObject, ...]
    assignments: tuple[JsonObject, ...]
    outcomes: tuple[JsonObject, ...]
    attempts: tuple[JsonObject, ...]
    diagnostics: tuple[JsonObject, ...]


class ValidationError(ValueError):
    def __init__(self, diagnostics: list[JsonObject]):
        self.diagnostics = diagnostics
        super().__init__('; '.join(d['message'] for d in diagnostics))


def _diagnostic(code, location, message, severity='error', refs=None):
    return dict(code=code, severity=severity, scope=location,
                source_refs=refs or [], message=f'{location}: {message}')


def _fail(location, message, code='INVALID_SCHEMA'):
    raise ValidationError([_diagnostic(code, location, message)])


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key {key!r}')
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f'nonfinite constant {value}')


def _decode(text, location):
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        def finite(x):
            if isinstance(x, float) and not math.isfinite(x):
                raise ValueError('nonfinite number')
            if isinstance(x, dict):
                for child in x.values():
                    finite(child)
            if isinstance(x, list):
                for child in x:
                    finite(child)
        finite(value)
        if not isinstance(value, dict):
            raise ValueError('expected a JSON object')
        return value
    except (ValueError, RecursionError) as error:
        _fail(location, str(error), 'INVALID_JSON')


def load_json(path: Path) -> JsonObject:
    try:
        return _decode(path.read_text(encoding='utf-8'), f'{path}:$')
    except (OSError, UnicodeError) as error:
        _fail(f'{path}:$', str(error), 'INVALID_JSON')


def load_jsonl(path: Path) -> tuple[JsonObject, ...]:
    try:
        text = path.read_bytes().decode('utf-8')
        lines = text.split('\n')
        if lines[-1] == '':
            lines.pop()
    except (OSError, UnicodeError) as error:
        _fail(f'{path}:$', str(error), 'INVALID_JSON')
    return tuple(_decode(line, f'{path}:{n}:$') for n, line in enumerate(lines, 1))


def _fields(value, required, optional, loc):
    if not isinstance(value, dict):
        _fail(loc, 'expected object')
    missing = set(required.split()) - value.keys()
    unknown = value.keys() - set((required + ' ' + optional + ' extensions').split())
    if missing or unknown:
        _fail(loc, f'missing fields {sorted(missing)}; unknown fields {sorted(unknown)}')
    if 'limitations' in value:
        _limitations(value['limitations'], loc + '.limitations')
    if 'extensions' in value and not isinstance(value['extensions'], dict):
        _fail(loc + '.extensions', 'expected object')


def _string(value, loc, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value:
        _fail(loc, 'expected nonempty string')


def _integer(value, loc, minimum=0):
    if type(value) is not int or value < minimum:
        _fail(loc, f'expected integer >= {minimum}')


def _number(value, loc, minimum=0, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        _fail(loc, 'number outside permitted finite range')


def _enum(value, choices, loc):
    if value not in choices:
        _fail(loc, f'expected one of {choices}')


def _limitations(value, loc):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        _fail(loc, 'expected list of limitation strings')


def _timestamp(value, loc):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', value):
        _fail(loc, 'expected timezone-aware RFC3339 timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('missing timezone')
        return parsed.astimezone(timezone.utc)
    except ValueError as error:
        _fail(loc, str(error))


def _safe(root, name, loc):
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
        _fail(loc, 'source path must stay under run root', 'UNSAFE_SOURCE_PATH')
    path = root / name
    if not path.resolve().is_relative_to(root):
        _fail(loc, 'source symlink escapes run root', 'UNSAFE_SOURCE_PATH')
    return path


def _sha(value, loc):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        _fail(loc, 'expected lowercase SHA-256')


_SETTINGS = 'provider mode endpoint query_parameters requested_num_results k snippet_chars retry_policy timeout_s concurrency run_window matching_profile'


def _settings(value, loc):
    _fields(value, _SETTINGS, 'limitations source_refs', loc)
    if 'source_refs' in value:
        if not isinstance(value['source_refs'], list):
            _fail(loc + '.source_refs', 'expected list of source references')
        for index, reference in enumerate(value['source_refs']):
            rloc = loc + f'.source_refs[{index}]'
            _string(reference, rloc)
            source, separator, fragment = reference.partition('#')
            if not source or not separator or not (re.fullmatch(r'line=[1-9][0-9]*', fragment) or fragment.startswith('$')):
                _fail(rloc, 'expected source ID plus line/object path')
    _string(value['provider'], loc + '.provider')
    _string(value['matching_profile'], loc + '.matching_profile')
    for key in ('mode', 'endpoint'):
        _string(value[key], loc + '.' + key, nullable=True)
    for key in ('requested_num_results', 'k'):
        _integer(value[key], loc + '.' + key, 1)
    if value['k'] > value['requested_num_results']:
        _fail(loc + '.k', 'k exceeds requested_num_results')
    if value['snippet_chars'] is not None:
        _integer(value['snippet_chars'], loc + '.snippet_chars')
    for key in ('query_parameters', 'retry_policy'):
        if value[key] is not None and not isinstance(value[key], dict):
            _fail(loc + '.' + key, 'expected object or null')
    if value['timeout_s'] is not None:
        _number(value['timeout_s'], loc + '.timeout_s')
    if value['concurrency'] is not None:
        _integer(value['concurrency'], loc + '.concurrency', 1)
    _window(value['run_window'], loc + '.run_window')


def _window(value, loc):
    if value is None:
        return
    _fields(value, 'started_at ended_at', '', loc)
    if _timestamp(value['ended_at'], loc + '.ended_at') < _timestamp(value['started_at'], loc + '.started_at'):
        _fail(loc, 'reversed time window')


def _protocol(value, loc):
    _fields(value, 'schema_version protocol_id adapter_profile matching_profile assignment_basis k snippet_chars retry_selection actual_retry_policy conversion_map_sha256 comparison_window requested_comparisons comparison_blockers bootstrap corruption_manifest_sha256 decision_criteria arms packets', 'status limitations', loc)
    _version(value, loc)
    if 'status' in value:
        _string(value['status'], loc + '.status')
    for key in ('protocol_id', 'adapter_profile', 'matching_profile', 'retry_selection'):
        _string(value[key], loc + '.' + key)
    _enum(value['assignment_basis'], ('predeclared', 'reconstructed', 'unreconstructable'), loc + '.assignment_basis')
    _integer(value['k'], loc + '.k', 1)
    if value['snippet_chars'] is not None:
        _integer(value['snippet_chars'], loc + '.snippet_chars')
    for key in ('conversion_map_sha256', 'corruption_manifest_sha256'):
        if value[key] is not None:
            _sha(value[key], loc + '.' + key)
    _window(value['comparison_window'], loc + '.comparison_window')
    if value['actual_retry_policy'] is not None and not isinstance(value['actual_retry_policy'], dict):
        _fail(loc + '.actual_retry_policy', 'expected object or null')
    for key in ('arms', 'decision_criteria', 'packets'):
        if not isinstance(value[key], dict):
            _fail(loc + '.' + key, 'expected object')
    for arm, settings in value['arms'].items():
        _string(arm, loc + '.arms')
        _settings(settings, loc + '.arms.' + arm)
    for arm, criteria in value['decision_criteria'].items():
        if arm not in value['arms']:
            _fail(loc + '.decision_criteria.' + arm, 'unknown criterion arm')
        if criteria is None:
            continue
        _fields(criteria, '', 'min_delivered_hit_rate max_provider_failure_rate max_unknown_rate', loc + '.decision_criteria.' + arm)
        for key, threshold in criteria.items():
            if key != 'extensions' and threshold is not None:
                _number(threshold, loc + '.decision_criteria.' + arm + '.' + key, maximum=1)
    boot = value['bootstrap']
    _fields(boot, 'seed replicates confidence', '', loc + '.bootstrap')
    _integer(boot['seed'], loc + '.bootstrap.seed')
    _integer(boot['replicates'], loc + '.bootstrap.replicates', 1)
    _number(boot['confidence'], loc + '.bootstrap.confidence', maximum=1)
    _limitations(value['comparison_blockers'], loc + '.comparison_blockers')
    if not isinstance(value['requested_comparisons'], list):
        _fail(loc + '.requested_comparisons', 'expected list')
    for i, pair in enumerate(value['requested_comparisons']):
        _fields(pair, 'arm_a arm_b', '', loc + f'.requested_comparisons[{i}]')
        for field in ('arm_a', 'arm_b'):
            _string(pair[field], loc + f'.requested_comparisons[{i}].' + field)
        if pair['arm_a'] not in value['arms'] or pair['arm_b'] not in value['arms'] or pair['arm_a'] == pair['arm_b']:
            _fail(loc + '.requested_comparisons', 'invalid arm pair')
    for key, packet in value['packets'].items():
        ploc = loc + '.packets.' + key
        _fields(packet, 'archive_run_id source_sha256 cohort_selector', 'excluded_task_manifest supported_task_count supported_source_group_count protected outcomes_inspected comparison_window', ploc)
        for field in ('archive_run_id', 'cohort_selector'):
            _string(packet[field], ploc + '.' + field)
        if 'excluded_task_manifest' in packet:
            _string(packet['excluded_task_manifest'], ploc + '.excluded_task_manifest')
        for field in ('supported_task_count', 'supported_source_group_count'):
            if field in packet:
                _integer(packet[field], ploc + '.' + field)
        for field in ('protected', 'outcomes_inspected'):
            if field in packet and type(packet[field]) is not bool:
                _fail(ploc + '.' + field, 'expected boolean')
        if 'comparison_window' in packet:
            _window(packet['comparison_window'], ploc + '.comparison_window')
        if not isinstance(packet['source_sha256'], dict):
            _fail(ploc, 'expected source hashes object')
        for source, digest in packet['source_sha256'].items():
            _sha(digest, ploc + '.source_sha256.' + source)


def _version(value, loc):
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        _fail(loc + '.schema_version', 'only schema version 1 is supported', 'UNSUPPORTED_VERSION')


def _ids(value, loc):
    if not isinstance(value, dict):
        _fail(loc, 'expected namespace to identifier-list object')
    for namespace, identifiers in value.items():
        _string(namespace, loc)
        if not isinstance(identifiers, list) or any(not isinstance(x, str) or not x for x in identifiers) or identifiers != sorted(set(identifiers)):
            _fail(loc + '.' + namespace, 'expected sorted unique identifier strings')


def _results(rows, loc):
    if not isinstance(rows, list):
        _fail(loc, 'expected ranked list')
    for index, row in enumerate(rows, 1):
        rloc = loc + f'[{index - 1}]'
        _fields(row, 'rank url title snippet returned_ids', '', rloc)
        if type(row['rank']) is not int or row['rank'] != index:
            _fail(rloc + '.rank', 'ranks must be contiguous in response order')
        _string(row['url'], rloc + '.url')
        for key in ('title', 'snippet'):
            if row[key] is not None and not isinstance(row[key], str):
                _fail(rloc + '.' + key, 'expected string or null')
        if not isinstance(row['returned_ids'], dict):
            _fail(rloc + '.returned_ids', 'expected object')


def validate_packet(root: Path) -> Packet:
    root = root.resolve()
    manifest = load_json(root / 'packet.json')
    _fields(manifest, 'schema_version run_id adapter_profile origin assignment_basis intended_count actual_settings attempt_history hashes protocol_sha256', 'assignment_manifest_frozen_at assignment_manifest_sha256 content_id normalized_table_digest reconciliation_note limitations excluded_task_count', 'packet.json:$')
    _version(manifest, 'packet.json:$')
    for key in ('run_id', 'adapter_profile'):
        _string(manifest[key], 'packet.json:$.' + key)
    _enum(manifest['origin'], ('archive', 'new_run'), 'packet.json:$.origin')
    _enum(manifest['assignment_basis'], ('predeclared', 'reconstructed', 'unreconstructable'), 'packet.json:$.assignment_basis')
    limits = manifest.get('limitations', [])
    _limitations(limits, 'packet.json:$.limitations')
    if manifest['assignment_basis'] == 'reconstructed':
        _string(manifest.get('reconciliation_note'), 'packet.json:$.reconciliation_note')
    protocol = load_json(root / 'protocol.json')
    _protocol(protocol, 'protocol.json:$')
    arms = protocol['arms']
    diagnostics = []
    for key in ('actual_settings', 'attempt_history', 'intended_count'):
        if not isinstance(manifest[key], dict) or set(manifest[key]) != set(arms):
            _fail('packet.json:$.' + key, 'must name exactly protocol arms')
    for arm in arms:
        loc = 'packet.json:$.actual_settings.' + arm
        _settings(manifest['actual_settings'][arm], loc)
        unknown = [k for k, v in manifest['actual_settings'][arm].items() if v is None]
        if unknown:
            if not limits:
                _fail(loc, 'unknown settings require explicit limitations')
            diagnostics.append(_diagnostic('UNKNOWN_ACTUAL_SETTINGS', 'arm:' + arm, ', '.join(unknown), 'block'))
        _enum(manifest['attempt_history'][arm], ('complete', 'partial', 'unknown'), 'packet.json:$.attempt_history.' + arm)
        if manifest['attempt_history'][arm] != 'complete':
            diagnostics.append(_diagnostic('UNKNOWN_ATTEMPT_HISTORY', 'arm:' + arm, 'physical history is incomplete', 'limitation'))
        if manifest['intended_count'][arm] is not None:
            _integer(manifest['intended_count'][arm], 'packet.json:$.intended_count.' + arm)
    source_file = load_json(root / 'sources.json')
    _fields(source_file, 'schema_version sources', '', 'sources.json:$')
    _version(source_file, 'sources.json:$')
    if not isinstance(source_file['sources'], list):
        _fail('sources.json:$.sources', 'expected list')
    sources = {}
    for i, source in enumerate(source_file['sources']):
        loc = f'sources.json:$.sources[{i}]'
        _fields(source, 'source_id role source_uri revision acquired_at local_path bytes sha256 license parents command', 'limitations', loc)
        for key in ('source_id', 'role', 'source_uri', 'license', 'command'):
            _string(source[key], loc + '.' + key)
        _string(source['revision'], loc + '.revision', nullable=True)
        if source['revision'] is None and not source.get('limitations'):
            _fail(loc + '.revision', 'absent revision requires documented limitation')
        _timestamp(source['acquired_at'], loc + '.acquired_at')
        _integer(source['bytes'], loc + '.bytes')
        _sha(source['sha256'], loc + '.sha256')
        path = _safe(root, source['local_path'], loc + '.local_path')
        if source['source_id'] in sources:
            _fail(loc, 'duplicate source ID', 'DUPLICATE_SOURCE')
        try:
            raw = path.read_bytes()
        except OSError as error:
            _fail(loc, str(error), 'HASH_MISMATCH')
        if len(raw) != source['bytes'] or hashlib.sha256(raw).hexdigest() != source['sha256']:
            _fail(loc, 'source bytes differ from inventory', 'HASH_MISMATCH')
        sources[source['source_id']] = source
    for index, source in enumerate(sources.values()):
        loc = f'sources.json:$.sources[{index}].parents'
        if not isinstance(source['parents'], list):
            _fail(loc, 'expected list of source identifiers')
        for parent_index, parent in enumerate(source['parents']):
            ploc = loc + f'[{parent_index}]'
            _string(parent, ploc)
            if parent not in sources:
                _fail(ploc, 'unknown transformation parent', 'ORPHAN_RECORD')

    def ref(value, loc):
        if not isinstance(value, str) or '#' not in value:
            _fail(loc, 'expected source ID plus line/object path')
        sid, fragment = value.split('#', 1)
        if sid not in sources:
            _fail(loc, 'unknown source ID', 'ORPHAN_RECORD')
        if not (re.fullmatch(r'line=[1-9][0-9]*', fragment) or fragment.startswith('$')):
            _fail(loc, 'expected line=N or JSON object path')
        return sources[sid], fragment

    rows = {name: load_jsonl(root / (name + '.jsonl')) for name in ('tasks', 'assignments', 'outcomes', 'attempts')}
    tasks, assignments, outcomes, attempts = {}, {}, {}, {}
    logical = set()
    indexes = set()
    for name in rows:
        for n, row in enumerate(rows[name], 1):
            loc = f'{name}.jsonl:{n}:$'
            if name == 'tasks':
                _fields(row, 'task_id source_group_id cohort_id query_text gold_ids bucket source_ref', '', loc)
                for key in ('task_id', 'cohort_id', 'query_text', 'bucket'):
                    _string(row[key], loc + '.' + key)
                _string(row['source_group_id'], loc + '.source_group_id', nullable=True)
                _ids(row['gold_ids'], loc + '.gold_ids')
                identity, table = row['task_id'], tasks
            elif name == 'assignments':
                _fields(row, 'assignment_id task_id arm_id settings_id source_ref', '', loc)
                for key in ('assignment_id', 'task_id', 'arm_id', 'settings_id'):
                    _string(row[key], loc + '.' + key)
                if row['task_id'] not in tasks or row['arm_id'] not in arms or row['settings_id'] not in arms:
                    _fail(loc, 'unknown task/arm/settings', 'ORPHAN_RECORD')
                pair = row['task_id'], row['arm_id']
                if pair in logical:
                    _fail(loc, 'duplicate task/arm assignment', 'DUPLICATE_ASSIGNMENT')
                logical.add(pair)
                identity, table = row['assignment_id'], assignments
            elif name == 'outcomes':
                _fields(row, 'assignment_id observation_kind terminal_status selected_attempt_id results reported_hit_rank source_ref limitations', '', loc)
                _string(row['assignment_id'], loc + '.assignment_id')
                _enum(row['observation_kind'], ('attempt_backed', 'archive_logical', 'unobserved', 'not_dispatched'), loc + '.observation_kind')
                _enum(row['terminal_status'], ('completed', 'provider_error', 'unknown', 'runner_failure'), loc + '.terminal_status')
                _string(row['selected_attempt_id'], loc + '.selected_attempt_id', nullable=True)
                _results(row['results'], loc + '.results')
                if row['reported_hit_rank'] is not None:
                    _integer(row['reported_hit_rank'], loc + '.reported_hit_rank', 1)
                    if row['reported_hit_rank'] > len(row['results']):
                        _fail(loc, 'reported hit rank beyond returned list')
                _results(row['results'], loc + '.results')
                _limitations(row['limitations'], loc + '.limitations')
                identity, table = row['assignment_id'], outcomes
            else:
                _fields(row, 'attempt_id assignment_id attempt_index started_at ended_at status results error latency_ms cost source_ref', 'limitations', loc)
                _string(row['assignment_id'], loc + '.assignment_id')
                _string(row['attempt_id'], loc + '.attempt_id')
                if row['assignment_id'] not in assignments:
                    _fail(loc, 'unknown assignment', 'ORPHAN_RECORD')
                _integer(row['attempt_index'], loc + '.attempt_index', 1)
                _enum(row['status'], ('completed', 'provider_error', 'unresolved'), loc + '.status')
                _results(row['results'], loc + '.results')
                _string(row['error'], loc + '.error', nullable=True)
                _limitations(row.get('limitations', []), loc + '.limitations')
                times = [_timestamp(row[k], loc + '.' + k) if row[k] is not None else None for k in ('started_at', 'ended_at')]
                if all(t is not None for t in times) and times[1] < times[0]:
                    _fail(loc, 'ended_at precedes started_at')
                if row['latency_ms'] is not None:
                    _number(row['latency_ms'], loc + '.latency_ms')
                cost = row['cost']
                _fields(cost, 'amount currency kind source_ref scope', '', loc + '.cost')
                _enum(cost['kind'], ('observed', 'estimated', 'missing'), loc + '.cost.kind')
                _enum(cost['scope'], ('attempt',), loc + '.cost.scope')
                _string(cost['currency'], loc + '.cost.currency', nullable=True)
                if cost['amount'] is not None:
                    if not isinstance(cost['amount'], str) or not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', cost['amount']):
                        _fail(loc + '.cost.amount', 'expected nonnegative decimal string')
                    try:
                        if not Decimal(cost['amount']).is_finite():
                            raise InvalidOperation
                    except InvalidOperation:
                        _fail(loc + '.cost.amount', 'invalid decimal')
                if cost['kind'] == 'missing' and (cost['amount'] is not None or cost['currency'] is not None or cost['source_ref'] is not None):
                    _fail(loc + '.cost', 'missing cost must remain null')
                if cost['kind'] in ('observed', 'estimated') and (cost['amount'] is None or cost['currency'] is None):
                    _fail(loc + '.cost', 'priced cost requires amount/currency')
                if cost['kind'] == 'observed':
                    try:
                        source, fragment = ref(cost['source_ref'], loc + '.cost.source_ref')
                    except ValidationError:
                        _fail(loc + '.cost.source_ref', 'observed cost lacks resolvable provenance', 'INVALID_COST_PROVENANCE')
                    try:
                        evidence = load_json(root / source['local_path']) if fragment == '$' else None
                    except ValidationError:
                        evidence = None
                    if evidence is None or evidence.get('request') != row['attempt_id'] or evidence.get('amount') != cost['amount'] or evidence.get('currency') != cost['currency']:
                        _fail(loc + '.cost', 'observed amount/currency/request must resolve to evidence', 'INVALID_COST_PROVENANCE')
                elif cost['source_ref'] is not None:
                    ref(cost['source_ref'], loc + '.cost.source_ref')
                if (None in times or row['latency_ms'] is None or cost['kind'] == 'missing') and not row.get('limitations'):
                    _fail(loc, 'missing request measurements require limitations')
                if manifest['origin'] == 'new_run' and manifest['attempt_history'].get(assignments.get(row['assignment_id'], {}).get('arm_id')) == 'complete' and None in times:
                    _fail(loc, 'complete new-run requests require timestamps')
                index = row['assignment_id'], row['attempt_index']
                if index in indexes:
                    _fail(loc, 'duplicate attempt index', 'DUPLICATE_ATTEMPT')
                indexes.add(index)
                identity, table = row['attempt_id'], attempts
            if name in ('outcomes', 'attempts') and row['assignment_id'] not in assignments:
                _fail(loc, 'unknown assignment', 'ORPHAN_RECORD')
            ref(row['source_ref'], loc + '.source_ref')
            if identity in table:
                _fail(loc, 'duplicate identity', 'DUPLICATE_ASSIGNMENT' if name == 'assignments' else 'DUPLICATE_RECORD')
            table[identity] = row
    for aid, outcome in outcomes.items():
        selected = outcome['selected_attempt_id']
        if selected is not None and (selected not in attempts or attempts[selected]['assignment_id'] != aid):
            _fail('outcomes.jsonl:$.selected_attempt_id', 'unknown or cross-assignment attempt', 'ORPHAN_RECORD')
    for aid in assignments.keys() - outcomes.keys():
        diagnostics.append(_diagnostic('MISSING_OUTCOME', 'assignment:' + aid, 'intended assignment has no terminal record', 'block'))
    if manifest['origin'] == 'new_run':
        frozen = _timestamp(manifest.get('assignment_manifest_frozen_at'), 'packet.json:$.assignment_manifest_frozen_at')
        _sha(manifest.get('assignment_manifest_sha256'), 'packet.json:$.assignment_manifest_sha256')
        for attempt in attempts.values():
            if attempt['started_at'] is not None and frozen > _timestamp(attempt['started_at'], 'attempts.jsonl:$.started_at'):
                _fail('packet.json:$.assignment_manifest_frozen_at', 'manifest frozen after dispatch', 'MANIFEST_AFTER_DISPATCH')
    hashes = manifest['hashes']
    if not isinstance(hashes, dict):
        _fail('packet.json:$.hashes', 'expected hash map')
    required = {'sources.json', 'protocol.json', 'tasks.jsonl', 'assignments.jsonl', 'outcomes.jsonl', 'attempts.jsonl'} | {s['local_path'] for s in sources.values()}
    if not required <= hashes.keys():
        _fail('packet.json:$.hashes', 'missing canonical/raw file hashes', 'HASH_MISMATCH')
    for name, digest in hashes.items():
        path = _safe(root, name, 'packet.json:$.hashes.' + name)
        _sha(digest, 'packet.json:$.hashes.' + name)
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            _fail('packet.json:$.hashes.' + name, str(error), 'HASH_MISMATCH')
        if digest != actual:
            _fail('packet.json:$.hashes.' + name, 'file bytes differ', 'HASH_MISMATCH')
    if manifest['protocol_sha256'] != hashes['protocol.json']:
        _fail('packet.json:$.protocol_sha256', 'protocol digest differs', 'HASH_MISMATCH')
    return Packet(root, manifest, protocol, tuple(sources.values()), rows['tasks'], rows['assignments'], rows['outcomes'], rows['attempts'], tuple(diagnostics))
