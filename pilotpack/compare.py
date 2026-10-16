"""Scoped retrieval eligibility, grouped uncertainty and observed request accounting.

Inputs are already verified and independently reconciled by score_run. This layer
annotates a copy; it neither selects cohorts nor edits frozen source evidence.
"""
from __future__ import annotations

import copy
from datetime import datetime
from decimal import Decimal, localcontext
import math
import platform
import random

from .schema import JsonObject, Packet, ValidationError, load_json


_SETTINGS = ('provider', 'mode', 'endpoint', 'query_parameters', 'requested_num_results',
             'k', 'snippet_chars', 'retry_policy', 'timeout_s', 'concurrency', 'run_window',
             'matching_profile')
_COMMON = ('k', 'requested_num_results', 'snippet_chars', 'matching_profile', 'run_window')
_COHORT = ('task_id', 'source_group_id', 'cohort_id', 'query_text', 'gold_ids', 'bucket')
_ESTIMAND = 'query-weighted delivered hit-rate difference (arm_a minus arm_b)'
_METHOD = 'source-group bootstrap; uniform groups with replacement; nearest-rank 2.5/97.5 percentiles'


def _diagnostic(code, scope, message, refs=(), severity='block'):
    return dict(code=code, severity=severity, scope=scope, source_refs=sorted(set(refs)), message=message)


def _bootstrap_unavailable(reason, *, n_groups=0, n_queries=0):
    return dict(interval=None, replicates=2000, seed=0, n_groups=n_groups, n_queries=n_queries,
                estimand=_ESTIMAND, method=_METHOD, python_version=platform.python_version(),
                unavailable_reason=reason, point_estimate=None,
                qualifications=['SMALL_GROUP_COUNT'] if n_groups < 50 else [])


def grouped_bootstrap(rows: list[JsonObject], *, replicates: int, seed: int) -> JsonObject:
    """Keep both arms and all variants together, recomputing query-weighted rates."""
    if type(replicates) is not int or replicates != 2000 or type(seed) is not int or seed != 0:
        raise ValueError('Version 1 requires exactly 2000 replicates and seed 0.')
    groups = {}
    seen = set()
    for row in rows:
        task, group = row.get('task_id'), row.get('source_group_id')
        if not isinstance(task, str) or not task or task in seen:
            return _bootstrap_unavailable('Task IDs must be present and unique.', n_queries=len(rows))
        if not isinstance(group, str) or not group:
            return _bootstrap_unavailable('Source group IDs are unavailable.', n_queries=len(rows))
        if any(type(row.get(k)) is not int or row[k] not in (0, 1) for k in ('a_hit', 'b_hit')):
            return _bootstrap_unavailable('Complete binary paired outcomes are required.', n_queries=len(rows))
        seen.add(task)
        delta, n = groups.get(group, (0, 0))
        groups[group] = (delta + row['a_hit'] - row['b_hit'], n + 1)
    result = _bootstrap_unavailable('Fewer than two source groups.', n_groups=len(groups), n_queries=len(rows))
    if len(groups) < 2:
        return result
    ordered = [groups[g] for g in sorted(groups)]
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        selected = [ordered[rng.randrange(len(ordered))] for _ in ordered]
        samples.append(sum(delta for delta, _ in selected) / sum(n for _, n in selected))
    samples.sort()
    result.update(interval=[samples[max(0, min(replicates - 1, math.ceil(p * replicates) - 1))]
                            for p in (.025, .975)], unavailable_reason=None,
                  point_estimate=sum(d for d, _ in ordered) / len(rows))
    return result


