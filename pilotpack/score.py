"""Deterministic logical delivery scoring over verified, immutable evidence."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import subprocess
import sys

from .ingest import verify_run
from .schema import JsonObject, ValidationError, load_json


def _diagnostic(code, scope, message, refs=(), severity='block'):
    return dict(code=code, severity=severity, scope=scope,
                source_refs=sorted(set(r for r in refs if r)), message=message)


def _map_values(identifier_map):
    if identifier_map is None:
        return {}
    values = identifier_map.get('pmc_to_pmid')
    if (set(identifier_map) != {'pmc_to_pmid'} or not isinstance(values, dict)
            or any(not isinstance(k, str) or not re.fullmatch(r'[0-9]+', k)
                   or (v is not None and (not isinstance(v, str) or not re.fullmatch(r'[0-9]+', v)))
                   for k, v in values.items())):
        raise ValidationError([_diagnostic('INVALID_IDENTIFIER_MAP', 'conversion_map',
                               'Expected pmc_to_pmid mapping of bare digit strings to digit strings or null.')])
    return values


def _extract(result, snippet_chars):
    # Rules are pinned to NEEDLE 73c7f810's scholar/ids.py and search/base.py.
    url = result.get('url') or ''
    snippet = result.get('snippet') or ''
    supported_snippet = '' if snippet_chars is None else snippet[:snippet_chars] if snippet_chars > 0 else snippet
    text = ' '.join(p for p in (result.get('title'), supported_snippet) if p)
    identity = r'(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5})'
    arxiv = {m.group(1).lower() for pattern in (
        rf'arxiv\.org/(?:abs|pdf|html)/({identity})(?:v\d+)?',
        rf'arxiv[:\s]+({identity})(?:v\d+)?', rf'10\.48550/arxiv\.({identity})')
        for value in (url, text) for m in re.finditer(pattern, value, re.I)}
    doi = {re.sub(r'/(full|pdf|epdf|html|meta|abstract|citations?)$', '', m.group(1).rstrip('.)').rstrip(','), flags=re.I).lower()
           for value in (url, text) for m in re.finditer(r'(10\.\d{4,9}/[-._;()/:a-z0-9]+)', value, re.I)}
    # The first two native PMID URL patterns are deliberately case sensitive.
    pmid = {m.group(1) for pattern, flags in (
        (r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', 0), (r'ncbi\.nlm\.nih\.gov/pubmed/(\d+)', 0),
        (r'europepmc\.org/(?:article|abstract)/MED/(\d+)', re.I)) for m in re.finditer(pattern, url, flags)}
    pmid.update(re.findall(r'\bPMID[:\s]*(\d{6,9})\b', text, re.I))
    pmc = {m.group(1) for pattern in (
        r'(?:pmc\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov/pmc)/articles?/PMC(\d+)',
        r'europepmc\.org/article/PMC/PMC(\d+)') for m in re.finditer(pattern, url, re.I)}
    return dict(arxiv=arxiv, doi=doi, pmid=pmid, pmcid=pmc)


def _matching(gold_ids, results, *, k, snippet_chars, identifier_map):
    mapping = _map_values(identifier_map)
    missing_before = False
    for rank, result in enumerate(results[:k], 1):
        found = _extract(result, snippet_chars)
        missing_here = snippet_chars is None and bool(result.get('snippet'))
        if gold_ids.get('pmid') and found['pmcid'] and not found['pmid']:
            missing_here |= any(mapping.get(p) is None for p in found['pmcid'])
            found['pmid'].update(mapping[p] for p in found['pmcid'] if mapping.get(p) is not None)
        if any(set(ids) & found.get(namespace, set()) for namespace, ids in gold_ids.items()):
            return rank, not missing_before, missing_before or missing_here
        missing_before |= missing_here
    return None, not missing_before, missing_before


def match_rank(gold_ids: dict[str, list[str]], results: list[JsonObject], *, k: int,
               snippet_chars: int, identifier_map: JsonObject | None) -> int | None:
    """First confirmed literal match; cached returned_ids/ranks never supply evidence.

    A null result alone does not establish a miss: score_run also checks map coverage.
    Zero snippet_chars is uncapped. An unknown cap leaves URL/title matches usable.
    """
    return _matching(gold_ids, results, k=k, snippet_chars=snippet_chars,
                     identifier_map=identifier_map)[0]


def select_delivery(assignment: JsonObject, outcome: JsonObject,
                    attempts: tuple[JsonObject, ...], protocol: JsonObject) -> JsonObject:
    """Select the first completed response, provisionally M until gold matching.

    Selection uses attempt_index, never a cached rank or later response quality.
    Archive logical observations remain usable descriptively with retry limits.
    """
    aid = assignment['assignment_id']
    rows = sorted((a for a in attempts if a['assignment_id'] == aid), key=lambda a: a['attempt_index'])
    refs = [assignment.get('source_ref'), outcome.get('source_ref')] + [a.get('source_ref') for a in rows]
    delivery = dict(selected_attempt_id=outcome.get('selected_attempt_id'), results=outcome.get('results'),
                    classification='U', unknown_reason=None, source_refs=sorted(set(r for r in refs if r)), diagnostics=[])

    def unknown(code, message, reason='unresolved_dispatch'):
        delivery.update(classification='U', unknown_reason=reason)
        delivery['diagnostics'].append(_diagnostic(code, 'assignment:' + aid, message, refs))
        return delivery

    kind, terminal = outcome.get('observation_kind'), outcome.get('terminal_status')
    if kind == 'not_dispatched' or terminal == 'runner_failure':
        delivery['unknown_reason'] = 'runner_not_dispatched'
        if rows:
            return unknown('RETRY_SELECTION_MISMATCH', 'Non-dispatch contradicts physical request evidence.', 'runner_not_dispatched')
        return delivery
    if kind == 'unobserved':
        delivery['unknown_reason'] = 'missing_record' if 'MISSING_OUTCOME' in outcome.get('limitations', []) else 'unresolved_dispatch'
        return delivery
    if kind == 'attempt_backed':
        if not rows:
            return unknown('UNKNOWN_ATTEMPT_HISTORY', 'Attempt-backed selection lacks physical evidence.')
        first = next((a for a in rows if a['status'] == 'completed'), None)
        before = rows if first is None else [a for a in rows if a['attempt_index'] < first['attempt_index']]
        prefix = before + ([first] if first is not None else [])
        if [a['attempt_index'] for a in prefix] != list(range(1, len(prefix) + 1)):
            return unknown('UNKNOWN_ATTEMPT_HISTORY', 'Missing earlier attempt indices prevent deterministic selection.')
        if any(a['status'] == 'unresolved' for a in before):
            return unknown('INTERRUPTED_RETRY', 'An unresolved attempt prevents deterministic logical selection.')
        if first is not None:
            delivery.update(selected_attempt_id=first['attempt_id'], results=first['results'])
            if (outcome.get('selected_attempt_id') != first['attempt_id'] or terminal != 'completed'
                    or outcome.get('results') != first['results']):
                return unknown('RETRY_SELECTION_MISMATCH', 'Outcome contradicts the first completed response.')
        elif terminal != 'provider_error' or any(a['status'] != 'provider_error' for a in rows):
            return unknown('INTERRUPTED_RETRY', 'No completed response or evidenced terminal provider failure.')
        elif outcome.get('selected_attempt_id') not in (None, rows[-1]['attempt_id']):
            return unknown('RETRY_SELECTION_MISMATCH', 'Terminal failure selects an inconsistent attempt.')
        if protocol.get('retry_selection') != 'first_completed':
            # Existing canonical/archive records may prove a selection but not the policy.
            delivery['diagnostics'].append(_diagnostic('UNKNOWN_ACTUAL_RETRY_POLICY', 'assignment:' + aid,
                                                      'Physical selection is recomputed; declared retry policy is not first_completed.', refs,
                                                      severity='limitation'))
    elif kind == 'archive_logical' and rows:
        return unknown('RETRY_SELECTION_MISMATCH', 'Archive logical observation contradicts supplied physical history.')
    if terminal == 'provider_error':
        delivery['classification'] = 'F'
    elif terminal == 'completed' and delivery['results'] is not None:
        if {'MISSING_MATCH_EVIDENCE', 'UNKNOWN_JUDGMENT'} & set(outcome.get('limitations', [])):
            delivery['unknown_reason'] = 'completed_unknown'
        else:
            delivery['classification'] = 'M'
    else:
        delivery['unknown_reason'] = 'completed_unknown' if terminal == 'completed' else 'unresolved_dispatch'
    return delivery


def _baselines(packet):
    sources = {s['source_id']: s for s in packet.sources}
    result = {}
    for name, sid in packet.manifest.get('extensions', {}).get('baseline_source_ids', {}).items():
        result[name] = load_json(packet.root / sources[sid]['local_path'])
    return result


def score_run(run: Path) -> JsonObject:
    packet = verify_run(run)
    manifest = packet.manifest
    baselines = _baselines(packet)
    identifier_map = load_json(run / 'identifier-map.json') if (run / 'identifier-map.json').exists() else None
    _map_values(identifier_map)
    diagnostics = list(packet.diagnostics)
    tasks = {t['task_id']: t for t in packet.tasks}
    outcomes = {o['assignment_id']: o for o in packet.outcomes}
    attempts = {}
    for attempt in packet.attempts:
        attempts.setdefault(attempt['assignment_id'], []).append(attempt)
    arms = {}
    cases = []
    profile = manifest.get('extensions', {}).get('native_profile')
    for arm_id in sorted(set(manifest['intended_count']) | {a['arm_id'] for a in packet.assignments}):
        arms[arm_id] = dict(N=0, H=0, M=0, F=0, U=0, unknown_reasons=dict(
            completed_unknown=0, missing_record=0, unresolved_dispatch=0, runner_not_dispatched=0))
    for assignment in sorted(packet.assignments, key=lambda a: a['assignment_id']):
        aid, arm_id = assignment['assignment_id'], assignment['arm_id']
        task = tasks[assignment['task_id']]
        outcome = outcomes[aid]
        rows = tuple(sorted(attempts.get(aid, []), key=lambda a: a['attempt_index']))
        delivery = select_delivery(assignment, outcome, rows, packet.protocol)
        map_source = manifest.get('extensions', {}).get('conversion_map', {}).get('source_id')
        if identifier_map is not None and map_source and task['gold_ids'].get('pmid'):
            delivery['source_refs'] = sorted(set(delivery['source_refs'] + [map_source + '#$']))
        rank, confirmed_rank, exact = None, None, True
        settings = manifest['actual_settings'][arm_id]
        if delivery['classification'] == 'M' and delivery['results']:
            if not task['gold_ids']:
                delivery.update(classification='U', unknown_reason='completed_unknown')
                delivery['diagnostics'].append(_diagnostic('MISSING_MATCH_EVIDENCE', 'assignment:' + aid,
                                                          'Gold evidence is unavailable.', delivery['source_refs']))
            else:
                confirmed_rank, exact, missing = _matching(task['gold_ids'], delivery['results'], k=settings['k'],
                                                         snippet_chars=settings['snippet_chars'], identifier_map=identifier_map)
                rank = confirmed_rank if exact else None
                if confirmed_rank is not None:
                    delivery['classification'] = 'H'
                elif missing:
                    delivery.update(classification='U', unknown_reason='completed_unknown')
                if missing:
                    delivery['diagnostics'].append(_diagnostic('MISSING_MATCH_EVIDENCE', 'assignment:' + aid,
                                                              'Snippet budget or frozen PMC-to-PMID coverage is unavailable; affected match/rank is unsupported.', delivery['source_refs'],
                                                              severity='limitation' if confirmed_rank is not None else 'block'))
        reported_rank_present = (outcome.get('reported_hit_rank') is not None
                                 or profile == 'needle-scholar-all-rows-v1' and outcome['observation_kind'] == 'archive_logical')
        if (reported_rank_present and delivery['classification'] in ('H', 'M')
                and exact and outcome['reported_hit_rank'] != rank):
            delivery['diagnostics'].append(_diagnostic('NATIVE_RANK_MISMATCH', 'assignment:' + aid,
                                                      'Reported native rank differs from literal recomputation.', delivery['source_refs']))
        arm = arms[arm_id]
        arm['N'] += 1
        arm[delivery['classification']] += 1
        if delivery['unknown_reason']:
            arm['unknown_reasons'][delivery['unknown_reason']] += 1
        case = dict(assignment_id=aid, task_id=task['task_id'], arm_id=arm_id,
                    source_group_id=task['source_group_id'], cohort_id=task['cohort_id'], bucket=task['bucket'],
                    query_text=task['query_text'], gold_ids=task['gold_ids'], partition=delivery['classification'],
                    classification=delivery['classification'], first_hit_rank=rank, confirmed_hit_rank=confirmed_rank,
                    rank_supported=exact, reported_hit_rank=outcome.get('reported_hit_rank'),
                    observation_kind=outcome['observation_kind'], terminal_status=outcome['terminal_status'],
                    selected_attempt_id=delivery['selected_attempt_id'], results=delivery['results'],
                    result_count=len(delivery['results']) if delivery['results'] is not None else None,
                    attempts=list(rows), unknown_reason=delivery['unknown_reason'],
                    source_refs=sorted(set(delivery['source_refs'] + [task['source_ref']])),
                    diagnostics=delivery['diagnostics'], limitations=outcome.get('limitations', []))
        cases.append(case)
        diagnostics.extend(delivery['diagnostics'])
    native = {}
    for arm_id, arm in arms.items():
        cohort = [c for c in cases if c['arm_id'] == arm_id]
        n = arm['N'] if manifest['assignment_basis'] != 'unreconstructable' else None
        arm['N'] = n
        arm['delivered_hit_at_k'] = arm['H'] / n if n else None
        arm['missingness_range'] = [arm['H'] / n, (arm['H'] + arm['U']) / n] if n else None
        if n is None or n == 0:
            diagnostics.append(_diagnostic('UNKNOWN_ASSIGNMENT_BASIS' if n is None else 'EMPTY_COHORT',
                                          'arm:' + arm_id, 'Intended-denominator metrics are undefined.', severity='limitation'))
        observed = sum(len(c['attempts']) for c in cohort)
        lower_bound = sum(max(len(c['attempts']), max((a['attempt_index'] for a in c['attempts']), default=0),
                             int(c['terminal_status'] in ('completed', 'provider_error')
                                                     and c['observation_kind'] != 'not_dispatched')) for c in cohort)
        contiguous = all([a['attempt_index'] for a in c['attempts']] == list(range(1, len(c['attempts']) + 1)) for c in cohort)
        complete = manifest['attempt_history'][arm_id] == 'complete' and lower_bound == observed and contiguous
        if manifest['attempt_history'][arm_id] == 'complete' and not complete:
            diagnostics.append(_diagnostic('UNKNOWN_ATTEMPT_HISTORY', 'arm:' + arm_id,
                                          'Claimed complete physical history has missing dispatches or attempt indices.',
                                          [ref for c in cohort for ref in c['source_refs']], severity='limitation'))
        arm['attempts'] = dict(observed_attempt_rows=observed, physical_attempt_count_lower_bound=lower_bound,
                               physical_attempt_count_exact=observed if complete else None,
                               history=manifest['attempt_history'][arm_id])
        arm['cost'] = dict(total=None, support_status='unassessed')
        arm['latency'] = dict(paired=None, support_status='unassessed')
        denominator_supported = (profile == 'needle-scholar-all-rows-v1' and n is not None
                                 and all(c['terminal_status'] in ('completed', 'provider_error')
                                         and c['observation_kind'] not in ('unobserved', 'not_dispatched') for c in cohort))
        supported = denominator_supported and not arm['U']
        rank_supported = supported and all(c['rank_supported'] for c in cohort)
        replay = baselines.get('native', {}).get('engines', {}).get(arm_id)
        reported = replay.get('full_archive_cached_summary') if replay else None
        native[arm_id] = dict(support_status=('supported' if rank_supported else 'partial' if denominator_supported else 'unsupported'),
                             profile=profile, num_scored=n if denominator_supported else None,
                             recall_at_k=(arm['H'] / n if n else 0.0) if supported else None,
                             mrr_at_k=(sum(1 / c['first_hit_rank'] for c in cohort if c['first_hit_rank']) / n if n else 0.0) if rank_supported else None,
                             search_errors=sum(c['terminal_status'] == 'provider_error' for c in cohort) if denominator_supported else None, reported=reported,
                             reported_support_status='reported_only' if reported is not None else 'unavailable',
                             frozen_replay={m: replay[m] for m in ('num_scored','recall_at_k','mrr_at_k','search_errors')} if replay else None)
    if 'native' in baselines:
        native['ceilings'] = {k: baselines['native'][k] for k in ('selected_engine_ultimate', 'original_all_engine_ultimate')
                              if k in baselines['native']}
    evaluation = dict(schema_version=1, run_id=manifest['run_id'], content_id=manifest['content_id'],
                      protocol_hash=manifest['protocol_sha256'], arms=arms, cases=cases, native_metrics=native,
                      reference_checks=[], pairs=[], decisions={}, diagnostics=diagnostics,
                      limitations=sorted(set(manifest.get('limitations', []))))
    reference_diagnostics = check_reference(run, evaluation)
    evaluation['diagnostics'].extend(reference_diagnostics)
    links = manifest.get('extensions', {}).get('baseline_source_ids', {})
    for name, key in (('independent_oracle', None), ('frozen_oracle', 'oracle'),
                      ('native_replay', 'native'), ('frozen_check', 'check')):
        available = key is None or key in baselines
        # Any failed reconciliation blocks reference acceptance as a whole.
        evaluation['reference_checks'].append(dict(
            reference=name, status=('mismatch' if reference_diagnostics else 'passed') if available else 'unavailable',
            source_refs=[links[key] + '#$'] if key in links else [],
            task_count=len(packet.tasks), source_group_count=len({t['source_group_id'] for t in packet.tasks}),
            assignment_count=len(packet.assignments), observed_attempt_rows=len(packet.attempts),
            absolute_tolerance=1e-9, reason=None if available else 'No frozen baseline linked in the verified packet.',
            diagnostics=reference_diagnostics if available else []))
    return evaluation


def check_reference(run: Path, evaluation: JsonObject) -> list[JsonObject]:
    """Compare a separate independent oracle and retained frozen baselines.

    Counts/identities/ranks compare exactly. Only numeric metrics allow 1e-9.
    No raw data or evaluation objects are changed.
    """
    packet = verify_run(run)
    refs = [s['source_id'] + '#$' for s in packet.sources]
    diagnostics = []

    def compare(actual, expected, scope, numeric=False):
        equal = actual == expected
        if isinstance(expected, int) and not isinstance(expected, bool) and not numeric:
            equal = type(actual) is int and actual == expected
        if numeric and isinstance(expected, list):
            if not isinstance(actual, list) or len(actual) != len(expected):
                equal = False
            else:
                equal = all(isinstance(a, (int, float)) and not isinstance(a, bool) and math.isfinite(a)
                            and abs(a - e) <= 1e-9 for a, e in zip(actual, expected))
        elif numeric and actual is not None and expected is not None:
            equal = (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                     and math.isfinite(actual) and abs(actual - expected) <= 1e-9)
        if not equal:
            diagnostics.append(_diagnostic('REFERENCE_MISMATCH', scope,
                                           f'Reference expected {expected!r}; evaluation has {actual!r}.', refs))

    proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'reference/oracle.py'),
                           '--run', str(Path(run).resolve())], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return [_diagnostic('REFERENCE_MISMATCH', 'run', 'Independent oracle failed: ' + proc.stderr.strip(), refs)]
    oracle = json.loads(proc.stdout)
    compare(evaluation.get('run_id'), oracle['run_id'], 'run:run_id')
    compare(evaluation.get('content_id'), packet.manifest['content_id'], 'run:content_id')
    compare(evaluation.get('protocol_hash'), packet.manifest['protocol_sha256'], 'run:protocol_hash')
    compare(len(packet.tasks), oracle['task_count'], 'run:task_count')
    compare(set(evaluation['arms']), set(oracle['arms']), 'run:arm_ids')
    actual_cases = {c['assignment_id']: c for c in evaluation['cases']}
    compare(len(evaluation['cases']), len(actual_cases), 'run:unique_case_ids')
    compare(set(actual_cases), set(oracle['assignments']), 'run:assignment_ids')
    task_records = {t['task_id']: t for t in packet.tasks}
    for assignment in packet.assignments:
        row = actual_cases.get(assignment['assignment_id'], {})
        task = task_records[assignment['task_id']]
        for field, expected in dict(task_id=assignment['task_id'], arm_id=assignment['arm_id'],
                                    source_group_id=task['source_group_id'], cohort_id=task['cohort_id']).items():
            compare(row.get(field), expected, 'assignment:' + assignment['assignment_id'] + ':' + field)
    for aid, expected in oracle['assignments'].items():
        row = actual_cases.get(aid, {})
        for field in ('partition', 'first_hit_rank', 'result_count'):
            compare(row.get(field), expected[field], 'assignment:' + aid + ':' + field)
    for arm_id, expected in oracle['arms'].items():
        actual = evaluation['arms'].get(arm_id, {})
        for field in ('N', 'H', 'M', 'F', 'U', 'missingness_range'):
            compare(actual.get(field), expected[field], 'arm:' + arm_id + ':' + field, field == 'missingness_range')
        compare(actual.get('delivered_hit_at_k'), expected['delivered_hit_at_k'], 'arm:' + arm_id + ':delivered_hit_at_k', True)
        compare(actual.get('unknown_reasons'), expected['unknown_subcounts'], 'arm:' + arm_id + ':unknown_reasons')
        for field in ('observed_attempt_rows', 'physical_attempt_count_lower_bound', 'physical_attempt_count_exact'):
            compare(actual.get('attempts', {}).get(field), expected[field], 'arm:' + arm_id + ':' + field)
        for field in ('support_status', 'num_scored', 'recall_at_k', 'mrr_at_k', 'search_errors'):
            compare(evaluation['native_metrics'].get(arm_id, {}).get(field), expected['native_metrics'][field],
                    'arm:' + arm_id + ':native:' + field, field in ('recall_at_k','mrr_at_k'))
    baselines = _baselines(packet)
    frozen = baselines.get('oracle')
    if frozen:
        for field in ('task_count', 'source_group_count'):
            compare(oracle[field], frozen[field], 'run:frozen_oracle:' + field)
        compare(set(actual_cases), set(frozen['assignments']), 'run:frozen_oracle:assignment_ids')
        for aid, expected in frozen['assignments'].items():
            for field in ('partition','first_hit_rank','result_count'):
                compare(actual_cases.get(aid, {}).get(field), expected[field], 'assignment:' + aid + ':frozen_oracle:' + field)
        for arm_id, expected in frozen['arms'].items():
            for field in ('N','H','M','F','U','delivered_hit_at_k','missingness_range'):
                compare(evaluation['arms'].get(arm_id, {}).get(field), expected[field],
                        'arm:' + arm_id + ':frozen_oracle:' + field, field in ('delivered_hit_at_k', 'missingness_range'))
            for field in ('num_scored','recall_at_k','mrr_at_k','search_errors'):
                compare(evaluation['native_metrics'].get(arm_id, {}).get(field), expected['native_metrics'][field],
                        'arm:' + arm_id + ':frozen_oracle:native:' + field, field in ('recall_at_k','mrr_at_k'))
    native = baselines.get('native')
    if native:
        compare(native.get('discrepancies'), [], 'run:native_replay:discrepancies')
        compare(len(packet.tasks), native['num_queries'], 'run:native_replay:task_count')
        # Native replay preserves original gold source row order; canonical rows sort by identity.
        ordered = sorted(packet.tasks, key=lambda t: int(t['source_ref'].rsplit('#line=', 1)[1]))
        for arm_id, expected in native['engines'].items():
            ranks = [actual_cases.get(arm_id + ':' + t['task_id'], {}).get('first_hit_rank') for t in ordered]
            compare(ranks, expected['per_query_hit_ranks'], 'arm:' + arm_id + ':native_replay:ranks')
            for field in ('num_scored','recall_at_k','mrr_at_k','search_errors'):
                compare(evaluation['native_metrics'].get(arm_id, {}).get(field), expected[field],
                        'arm:' + arm_id + ':native_replay:' + field, field in ('recall_at_k','mrr_at_k'))
    if 'check' in baselines:
        witness = baselines['check']
        compare(witness['task_count'], len(packet.tasks), 'run:frozen_check:task_count')
        compare(witness['group_count'], len({t['source_group_id'] for t in packet.tasks}), 'run:frozen_check:group_count')
        compare(witness['rank_comparisons'], len(packet.assignments), 'run:frozen_check:rank_comparisons')
        for field in ('native_archive_discrepancies', 'oracle_native_discrepancies'):
            compare(witness[field], [], 'run:frozen_check:' + field)
    return diagnostics
