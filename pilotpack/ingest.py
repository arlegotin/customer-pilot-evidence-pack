"""Offline normalization and atomic frozen runs for the observed Scholar profile.

Direct archive callers supply config['_context'] = {'protocol': loaded_object,
'sources': loaded_registry, 'source_root': Path}. freeze supplies this runtime
context from its explicit arguments; it never enters content identity.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from pilotpack.ledger import create_ledger, normalized_digest, read_records, verify_ledger
from pilotpack.schema import JsonObject, Packet, ValidationError, load_json, load_jsonl, validate_packet

_TABLES = ('tasks', 'assignments', 'outcomes', 'attempts')
_KEYS = {'tasks': 'task_id', 'assignments': 'assignment_id', 'outcomes': 'assignment_id', 'attempts': 'attempt_id'}
_LIMITS = ['UNKNOWN_ATTEMPT_HISTORY', 'MISSING_COST', 'MISSING_TASK_TIMESTAMPS', 'UNKNOWN_ACTUAL_SETTINGS']
_BINDING = 'raw/normalization-input.json'


def _fail(code: str, scope: str, message: str) -> None:
    raise ValidationError([dict(code=code, severity='error', scope=scope, source_refs=[], message=message)])


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
        _fail('UNSAFE_SOURCE_PATH', str(name), 'expected a relative path inside its provenance root')
    root = root.resolve()
    candidate = root / name
    if not candidate.resolve().is_relative_to(root):
        _fail('UNSAFE_SOURCE_PATH', name, 'path or symlink escapes provenance root')
    return candidate


def _authoritative(manifest: JsonObject) -> JsonObject:
    return {k: v for k, v in manifest.items() if k not in ('hashes', 'protocol_sha256', 'content_id', 'normalized_table_digest')}


def _source(source: JsonObject) -> JsonObject:
    result = dict(source)
    absence = result.pop('revision_absence_reason', None)
    if absence:
        result['limitations'] = list(result.get('limitations', [])) + [absence]
    return result


def _generated(sid: str, path: str, data: bytes, parents: list[str], command: str) -> JsonObject:
    return dict(source_id=sid, role='derived-normalization-evidence', source_uri='local:' + path,
                revision=None, acquired_at='1970-01-01T00:00:00Z', local_path=path, bytes=len(data),
                sha256=_sha(data), license='derived-data', parents=parents, command=command,
                limitations=['Deterministic normalization artifact; timestamp is a fixed serialization marker, not acquisition time.'])


def _reconcile(packet: Packet) -> Packet:
    found = {r['assignment_id'] for r in packet.outcomes}
    missing = [r for r in packet.assignments if r['assignment_id'] not in found]
    outcomes = list(packet.outcomes)
    for row in missing:
        outcomes.append(dict(assignment_id=row['assignment_id'], observation_kind='unobserved',
                             terminal_status='unknown', selected_attempt_id=None, results=[], reported_hit_rank=None,
                             source_ref=row['source_ref'], limitations=['MISSING_OUTCOME', 'NO_DISPATCH_INFERENCE']))
    return replace(packet, outcomes=tuple(outcomes))


def _check_counts(packet: Packet) -> None:
    for arm, expected in packet.manifest['intended_count'].items():
        actual = sum(row['arm_id'] == arm for row in packet.assignments)
        if expected is not None and expected != actual:
            _fail('COUNT_MISMATCH', 'intended_count.' + arm, 'intended count differs from assignment manifest')


def _assignment_manifest(packet: Packet) -> bytes:
    sid = packet.manifest.get('extensions', {}).get('assignment_manifest_source_id')
    if sid is not None:
        source = next((s for s in packet.sources if s['source_id'] == sid), None)
        if source is None:
            _fail('ORPHAN_RECORD', 'assignment_manifest_source_id', 'missing frozen assignment manifest source')
        return _safe(packet.root, source['local_path']).read_bytes()
    return (packet.root / 'assignments.jsonl').read_bytes()


def _check_assignment_manifest(packet: Packet) -> None:
    if packet.manifest['origin'] != 'new_run':
        return
    data = _assignment_manifest(packet)
    if _sha(data) != packet.manifest['assignment_manifest_sha256']:
        _fail('MANIFEST_HASH_MISMATCH', 'packet.json', 'pre-dispatch assignment hash differs from retained manifest bytes')
    try:
        lines = data.decode('utf-8').split('\n')
        if lines[-1] == '':
            lines.pop()
        rows = [_embedded(line, f'assignment-manifest:{n}:$') for n, line in enumerate(lines, 1)]
    except (UnicodeError, ValidationError) as error:
        _fail('MANIFEST_CONTENT_MISMATCH', 'assignment-manifest', 'invalid intended assignment JSONL: ' + str(error))
    if sorted(_bytes(row) for row in rows) != sorted(_bytes(row) for row in packet.assignments):
        _fail('MANIFEST_CONTENT_MISMATCH', 'assignment-manifest',
              'retained pre-dispatch assignment records differ from canonical identities, settings or evidence')


def _conversion_map(packet: Packet, *, frozen: bool = False,
                    source_paths: dict[str, Path] | None = None) -> tuple[Packet, bytes | None]:
    expected = packet.protocol['conversion_map_sha256']
    linkage = packet.manifest.get('extensions', {}).get('conversion_map')
    canonical = _safe(packet.root, 'identifier-map.json')
    exists = canonical.exists()
    candidates = [s for s in packet.sources if s['local_path'] == 'identifier-map.json']
    if linkage is None and not exists and expected is None:
        return packet, None
    if linkage is None and exists and len(candidates) == 1:
        linkage = {'status': 'available', 'source_id': candidates[0]['source_id']}
    if not isinstance(linkage, dict) or linkage.get('status') not in ('available', 'unavailable'):
        _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'conversion_map',
              'a supplied or protocol-pinned map needs a source link or explicit initial unavailability')
    if linkage['status'] == 'unavailable':
        if (set(linkage) != {'status', 'source_id', 'reason'} or linkage['source_id'] is not None
                or not isinstance(linkage['reason'], str) or not linkage['reason'].strip()):
            _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'conversion_map', 'unavailability requires null source_id and an explicit reason')
        if exists or candidates:
            _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'conversion_map', 'unavailable map contradicts supplied bytes/provenance')
        diagnostic = dict(code='MISSING_MATCH_EVIDENCE', severity='block', scope='conversion_map',
                          source_refs=[], message='Required identifier conversion evidence is unavailable: ' + linkage['reason'])
        diagnostics = tuple(d for d in packet.diagnostics if not (d['code'] == 'MISSING_MATCH_EVIDENCE' and d['scope'] == 'conversion_map'))
        return replace(packet, diagnostics=(*diagnostics, diagnostic)), None
    if set(linkage) != {'status', 'source_id'} or not isinstance(linkage['source_id'], str):
        _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'conversion_map', 'available map requires one explicit source ID')
    source = next((s for s in packet.sources if s['source_id'] == linkage['source_id']), None)
    if source is None or expected is None or source['sha256'] != expected:
        _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'conversion_map', 'conversion-map source and protocol hash disagree')
    if frozen and not exists:
        _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'identifier-map.json', 'previously available frozen map is missing')
    source_path = source_paths[source['source_id']] if source_paths is not None else _safe(packet.root, source['local_path'])
    try:
        data = source_path.read_bytes()
    except OSError as error:
        _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'conversion_map', str(error))
    if _sha(data) != expected or len(data) != source['bytes'] or (exists and canonical.read_bytes() != data):
        _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'conversion_map', 'canonical map bytes, provenance and protocol hash disagree')
    try:
        _embedded(data.decode('utf-8'), 'identifier-map.json:$')
    except UnicodeError as error:
        _fail('INVALID_JSON', 'identifier-map.json', str(error))
    manifest = {**packet.manifest, 'extensions': {**packet.manifest.get('extensions', {}), 'conversion_map': linkage}}
    return replace(packet, manifest=manifest), data


def import_canonical(input_dir: Path, config: JsonObject) -> Packet:
    """Validate contained canonical evidence without changing source identities."""
    if config.get('adapter_profile') != 'canonical-v1':
        _fail('UNSUPPORTED_VERSION', 'config.adapter_profile', 'expected canonical-v1')
    _preflight(input_dir)
    packet = validate_packet(input_dir)
    _check_counts(packet)
    _check_assignment_manifest(packet)
    packet, _ = _conversion_map(packet)
    return _reconcile(packet)


def _embedded(text: str, scope: str) -> JsonObject:
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate key ' + key)
            result[key] = value
        return result
    try:
        result = json.loads(text, object_pairs_hook=pairs)
        _bytes(result)
        if not isinstance(result, dict):
            raise ValueError('expected object')
        return result
    except (ValueError, TypeError) as error:
        _fail('INVALID_SCHEMA', scope, str(error))


def _archive(input_dir: Path, config: JsonObject) -> Packet:
    if config.get('adapter_profile') != 'needle-scholar-2026-10-14-v1':
        _fail('UNSUPPORTED_VERSION', 'config.adapter_profile', 'only the acquired Scholar profile is supported')
    if config.get('gold_namespace_required') != 'arxiv':
        _fail('MISSING_MATCH_EVIDENCE', 'config.gold_namespace_required', 'only arXiv gold is supported without the missing historical conversion map')
    evidence = config.get('assignment_evidence')
    if not isinstance(evidence, dict) or evidence.get('kind') != 'coarchived-gold-exact-tuple' or not evidence.get('revision'):
        _fail('UNRECONSTRUCTABLE_ASSIGNMENTS', 'config.assignment_evidence', 'versioned co-archival and exact full-tuple gold evidence required')
    context = config.get('_context')
    if not isinstance(context, dict) or not {'protocol', 'sources', 'source_root'} <= context.keys():
        _fail('MISSING_IMPORT_CONTEXT', 'config._context', 'direct import requires explicit protocol, sources and source_root')
    protocol = context['protocol']
    registry = context['sources']['sources']
    by_id = {r['source_id']: r for r in registry}
    if len(by_id) != len(registry):
        _fail('DUPLICATE_SOURCE', 'sources', 'duplicate source ID')
    run_id = config['run_id']
    policy = protocol['packets'][run_id]
    if policy['archive_run_id'] != config['archive_run_id'] or policy['cohort_selector'] != 'gold.ids.arxiv present':
        _fail('PROTOCOL_MISMATCH', 'config', 'packet identity/selection differs from frozen protocol')
    arms = config['arms']
    if len(set(arms)) != len(arms) or set(arms) != set(protocol['arms']) or 'ultimate' in arms:
        _fail('PROTOCOL_MISMATCH', 'config.arms', 'real selected arms must match protocol arms')
    gold_id, summary_id = evidence['gold_source_id'], evidence['summary_source_id']
    paths = {gold_id: config['gold_path'], summary_id: config['summary_path']}
    for arm in arms:
        paths[run_id + '-' + arm] = 'scholar/' + arm + '.json'
    for sid, name in paths.items():
        source = by_id[sid]
        raw = _safe(input_dir, name).read_bytes()
        if source['revision'] != evidence['revision'] or policy['source_sha256'].get(sid) != source['sha256']:
            _fail('GOLD_VERSION_MISMATCH', sid, 'co-archival revision/source hash lacks protocol evidence')
        if len(raw) != source['bytes'] or _sha(raw) != source['sha256']:
            _fail('HASH_MISMATCH', sid, 'archive bytes differ from acquisition inventory')
    summary = load_json(_safe(input_dir, config['summary_path']))
    gold_rows = load_jsonl(_safe(input_dir, config['gold_path']))
    if summary['num_queries'] != len(gold_rows):
        _fail('COUNT_MISMATCH', summary_id, 'summary/gold inventory count differs')
    for arm in arms:
        settings = config['actual_settings'][arm]
        for field, expected in (('provider', arm), ('requested_num_results', summary['num_results']),
                                ('k', protocol['k']), ('snippet_chars', summary['snippet_chars']),
                                ('matching_profile', protocol['arms'][arm]['matching_profile'])):
            if settings[field] != expected:
                _fail('PROTOCOL_MISMATCH', 'actual_settings.' + arm + '.' + field, 'setting differs from observed report/profile policy')
        for field in ('mode', 'endpoint', 'query_parameters', 'retry_policy', 'timeout_s', 'concurrency', 'run_window'):
            if settings[field] is not None:
                _fail('UNPROVED_ACTUAL_SETTING', 'actual_settings.' + arm + '.' + field, 'archive has no actual request parameter evidence')
    by_key, ids, selected, excluded = {}, set(), {}, []
    for line, row in enumerate(gold_rows, 1):
        gold = _embedded(row['gold'], f'{gold_id}#line={line}.gold')
        origin = _embedded(row['query_origin'], f'{gold_id}#line={line}.query_origin')
        key = (row['query_text'], gold['paper_key'], origin['bucket'])
        if key in by_key or row['query_id'] in ids:
            _fail('DUPLICATE_RECORD', gold_id + '#line=' + str(line), 'duplicate query identity or ambiguous full tuple')
        ids.add(row['query_id'])
        by_key[key] = (row, gold, origin, line)
        if 'arxiv' in gold['ids']:
            selected[key] = by_key[key]
        else:
            excluded.append(dict(task_id=row['query_id'], paper_key=gold['paper_key'], source_line=line,
                                 reason='MISSING_HISTORICAL_PMC_PMID_MAP'))
    tasks, assignments, outcomes = [], [], []
    for row, gold, origin, line in selected.values():
        tasks.append(dict(task_id=row['query_id'], source_group_id=gold['paper_key'], cohort_id=config['cohort_id'],
                          query_text=row['query_text'], gold_ids={k: sorted({str(v)}) for k, v in gold['ids'].items()},
                          bucket=origin['bucket'], source_ref=f'{gold_id}#line={line}'))
    for arm in arms:
        path = summary['engines'][arm]['per_query_path']
        if path != paths[run_id + '-' + arm]:
            _fail('PROTOCOL_MISMATCH', summary_id, 'unexpected engine artifact path')
        engine = load_json(_safe(input_dir, path))
        observed = {}
        for index, row in enumerate(engine['per_query']):
            key = row['query'], row['paper_key'], row['bucket']
            if key in observed:
                _fail('DUPLICATE_RECORD', f'{arm}#$.per_query[{index}]', 'duplicate full tuple')
            if key not in by_key:
                _fail('ORPHAN_RECORD', f'{arm}#$.per_query[{index}]', 'terminal full tuple has no gold')
            if type(row['n_results']) is not int or row['n_results'] != len(row['results']):
                _fail('COUNT_MISMATCH', f'{arm}#$.per_query[{index}]', 'n_results differs from results')
            observed[key] = row, index
        for key, (row, gold, origin, line) in selected.items():
            aid = arm + ':' + row['query_id']
            assignments.append(dict(assignment_id=aid, task_id=row['query_id'], arm_id=arm, settings_id=arm,
                                    source_ref=f'{gold_id}#line={line}'))
            if key not in observed:
                continue
            terminal, index = observed[key]
            results = [dict(rank=n, url=r['url'], title=r.get('title'), snippet=r.get('snippet'), returned_ids=r.get('ids', {}))
                       for n, r in enumerate(terminal['results'], 1)]
            outcomes.append(dict(assignment_id=aid, observation_kind='archive_logical',
                                 terminal_status='provider_error' if terminal['search_error'] is not None else 'completed',
                                 selected_attempt_id=None, results=results, reported_hit_rank=terminal['hit_rank'],
                                 source_ref=f'{run_id}-{arm}#$.per_query[{index}]', limitations=list(_LIMITS)))
    baselines = config.get('baseline_source_ids', {})
    if not isinstance(baselines, dict) or set(baselines) - {'native', 'oracle', 'check'} or any(not isinstance(sid, str) for sid in baselines.values()):
        _fail('INVALID_SCHEMA', 'config.baseline_source_ids', 'expected explicit native/oracle/check source IDs')
    selected_sources = set(paths) | set(config.get('auxiliary_source_ids', [])) | set(baselines.values())
    conversion = config.get('conversion_map')
    if isinstance(conversion, dict) and conversion.get('status') == 'available':
        sid = conversion.get('source_id')
        if not isinstance(sid, str):
            _fail('CONVERSION_MAP_INTEGRITY_MISMATCH', 'config.conversion_map', 'available map requires a source ID')
        selected_sources.add(sid)
    pending = list(selected_sources)
    while pending:
        sid = pending.pop()
        if sid not in by_id:
            _fail('ORPHAN_RECORD', 'sources:' + sid, 'missing required provenance source')
        for parent in by_id[sid]['parents']:
            if parent not in selected_sources:
                selected_sources.add(parent)
                pending.append(parent)
    if any(sid.startswith('packet-') and not sid.startswith(run_id + '-') for sid in selected_sources):
        _fail('PROTECTED_SOURCE', 'sources', 'configuration selects another packet source')
    sources = tuple(_source(by_id[sid]) for sid in sorted(selected_sources))
    manifest = dict(schema_version=1, run_id=run_id, adapter_profile=config['adapter_profile'], origin='archive',
                    assignment_basis='reconstructed', intended_count={a: len(tasks) for a in arms},
                    actual_settings=config['actual_settings'], attempt_history={a: 'unknown' for a in arms},
                    excluded_task_count=len(excluded), hashes={}, protocol_sha256='',
                    reconciliation_note='Intended arXiv cohort reconstructed from versioned co-archival and exact (query_text,paper_key,bucket) correspondence; no dispatch inferred.',
                    limitations=['PMID_COHORT_EXCLUDED_MISSING_CONVERSION_MAP', *_LIMITS],
                    extensions={'selection': {'cohort_id': config['cohort_id'], 'selector': policy['cohort_selector']},
                                'native_profile': 'needle-scholar-all-rows-v1', 'baseline_source_ids': baselines,
                                'raw_task_count': len(gold_rows), 'excluded_tasks': excluded})
    if conversion is not None:
        manifest['extensions']['conversion_map'] = conversion
    return _reconcile(Packet(input_dir, manifest, protocol, sources, tuple(tasks), tuple(assignments), tuple(outcomes), (), ()))


def import_needle_scholar(input_dir: Path, config: JsonObject) -> Packet:
    """Normalize only the documented versioned archive profile; no live lookup."""
    try:
        packet = _archive(Path(input_dir), config)
        root = Path(config['_context']['source_root'])
        paths = {s['source_id']: _safe(root, s['local_path']) for s in packet.sources}
        return _conversion_map(packet, source_paths=paths)[0]
    except (KeyError, TypeError, IndexError, ValueError) as error:
        if isinstance(error, ValidationError):
            raise
        _fail('INVALID_SCHEMA', 'archive/config', str(error))


def _resolve_refs(packet: Packet) -> None:
    sources = {s['source_id']: s for s in packet.sources}
    cached: dict[str, Any] = {}
    def resolve(reference):
        try:
            sid, fragment = reference.split('#', 1)
            source = sources[sid]
            path = _safe(packet.root, source['local_path'])
            if fragment.startswith('line='):
                lines = path.read_bytes().split(b'\n')
                if lines[-1] == b'':
                    lines.pop()
                number = int(fragment[5:])
                if number < 1 or number > len(lines) or not lines[number - 1].strip():
                    raise ValueError('line does not exist')
                return
            if sid not in cached:
                cached[sid] = load_json(path)
            value, rest = cached[sid], fragment
            if not rest.startswith('$'):
                raise ValueError('invalid JSON object fragment')
            rest = rest[1:]
            while rest:
                match = re.match(r'\.([A-Za-z_][A-Za-z_0-9-]*)|\[([0-9]+)\]', rest)
                if not match:
                    raise ValueError('unsupported object path')
                value = value[match.group(1)] if match.group(1) is not None else value[int(match.group(2))]
                rest = rest[match.end():]
        except (ValueError, KeyError, IndexError, TypeError, OSError) as error:
            _fail('INVALID_SOURCE_REF', str(reference), str(error))
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'source_ref' and child is not None:
                    resolve(child)
                elif key == 'source_refs':
                    for reference in child:
                        resolve(reference)
                else:
                    walk(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                walk(child)
    for value in (packet.manifest, packet.protocol, packet.tasks, packet.assignments, packet.outcomes, packet.attempts, packet.diagnostics):
        walk(value)


def _preflight(root: Path) -> None:
    for name in ('packet.json', 'protocol.json', 'sources.json', 'ledger.sqlite', 'identifier-map.json', *(n + '.jsonl' for n in _TABLES)):
        _safe(root, name)


def _hashes(root: Path) -> dict[str, str]:
    names = {'sources.json', 'protocol.json', 'identifier-map.json', *(n + '.jsonl' for n in _TABLES)}
    hashes = {}
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        _safe(root, name)
        if path.is_file() and (name.startswith('raw/') or name in names):
            hashes[name] = _sha(path.read_bytes())
    return hashes


def freeze(input_dir: Path, *, adapter: str, config_path: Path, protocol_path: Path, sources_path: Path, out: Path) -> Path:
    """Validate and publish a complete sibling-staged run, refusing existing paths."""
    input_dir, out = Path(input_dir).resolve(), Path(out).absolute()
    if out.exists() or out.is_symlink():
        raise FileExistsError(f'refusing existing run: {out}')
    config, protocol, inventory = load_json(config_path), load_json(protocol_path), load_json(sources_path)
    if '_context' in config:
        _fail('INVALID_SCHEMA', 'config', 'runtime context cannot be supplied in a persisted selection config')
    if adapter == 'canonical':
        packet = import_canonical(input_dir, config)
        if packet.protocol != protocol or {'schema_version': 1, 'sources': list(packet.sources)} != inventory:
            _fail('PROTOCOL_MISMATCH', 'canonical', 'explicit protocol/sources differ from contained canonical evidence')
        source_root = input_dir
        raw_paths = {s['source_id']: _safe(source_root, s['local_path']) for s in packet.sources}
    elif adapter == 'needle-scholar':
        source_root = Path(sources_path).resolve().parent
        runtime = {**config, '_context': dict(protocol=protocol, sources=inventory, source_root=source_root)}
        packet = import_needle_scholar(input_dir, runtime)
        raw_paths = {}
        for source in packet.sources:
            sid = source['source_id']
            if sid == config['assignment_evidence']['gold_source_id']:
                raw_paths[sid] = _safe(input_dir, config['gold_path'])
            elif sid == config['assignment_evidence']['summary_source_id']:
                raw_paths[sid] = _safe(input_dir, config['summary_path'])
            elif sid in {config['run_id'] + '-' + arm for arm in config['arms']}:
                raw_paths[sid] = _safe(input_dir, 'scholar/' + sid[len(config['run_id']) + 1:] + '.json')
            else:
                raw_paths[sid] = _safe(source_root, source['local_path'])
    else:
        _fail('UNSUPPORTED_ADAPTER', 'adapter', adapter)
    packet, conversion_bytes = _conversion_map(packet, source_paths=raw_paths)
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + out.name + '.staging-', dir=out.parent))
    reserved = False
    try:
        (staging / 'raw').mkdir()
        sources = []
        for source in packet.sources:
            sid = source['source_id']
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', sid):
                _fail('UNSAFE_SOURCE_PATH', sid, 'source ID cannot be used as a retained filename')
            data = raw_paths[sid].read_bytes()
            if len(data) != source['bytes'] or _sha(data) != source['sha256']:
                _fail('HASH_MISMATCH', sid, 'source bytes differ from acquisition inventory')
            name = 'raw/' + sid + ''.join(raw_paths[sid].suffixes)
            if any(s['local_path'] == name for s in sources):
                _fail('DUPLICATE_SOURCE', sid, 'retained raw filename collision')
            (staging / name).write_bytes(data)
            sources.append({**source, 'local_path': name})
        if conversion_bytes is not None:
            (staging / 'identifier-map.json').write_bytes(conversion_bytes)
        manifest = dict(packet.manifest)
        if manifest['origin'] == 'new_run':
            data = _assignment_manifest(packet)
            name = 'raw/assignment-manifest.jsonl'
            (staging / name).write_bytes(data)
            sources.append(_generated('normalization-assignment-manifest', name, data,
                                      sorted({a['source_ref'].split('#')[0] for a in packet.assignments}),
                                      'Retain original pre-dispatch assignment manifest bytes'))
            manifest['extensions'] = {**manifest.get('extensions', {}), 'assignment_manifest_source_id': 'normalization-assignment-manifest'}
        if adapter == 'needle-scholar':
            exclusions = manifest['extensions'].pop('excluded_tasks')
            data = _bytes(dict(original_tasks=manifest['extensions']['raw_task_count'],
                               selected_tasks=len(packet.tasks), excluded_tasks=exclusions))
            (staging / 'raw/exclusions.json').write_bytes(data)
            sources.append(_generated('normalization-exclusions', 'raw/exclusions.json', data,
                                      [config['assignment_evidence']['gold_source_id']], 'Exclude non-arXiv gold without historical conversion evidence'))
            manifest['extensions']['exclusions_source_id'] = 'normalization-exclusions'
        reconciled = [r for r in packet.outcomes if 'MISSING_OUTCOME' in r['limitations']]
        if reconciled:
            evidence = [dict(assignment_id=r['assignment_id'], inference='Intended assignment has no terminal record; dispatch is unknown',
                             source_ref=next(a['source_ref'] for a in packet.assignments if a['assignment_id'] == r['assignment_id'])) for r in reconciled]
            data = _bytes(dict(rows=evidence))
            (staging / 'raw/reconciliation.json').write_bytes(data)
            parents = sorted({r['source_ref'].split('#')[0] for r in evidence})
            sources.append(_generated('normalization-reconciliation', 'raw/reconciliation.json', data, parents, 'Synthesize explicit unknown outcomes from intended assignments'))
            refs = {r['assignment_id']: f'normalization-reconciliation#$.rows[{n}]' for n, r in enumerate(evidence)}
            packet = replace(packet, outcomes=tuple({**r, 'source_ref': refs[r['assignment_id']]} if r['assignment_id'] in refs else r for r in packet.outcomes))
        snapshot = dict(schema_version=1, adapter=adapter, config=config, authoritative_manifest=_authoritative(manifest))
        data = _bytes(snapshot)
        (staging / _BINDING).write_bytes(data)
        sources.append(_generated('normalization-input', _BINDING, data, sorted(s['source_id'] for s in sources),
                                  'Bind logical adapter config and authoritative manifest facts to normalized run identity'))
        (staging / 'sources.json').write_bytes(_bytes(dict(schema_version=1, sources=sorted(sources, key=lambda s: s['source_id']))))
        # Preserve the explicitly frozen protocol bytes; formatting is part of protocol identity.
        (staging / 'protocol.json').write_bytes(Path(protocol_path).read_bytes())
        for name in _TABLES:
            rows = sorted(getattr(packet, name), key=lambda r: r[_KEYS[name]])
            (staging / (name + '.jsonl')).write_bytes(b''.join(_bytes(r) for r in rows))
        manifest['hashes'] = _hashes(staging)
        manifest['protocol_sha256'] = manifest['hashes']['protocol.json']
        manifest['content_id'] = _sha(_bytes(manifest['hashes']))
        (staging / 'packet.json').write_bytes(_bytes(manifest))
        validated = validate_packet(staging)
        validated, _ = _conversion_map(validated, frozen=True)
        _resolve_refs(validated)
        create_ledger(validated, staging / 'ledger.sqlite')
        manifest['normalized_table_digest'] = normalized_digest(staging / 'ledger.sqlite')
        (staging / 'packet.json').write_bytes(_bytes(manifest))
        verify_run(staging)
        # An exclusive empty reservation prevents rename from replacing a racing
        # publisher's empty destination. No run files appear until atomic rename.
        out.mkdir()
        reserved = True
        staging.rename(out)
        reserved = False
        return out
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        if reserved:
            try:
                out.rmdir()
            except OSError:
                pass
        raise


def verify_run(run: Path) -> Packet:
    """Read-only verification of source bytes, manifest binding and SQL identity."""
    run = Path(run).resolve()
    _preflight(run)
    manifest = load_json(run / 'packet.json')
    snapshot = load_json(_safe(run, _BINDING))
    if snapshot.get('authoritative_manifest') != _authoritative(manifest):
        _fail('MANIFEST_INTEGRITY_MISMATCH', 'packet.json', 'authoritative manifest differs from hashed normalization input')
    packet = validate_packet(run)
    _check_counts(packet)
    _check_assignment_manifest(packet)
    packet, _ = _conversion_map(packet, frozen=True)
    hashes = _hashes(run)
    if hashes != manifest['hashes'] or _sha(_bytes(hashes)) != manifest.get('content_id'):
        _fail('CONTENT_ID_MISMATCH', 'packet.json', 'content map or content identity differs')
    _resolve_refs(packet)
    digest = manifest.get('normalized_table_digest')
    if not isinstance(digest, str):
        _fail('LEDGER_INTEGRITY_MISMATCH', 'packet.json', 'missing normalized ledger digest')
    verify_ledger(run / 'ledger.sqlite', digest)
    records = read_records(run / 'ledger.sqlite')
    for name in ('sources', *_TABLES, 'diagnostics'):
        left = sorted((_bytes(r) for r in getattr(packet, name)))
        right = sorted((_bytes(r) for r in records[name]))
        if left != right:
            _fail('LEDGER_INTEGRITY_MISMATCH', name, 'ledger evidence differs from canonical records')
    return packet