def observed_cost(attempts: tuple[JsonObject, ...], *, history_complete: bool) -> JsonObject:
    """Sum only evidenced observed request amounts, using exact decimal arithmetic.

    Provenance fragments are resolved and witnessed during packet validation.
    A missing witness/reference here cannot establish even a zero observed cost.
    """
    values = {}
    counts = dict(attempt_rows=len(attempts), observed=0, estimated=0, missing=0, unsupported=0)
    refs = []
    for row in attempts:
        cost = row.get('cost') or {}
        kind = cost.get('kind')
        if (kind == 'observed' and cost.get('scope') == 'attempt' and cost.get('source_ref')
                and cost.get('amount') is not None and cost.get('currency')):
            amount = Decimal(cost['amount'])
            if amount.is_finite() and amount >= 0:
                values.setdefault(cost['currency'], []).append(amount)
                counts['observed'] += 1
                refs.append(cost['source_ref'])
                continue
        counts[kind if kind in ('estimated', 'missing') else 'unsupported'] += 1
    subtotals = {}
    for currency, amounts in sorted(values.items()):
        # Decimal's default 28-digit context must not round long fixed-point receipts.
        precision = max(max(a.adjusted() + 1, 1) for a in amounts)
        precision += max(max(-a.as_tuple().exponent, 0) for a in amounts) + len(str(len(amounts))) + 2
        with localcontext() as context:
            context.prec = precision
            subtotals[currency] = format(sum(amounts, Decimal(0)), 'f')
    reasons = []
    if not history_complete:
        reasons.append('Physical attempt history is incomplete.')
    if not attempts:
        reasons.append('No observed request-cost rows; zero cost is not established.')
    if counts['observed'] != len(attempts):
        reasons.append('Some attempt rows lack observed request-cost evidence of consistent scope.')
    if len(subtotals) > 1:
        reasons.append('Observed request costs use mixed currencies.')
    currency = next(iter(subtotals)) if len(subtotals) == 1 else None
    subtotal = subtotals[currency] if currency else None
    total = subtotal if not reasons else None
    return dict(total=total, currency=currency, known_subtotal=subtotal, known_subtotals=subtotals,
                coverage=counts, history_complete=history_complete, scope='attempt',
                support_status='supported' if total is not None else 'unavailable',
                unavailable_reason=' '.join(reasons) or None, source_refs=sorted(set(refs)))


def _scope_applies(diagnostic, arm, cases):
    scope = diagnostic['scope']
    if scope == 'conversion_map' and diagnostic['code'] == 'MISSING_MATCH_EVIDENCE':
        # Scoring has already emitted narrower diagnostics for affected judgments.
        return False
    if scope.startswith('pair:'):
        return False
    if scope.startswith('metric:'):
        prefix = 'metric:arm:' + arm + ':'
        return scope.startswith(prefix) and scope[len(prefix):] in (
            'delivered_hit_at_k', 'missingness_range', 'accounting')
    if scope.startswith('arm:'):
        return scope == 'arm:' + arm or scope.startswith('arm:' + arm + ':')
    if scope.startswith('assignment:'):
        return any(scope == 'assignment:' + c['assignment_id'] or
                   scope.startswith('assignment:' + c['assignment_id'] + ':') for c in cases)
    # Unscoped schema/hash/reference faults affect the verified packet as a whole.
    return True


def _arm_refs(packet, arm, cases):
    return sorted(set(packet.manifest['actual_settings'][arm].get('source_refs', []) +
                      [r for c in cases for r in c.get('source_refs', [])]))


def _inside_window(window, allowed):
    def stamp(value):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    return (stamp(allowed['started_at']) <= stamp(window['started_at'])
            <= stamp(window['ended_at']) <= stamp(allowed['ended_at']))


def _arm_gates(packet, evaluation, arm, cases):
    refs = _arm_refs(packet, arm, cases)
    scope = 'arm:' + arm
    arm_data = evaluation['arms'][arm]
    gates = []
    for d in evaluation['diagnostics']:
        if d['severity'] in ('block', 'error') and _scope_applies(d, arm, cases):
            gates.append(copy.deepcopy(d))
    n = arm_data['N']
    if (packet.manifest['assignment_basis'] == 'unreconstructable'
            or type(n) is not int or n <= 0 or n != len(cases)
            or n != packet.manifest['intended_count'].get(arm)
            or any(type(arm_data.get(k)) is not int or arm_data[k] < 0 for k in 'HMFU')
            or n != sum(arm_data[k] for k in 'HMFU')
            or any(arm_data[k] != sum(c['partition'] == k for c in cases) for k in 'HMFU')):
        gates.append(_diagnostic('UNSUPPORTED_ACCOUNTING', scope,
                                 'Intended assignments and the H/M/F/U denominator must reconcile.', refs))
    declared, actual = packet.protocol['arms'][arm], packet.manifest['actual_settings'][arm]
    mismatches = [key for key in _SETTINGS if actual[key] is not None
                  and declared[key] is not None and actual[key] != declared[key]]
    # A known actual value against an unknown declaration is also undeclared treatment.
    mismatches += [key for key in _SETTINGS if actual[key] is not None and declared[key] is None]
    if mismatches:
        gates.append(_diagnostic('ACTUAL_SETTINGS_MISMATCH', scope,
                                 'Actual settings differ from the frozen arm declaration: ' + ', '.join(mismatches), refs))
    checks = evaluation.get('reference_checks', [])
    oracle = [c for c in checks if c['reference'] == 'independent_oracle']
    if not oracle or any(c['status'] != 'passed' for c in oracle):
        gates.append(_diagnostic('REFERENCE_UNAVAILABLE', scope, 'Independent oracle agreement is not established.', refs))
    for check in checks:
        if check['status'] == 'mismatch':
            gates.append(_diagnostic('REFERENCE_MISMATCH', scope,
                                     'A frozen reference check disagrees: ' + check['reference'], check.get('source_refs', [])))
    native = evaluation.get('native_metrics', {}).get(arm, {})
    # Canonical evidence without original native metrics has no native replay obligation.
    native_required = (native.get('reported') is not None or native.get('frozen_replay') is not None
                       or packet.manifest['origin'] == 'archive' and native.get('profile') is not None)
    if native_required:
        replay = [c for c in checks if c['reference'] == 'native_replay']
        if not replay or any(c['status'] != 'passed' for c in replay):
            gates.append(_diagnostic('NATIVE_REPLAY_UNAVAILABLE', scope,
                                     'Original native scoring requires an established frozen replay.', refs))
    return gates


def _latency(packet, cases):
    aids = {c['assignment_id'] for c in cases}
    linked = [dict(attempt_id=a['attempt_id'], assignment_id=a['assignment_id'], latency_ms=a['latency_ms'],
                   source_refs=[a['source_ref']]) for a in packet.attempts
              if a['assignment_id'] in aids and a.get('latency_ms') is not None]
    source_ids = {r.split('#', 1)[0] for c in cases for r in c.get('source_refs', [])}
    marginal = []
    for source in packet.sources:
        if source['source_id'] not in source_ids or source['role'] != 'engine-terminal-results':
            continue
        raw = load_json(packet.root / source['local_path'])
        if isinstance(raw.get('latency'), dict):
            marginal.append(dict(raw['latency'], source_refs=[source['source_id'] + '#$.latency'],
                                 native_eligibility=dict(num_scored=raw.get('num_scored'),
                                                         search_errors=raw.get('search_errors'),
                                                         description='Original archive latency eligibility; not the selected paired cohort.')))
    return dict(paired=None, linked_attempt_observations=linked, marginal=marginal,
                support_status='linked_observations' if linked else 'marginal_only' if marginal else 'unavailable',
                unavailable_reason='Pairing requires task-linked selected-response observations in both arms.')


def _paired_latency(packet, a_cases, b_cases, eligible):
    unavailable = dict(paired=None, n_tasks=0, support_status='unavailable',
                       unavailable_reason='All tasks require selected-response-linked latency in both eligible arms.')
    if not eligible:
        return unavailable
    attempts = {a['attempt_id']: a for a in packet.attempts}
    rows = []
    for task in sorted(a_cases):
        a = attempts.get(a_cases[task].get('selected_attempt_id'))
        b = attempts.get(b_cases[task].get('selected_attempt_id'))
        if (a is None or b is None or a.get('latency_ms') is None or b.get('latency_ms') is None
                or a['assignment_id'] != a_cases[task]['assignment_id']
                or b['assignment_id'] != b_cases[task]['assignment_id']):
            return unavailable
        rows.append(dict(task_id=task, a_attempt_id=a['attempt_id'], b_attempt_id=b['attempt_id'],
                         a_latency_ms=a['latency_ms'], b_latency_ms=b['latency_ms'],
                         difference_ms=a['latency_ms'] - b['latency_ms'],
                         source_refs=sorted(set([a['source_ref'], b['source_ref']]))))
    return dict(paired=rows, n_tasks=len(rows), support_status='supported', unavailable_reason=None,
                estimand='Selected delivered-response latency difference in milliseconds; arm_a minus arm_b.')


def _pair(packet, evaluation, a, b):
    scope = 'pair:' + a + ':' + b
    a_rows = [c for c in evaluation['cases'] if c['arm_id'] == a]
    b_rows = [c for c in evaluation['cases'] if c['arm_id'] == b]
    refs = _arm_refs(packet, a, a_rows) + _arm_refs(packet, b, b_rows)
    gates = copy.deepcopy(evaluation['arms'][a]['gates'] + evaluation['arms'][b]['gates'])
    for code in packet.protocol.get('comparison_blockers', []):
        gates.append(_diagnostic(code, scope, 'Frozen protocol declares this evidence-policy comparison blocker.', refs))
    for diagnostic in evaluation['diagnostics']:
        if diagnostic['scope'] in (scope, 'pair:' + b + ':' + a,
                'metric:arm:' + a + ':comparison_conditions', 'metric:arm:' + b + ':comparison_conditions'):
            gates.append(copy.deepcopy(diagnostic))
    a_cases, b_cases = {c['task_id']: c for c in a_rows}, {c['task_id']: c for c in b_rows}
    assigned = {arm: {x['task_id'] for x in packet.assignments if x['arm_id'] == arm} for arm in (a, b)}
    if (set(a_cases) != set(b_cases) or assigned[a] != assigned[b]
            or set(a_cases) != assigned[a] or set(b_cases) != assigned[b]
            or len(a_cases) != len(a_rows) or len(b_cases) != len(b_rows)
            or any(any(a_cases[t].get(k) != b_cases[t].get(k) for k in _COHORT) for t in set(a_cases) & set(b_cases))):
        gates.append(_diagnostic('COHORT_MISMATCH', scope,
                                 'Frozen task/query/gold/group/selection cohorts differ; no intersection or rows dropped.', refs))
    for arm, rows in ((a, a_rows), (b, b_rows)):
        actual, declared = packet.manifest['actual_settings'][arm], packet.protocol['arms'][arm]
        unknown = [k for k in _SETTINGS if actual[k] is None or declared[k] is None]
        if unknown:
            code = 'UNKNOWN_ACTUAL_RETRY_POLICY' if 'retry_policy' in unknown else 'UNKNOWN_ACTUAL_SETTINGS'
            gates.append(_diagnostic(code, scope, f'Arm {arm} comparison-critical settings are unknown: ' + ', '.join(unknown),
                                     _arm_refs(packet, arm, rows)))
        if packet.protocol.get('retry_selection') not in ('first_completed', 'archive_native_logical'):
            # The archive's explicit physical-history suffix is not a known logical retry policy.
            gates.append(_diagnostic('UNKNOWN_ACTUAL_RETRY_POLICY', scope,
                                     f'Arm {arm} logical selection/retry policy is unsupported.', refs))
        unknowns = evaluation['arms'][arm].get('unknown_reasons', {})
        blocked_dispatch = [k for k in ('runner_not_dispatched', 'missing_record', 'unresolved_dispatch') if unknowns.get(k, 0)]
        if blocked_dispatch:
            gates.append(_diagnostic('DISPATCH_NOT_ESTABLISHED', scope,
                                     f'Arm {arm} has non-dispatch, absent outcomes or unresolved dispatch: ' + ', '.join(blocked_dispatch), refs))
        if evaluation['arms'][arm]['attempts']['physical_attempt_count_exact'] is None:
            gates.append(_diagnostic('INCOMPLETE_PHYSICAL_HISTORY', scope,
                                     f'Arm {arm}: exact request totals, total cost and request efficiency unavailable; supported retrieval retained.',
                                     refs, severity='limitation'))
    actual_a, actual_b = packet.manifest['actual_settings'][a], packet.manifest['actual_settings'][b]
    incompatible = [key for key in _COMMON if actual_a[key] != actual_b[key]]
    if incompatible:
        gates.append(_diagnostic('COMPARISON_CONDITIONS_MISMATCH', scope,
                                 'Common comparison settings differ: ' + ', '.join(incompatible), refs))
    window = packet.protocol.get('packets', {}).get(packet.manifest['run_id'], {}).get(
        'comparison_window', packet.protocol.get('comparison_window'))
    if window is None:
        gates.append(_diagnostic('UNKNOWN_COMPARISON_WINDOW', scope, 'Frozen comparison window is unknown.', refs))
    elif any(s['run_window'] is not None and not _inside_window(s['run_window'], window) for s in (actual_a, actual_b)):
        gates.append(_diagnostic('COMPARISON_WINDOW_MISMATCH', scope, 'An actual run window is outside the frozen comparison window.', refs))
    # The common profile/budget must also agree with the protocol's global scoring policy.
    for key in ('k', 'snippet_chars', 'matching_profile'):
        if any(s[key] != packet.protocol[key] for s in (actual_a, actual_b)):
            gates.append(_diagnostic('SCORING_POLICY_MISMATCH', scope, 'Arm settings disagree with frozen scoring policy: ' + key, refs))
    eligible = not any(g['severity'] in ('block', 'error') for g in gates)
    aa, bb = evaluation['arms'][a], evaluation['arms'][b]
    difference, bounds = None, None
    bootstrap = _bootstrap_unavailable('Comparison is blocked.', n_queries=len(a_cases))
    if eligible:
        n = aa['N']
        difference = aa['H'] / n - bb['H'] / n
        bounds = [aa['H']/n - (bb['H']+bb['U'])/n, (aa['H']+aa['U'])/n - bb['H']/n]
        if aa['U'] or bb['U']:
            bootstrap = _bootstrap_unavailable('Unknown outcomes require missingness bounds; paired bootstrap suppressed.',
                        n_queries=n, n_groups=len({c['source_group_id'] for c in a_rows if c.get('source_group_id')}))
        else:
            rows = [dict(task_id=t, source_group_id=a_cases[t].get('source_group_id'),
                         a_hit=int(a_cases[t]['partition'] == 'H'), b_hit=int(b_cases[t]['partition'] == 'H'))
                    for t in sorted(a_cases)]
            bootstrap = grouped_bootstrap(rows, replicates=packet.protocol['bootstrap']['replicates'],
                                          seed=packet.protocol['bootstrap']['seed'])
    return dict(arm_a=a, arm_b=b, comparison_status='eligible' if eligible else 'blocked', gates=gates,
                delivered_difference=difference, missingness_difference_range=bounds, bootstrap=bootstrap,
                latency=_paired_latency(packet, a_cases, b_cases, eligible))


def _decision(arm, criteria):
    criteria = {key: value for key, value in (criteria or {}).items() if value is not None}
    blocked = [g for g in arm['gates'] if g['severity'] in ('block', 'error')]
    if blocked:
        return dict(criteria=criteria, decision_status='not_evaluable', reasons=blocked)
    if not criteria:
        return dict(criteria={}, decision_status='descriptive_only', reasons=[])
    checks = []
    for key, threshold in sorted(criteria.items()):
        if key == 'min_delivered_hit_rate':
            low, high = arm['missingness_range']
            status = 'met' if low >= threshold else 'failed' if high < threshold else 'indeterminate'
            observed = [low, high]
        else:
            value = arm['F' if key == 'max_provider_failure_rate' else 'U'] / arm['N']
            status = 'met' if value <= threshold else 'failed'
            observed = value
        checks.append(dict(criterion=key, threshold=threshold, observed=observed, status=status))
    status = ('fails_criteria' if any(c['status'] == 'failed' for c in checks) else
              'indeterminate' if any(c['status'] == 'indeterminate' for c in checks) else 'meets_criteria')
    return dict(criteria=criteria, decision_status=status, reasons=checks)


def assess(packet: Packet, evaluation: JsonObject) -> JsonObject:
    """Return an annotated copy; compare only explicitly requested arm pairs."""
    bootstrap = packet.protocol['bootstrap']
    if (type(bootstrap['replicates']) is not int or bootstrap['replicates'] != 2000
            or type(bootstrap['seed']) is not int or bootstrap['seed'] != 0
            or bootstrap['confidence'] != .95):
        raise ValidationError([_diagnostic('INVALID_BOOTSTRAP_POLICY', 'protocol:bootstrap',
            'Version 1 requires 2000 replicates, seed 0 and confidence 0.95.', severity='error')])
    result = copy.deepcopy(evaluation)
    result['source_inventory'] = copy.deepcopy(list(packet.sources))
    result['accounting'] = dict(assignment_basis=packet.manifest['assignment_basis'],
                                reconstruction_note=packet.manifest.get('reconciliation_note'),
                                intended_count=copy.deepcopy(packet.manifest['intended_count']),
                                task_count=len(packet.tasks), assignment_count=len(packet.assignments),
                                source_group_count=len({t['source_group_id'] for t in packet.tasks}),
                                observed_attempt_rows=len(packet.attempts))
    # Retain the original map diagnostic as an evidence limitation. Case diagnostics
    # carry blocks only where conversion is actually required and unavailable.
    for d in result['diagnostics']:
        if d['code'] in ('UNKNOWN_ACTUAL_SETTINGS', 'UNKNOWN_ACTUAL_RETRY_POLICY') and d['scope'].startswith('arm:'):
            arm = d['scope'][4:]
            d['scope'] = 'metric:arm:' + arm + ':comparison_conditions'
            d['source_refs'] = _arm_refs(packet, arm, [c for c in result['cases'] if c['arm_id'] == arm])
        if d['code'] == 'MISSING_MATCH_EVIDENCE' and d['scope'] == 'conversion_map':
            d['severity'] = 'limitation'
    for arm, data in result['arms'].items():
        cases = [c for c in result['cases'] if c['arm_id'] == arm]
        data['settings'] = dict(declared=copy.deepcopy(packet.protocol['arms'][arm]),
                                actual=copy.deepcopy(packet.manifest['actual_settings'][arm]))
        data['gates'] = _arm_gates(packet, result, arm, cases)
        ids = {c['assignment_id'] for c in cases}
        attempts = tuple(a for a in packet.attempts if a['assignment_id'] in ids)
        complete = (packet.manifest['attempt_history'][arm] == 'complete'
                    and data['attempts']['physical_attempt_count_exact'] == len(attempts))
        data['cost'] = observed_cost(attempts, history_complete=complete)
        data['latency'] = _latency(packet, cases)
    result['pairs'] = [_pair(packet, result, p['arm_a'], p['arm_b'])
                       for p in packet.protocol['requested_comparisons']]
    result['decisions'] = {arm: _decision(data, packet.protocol['decision_criteria'].get(arm))
                           for arm, data in sorted(result['arms'].items())}
    # Collect newly generated findings while preserving source diagnostic provenance.
    for finding in [g for arm in result['arms'].values() for g in arm['gates']] + [
            g for pair in result['pairs'] for g in pair['gates']]:
        if finding not in result['diagnostics']:
            result['diagnostics'].append(copy.deepcopy(finding))
    result['limitations'] = sorted(set(result['limitations']) | {
        'Retrieval is not answer quality or citation support.',
        'A miss does not prove index absence.',
        'Missingness bounds are not confidence intervals.',
        'The demonstration is too small to resolve tiny provider differences.'})
    return result


def build_verdict(evaluation: JsonObject) -> JsonObject:
    """Documented summary subset; inspectable response/case text stays in evaluation."""
    fields = ('schema_version', 'run_id', 'content_id', 'protocol_hash', 'source_inventory',
              'accounting', 'arms', 'native_metrics', 'pairs', 'decisions', 'reference_checks',
              'diagnostics', 'limitations')
    return copy.deepcopy({field: evaluation[field] for field in fields})
