"""Comparison eligibility, clustered uncertainty and independent arm decisions."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest

from pilotpack import compare, ingest, score
from pilotpack.schema import Packet, ValidationError
from support import ROOT, apply_mutation, rehash, tree_hash, write_json


def control(n=10, a=('H',) * 4 + ('U',) * 3 + ('M',) * 3,
            b=('H',) * 5 + ('U',) + ('F',) * 4):
    window = dict(started_at='2026-01-01T00:00:00Z', ended_at='2026-01-02T00:00:00Z')
    settings = dict(provider='example', mode='auto', endpoint='https://example.org', query_parameters={},
                    requested_num_results=10, k=10, snippet_chars=2000, retry_policy={'max_attempts': 1},
                    timeout_s=30, concurrency=1, run_window=window, matching_profile='literal-v1',
                    source_refs=['src#$'])
    protocol = dict(schema_version=1, arms={'a': copy.deepcopy(settings), 'b': copy.deepcopy(settings)},
                    requested_comparisons=[dict(arm_a='a', arm_b='b')], decision_criteria={}, k=10,
                    snippet_chars=2000, matching_profile='literal-v1', comparison_window=window,
                    retry_selection='first_completed', actual_retry_policy={'max_attempts': 1},
                    conversion_map_sha256=None, bootstrap=dict(seed=0, replicates=2000, confidence=0.95),
                    comparison_blockers=[])
    tasks = [dict(task_id=f't{i}', source_group_id=f'g{i // 2}', cohort_id='c', query_text=f'q{i}',
                  gold_ids={'arxiv': ['2101.00001']}, bucket='title', source_ref='src#$') for i in range(n)]
    assignments, outcomes, cases = [], [], []
    arms = {}
    for arm, values in [('a', a), ('b', b)]:
        for t, value in zip(tasks, values):
            aid = arm + ':' + t['task_id']
            assignments.append(dict(assignment_id=aid, task_id=t['task_id'], arm_id=arm,
                                    settings_id=arm, source_ref='src#$'))
            outcomes.append(dict(assignment_id=aid, observation_kind='archive_logical',
                                 terminal_status='completed', source_ref='src#$'))
            cases.append(dict(t, assignment_id=aid, arm_id=arm, partition=value, classification=value,
                              unknown_reason='completed_unknown' if value == 'U' else None,
                              selected_attempt_id=None, attempts=[], source_refs=['src#$'], diagnostics=[]))
        counts = {v: values.count(v) for v in 'HMFU'}
        arms[arm] = dict(N=n, **counts, delivered_hit_at_k=counts['H']/n,
                         missingness_range=[counts['H']/n, (counts['H']+counts['U'])/n],
                         unknown_reasons=dict(completed_unknown=counts['U'], missing_record=0,
                                              unresolved_dispatch=0, runner_not_dispatched=0),
                         attempts=dict(history='partial', observed_attempt_rows=0,
                                       physical_attempt_count_lower_bound=n, physical_attempt_count_exact=None))
    packet = Packet(Path('.'), dict(run_id='test', origin='new_run', assignment_basis='predeclared',
                    intended_count={'a': n, 'b': n}, actual_settings=copy.deepcopy(protocol['arms']),
                    attempt_history={'a': 'partial', 'b': 'partial'}, limitations=[]), protocol,
                    (dict(source_id='src', role='synthetic-control', local_path='none'),),
                    tuple(tasks), tuple(assignments), tuple(outcomes), (), ())
    evaluation = dict(schema_version=1, run_id='test', content_id='content', protocol_hash='protocol',
                      arms=arms, cases=cases, native_metrics={a: dict(profile=None, support_status='unsupported',
                      reported=None) for a in arms}, reference_checks=[dict(reference='independent_oracle',
                      status='passed', source_refs=['src#$'])], pairs=[], decisions={}, diagnostics=[], limitations=[])
    return packet, evaluation


class CompareTests(unittest.TestCase):
    def test_missingness_bounds_keep_all_assignments_and_suppress_bootstrap(self):
        packet, evaluation = control()
        original = copy.deepcopy(evaluation)
        got = compare.assess(packet, evaluation)
        pair = got['pairs'][0]
        self.assertEqual(pair['comparison_status'], 'eligible')
        self.assertAlmostEqual(pair['delivered_difference'], -0.1)
        for actual, expected in zip(pair['missingness_difference_range'], [-0.2, 0.2]):
            self.assertAlmostEqual(actual, expected, delta=1e-9)
        self.assertIsNone(pair['bootstrap']['interval'])
        self.assertIn('unknown', pair['bootstrap']['unavailable_reason'].lower())
        self.assertEqual(evaluation, original)
        self.assertEqual(len(got['cases']), 20)

    def test_different_declared_modes_and_physical_history_gaps_allow_retrieval(self):
        packet, evaluation = control()
        packet.protocol['arms']['b']['mode'] = 'pro'
        packet.manifest['actual_settings']['b']['mode'] = 'pro'
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'eligible')
        self.assertIsNone(got['arms']['a']['cost']['total'])
        self.assertIn('INCOMPLETE_PHYSICAL_HISTORY', [g['code'] for g in got['pairs'][0]['gates']])

    def test_actual_versus_declaration_blocks_only_affected_arm_and_pair(self):
        for key, value in [('mode', 'pro'), ('endpoint', 'https://other.org'), ('query_parameters', {'q': 'x'}),
                           ('retry_policy', {'max_attempts': 2}), ('timeout_s', 10), ('concurrency', 3)]:
            with self.subTest(key):
                packet, evaluation = control()
                packet.manifest['actual_settings']['a'][key] = value
                got = compare.assess(packet, evaluation)
                self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
                self.assertEqual(got['decisions']['a']['decision_status'], 'not_evaluable')
                self.assertEqual(got['decisions']['b']['decision_status'], 'descriptive_only')
                self.assertTrue(any(g['code'] == 'ACTUAL_SETTINGS_MISMATCH' and g['source_refs']
                                    for g in got['pairs'][0]['gates']))

    def test_common_conditions_cannot_silently_differ(self):
        for key, value in [('k', 5), ('requested_num_results', 12), ('snippet_chars', 0),
                           ('matching_profile', 'other'), ('run_window', dict(
                            started_at='2026-01-03T00:00:00Z', ended_at='2026-01-04T00:00:00Z'))]:
            with self.subTest(key):
                packet, evaluation = control()
                packet.manifest['actual_settings']['b'][key] = value
                packet.protocol['arms']['b'][key] = value
                got = compare.assess(packet, evaluation)
                self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
                self.assertIsNone(got['pairs'][0]['delivered_difference'])
                self.assertEqual(got['decisions']['a']['decision_status'], 'descriptive_only')

    def test_unknown_actual_settings_and_retry_policy_block_pair_preserve_absolute_status(self):
        for field in ['mode', 'retry_policy', 'query_parameters', 'timeout_s', 'concurrency', 'run_window']:
            with self.subTest(field):
                packet, evaluation = control()
                packet.manifest['actual_settings']['a'][field] = None
                packet.protocol['arms']['a'][field] = None
                packet.protocol['decision_criteria'] = {'a': {'min_delivered_hit_rate': .3}}
                got = compare.assess(packet, evaluation)
                self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
                self.assertEqual(got['decisions']['a']['decision_status'], 'meets_criteria')

    def test_unmatched_cohorts_block_without_intersection(self):
        packet, evaluation = control()
        rows = [r for r in packet.assignments if r['assignment_id'] != 'b:t9']
        packet = replace(packet, assignments=tuple(rows))
        evaluation['cases'] = [r for r in evaluation['cases'] if r['assignment_id'] != 'b:t9']
        evaluation['arms']['b']['N'] = 9
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertIn('COHORT_MISMATCH', [g['code'] for g in got['pairs'][0]['gates']])
        self.assertEqual(len(got['cases']), 19)

    def test_case_query_gold_group_and_selection_mismatches_block_pair(self):
        for field, value in [('query_text', 'other'), ('gold_ids', {'arxiv': ['9999.00001']}),
                             ('source_group_id', 'other'), ('cohort_id', 'other'), ('bucket', 'body')]:
            with self.subTest(field):
                packet, evaluation = control()
                evaluation['cases'][-1][field] = value
                got = compare.assess(packet, evaluation)
                self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')

    def test_dispatch_gates_preserve_unknown_bounds(self):
        for reason in ['runner_not_dispatched', 'missing_record', 'unresolved_dispatch']:
            with self.subTest(reason):
                packet, evaluation = control()
                evaluation['arms']['a']['unknown_reasons']['completed_unknown'] -= 1
                evaluation['arms']['a']['unknown_reasons'][reason] = 1
                got = compare.assess(packet, evaluation)
                self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
                self.assertEqual(got['arms']['a']['missingness_range'], [.4, .7])

    def test_scoped_integrity_and_reference_blocks(self):
        for code, scope in [('REFERENCE_MISMATCH', 'run'), ('HASH_MISMATCH', 'run'),
                            ('NATIVE_RANK_MISMATCH', 'assignment:a:t1'), ('DUPLICATE_ASSIGNMENT', 'arm:a')]:
            with self.subTest(code):
                packet, evaluation = control()
                evaluation['diagnostics'].append(dict(code=code, severity='block', scope=scope,
                                                      source_refs=['src#$'], message='Witness disagreement'))
                got = compare.assess(packet, evaluation)
                self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
                self.assertEqual(got['decisions']['a']['decision_status'], 'not_evaluable')
                if scope != 'run':
                    self.assertEqual(got['decisions']['b']['decision_status'], 'descriptive_only')

    def test_conversion_absence_only_blocks_affected_evidence(self):
        packet, evaluation = control()
        evaluation['diagnostics'].append(dict(code='MISSING_MATCH_EVIDENCE', severity='block',
            scope='conversion_map', source_refs=[], message='Map absent'))
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'eligible')
        evaluation['diagnostics'].append(dict(code='MISSING_MATCH_EVIDENCE', severity='block',
            scope='assignment:a:t4', source_refs=['src#$'], message='PMC judgment unavailable'))
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['decisions']['a']['decision_status'], 'not_evaluable')
        self.assertEqual(got['decisions']['b']['decision_status'], 'descriptive_only')

    def test_conversion_integrity_fault_is_not_missing_coverage(self):
        packet, evaluation = control()
        evaluation['diagnostics'].append(dict(code='CONVERSION_MAP_INTEGRITY_MISMATCH', severity='block',
            scope='conversion_map', source_refs=['src#$'], message='Frozen map bytes disagree'))
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertEqual(got['decisions']['a']['decision_status'], 'not_evaluable')
        self.assertEqual(got['decisions']['b']['decision_status'], 'not_evaluable')

    def test_metric_denominator_and_reference_support_required(self):
        for change in ['denominator', 'oracle', 'partition']:
            with self.subTest(change):
                packet, evaluation = control()
                if change == 'denominator':
                    evaluation['arms']['a']['N'] = None
                elif change == 'oracle':
                    evaluation['reference_checks'][0]['status'] = 'unavailable'
                else:
                    evaluation['arms']['a']['H'] = 5
                self.assertEqual(compare.assess(packet, evaluation)['pairs'][0]['comparison_status'], 'blocked')

    def test_no_thresholds_and_per_arm_thresholds_have_no_winner(self):
        packet, evaluation = control()
        got = compare.assess(packet, evaluation)
        self.assertEqual({v['decision_status'] for v in got['decisions'].values()}, {'descriptive_only'})
        packet.protocol['decision_criteria'] = {'a': {'min_delivered_hit_rate': .4},
                                                'b': {'max_provider_failure_rate': .3}}
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['decisions']['a']['decision_status'], 'meets_criteria')
        self.assertEqual(got['decisions']['b']['decision_status'], 'fails_criteria')
        self.assertNotIn('winner', got)
        self.assertNotIn('decision_status', got)

    def test_hit_threshold_bounds_and_exact_failure_unknown_rates(self):
        for criteria, status in [({'min_delivered_hit_rate': .3}, 'meets_criteria'),
                                  ({'min_delivered_hit_rate': .7}, 'indeterminate'),
                                  ({'min_delivered_hit_rate': .8}, 'fails_criteria'),
                                  ({'min_delivered_hit_rate': .5}, 'indeterminate'),
                                  ({'max_unknown_rate': .3}, 'meets_criteria'),
                                  ({'max_unknown_rate': .29}, 'fails_criteria'),
                                  ({'max_provider_failure_rate': 0}, 'meets_criteria'),
                                  ({'min_delivered_hit_rate': .5, 'max_unknown_rate': .2}, 'fails_criteria'),
                                  ({'min_delivered_hit_rate': None}, 'descriptive_only')]:
            with self.subTest(criteria):
                packet, evaluation = control()
                packet.protocol['decision_criteria'] = {'a': criteria}
                self.assertEqual(compare.assess(packet, evaluation)['decisions']['a']['decision_status'], status)

    def test_pair_only_block_preserves_independent_arm_decision(self):
        packet, evaluation = control()
        packet.protocol['arms']['b']['snippet_chars'] = 0
        packet.manifest['actual_settings']['b']['snippet_chars'] = 0
        packet.protocol['decision_criteria'] = {'a': {'min_delivered_hit_rate': .4}}
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertEqual(got['decisions']['a']['decision_status'], 'meets_criteria')

    def test_no_requested_pairs_and_verdict_omits_case_text(self):
        packet, evaluation = control()
        packet.protocol['requested_comparisons'] = []
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'], [])
        verdict = compare.build_verdict(got)
        for field in ['source_inventory', 'accounting', 'arms', 'native_metrics', 'reference_checks',
                      'diagnostics', 'decisions', 'pairs', 'run_id', 'content_id', 'protocol_hash']:
            self.assertIn(field, verdict)
        self.assertNotIn('cases', verdict)
        self.assertNotIn('winner', verdict)

    def test_ingested_unknown_settings_are_comparison_scoped(self):
        packet, evaluation = control()
        packet.manifest['actual_settings']['a']['mode'] = None
        packet.protocol['arms']['a']['mode'] = None
        evaluation['diagnostics'].append(dict(code='UNKNOWN_ACTUAL_SETTINGS', severity='block',
            scope='arm:a', source_refs=[], message='mode'))
        packet.protocol['decision_criteria'] = {'a': {'min_delivered_hit_rate': .4}}
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertEqual(got['decisions']['a']['decision_status'], 'meets_criteria')
        self.assertTrue(all(d['source_refs'] for d in got['diagnostics'] if d['code'] == 'UNKNOWN_ACTUAL_SETTINGS'))

    def test_canonical_native_without_original_metric_does_not_require_replay(self):
        packet, evaluation = control()
        for native in evaluation['native_metrics'].values():
            native['profile'] = 'needle-scholar-all-rows-v1'
        evaluation['reference_checks'].append(dict(reference='native_replay', status='unavailable', source_refs=[]))
        self.assertEqual(compare.assess(packet, evaluation)['pairs'][0]['comparison_status'], 'eligible')
        evaluation['native_metrics']['a']['reported'] = {'recall_at_k': .4}
        self.assertEqual(compare.assess(packet, evaluation)['pairs'][0]['comparison_status'], 'blocked')

    def test_inherited_pair_block_and_metric_scopes_are_respected(self):
        for scope, a_status in [('pair:a:b', 'descriptive_only'),
                                ('metric:arm:a:delivered_hit_at_k', 'not_evaluable')]:
            with self.subTest(scope):
                packet, evaluation = control()
                evaluation['diagnostics'].append(dict(code='UNSUPPORTED_METRIC', severity='block',
                    scope=scope, source_refs=['src#$'], message='Scoped evidence unsupported'))
                got = compare.assess(packet, evaluation)
                self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
                self.assertEqual(got['decisions']['a']['decision_status'], a_status)
                self.assertEqual(got['decisions']['b']['decision_status'], 'descriptive_only')

    def test_unsupported_exact_rank_does_not_erase_supported_direct_hits(self):
        packet, evaluation = control(n=2, a=('H', 'M'), b=('H', 'F'))
        evaluation['cases'][0].update(rank_supported=False, first_hit_rank=None, confirmed_hit_rank=2)
        evaluation['diagnostics'].append(dict(code='UNSUPPORTED_METRIC', severity='block',
            scope='metric:arm:a:native_mrr_at_k', source_refs=['src#$'], message='Exact first rank unsupported'))
        packet.protocol['decision_criteria'] = {'a': {'min_delivered_hit_rate': .5}}
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'eligible')
        self.assertEqual(got['decisions']['a']['decision_status'], 'meets_criteria')
        self.assertEqual(got['arms']['a']['H'], 1)

    def test_assess_rejects_non_v1_bootstrap_policy_even_with_unknown_outcomes(self):
        for field, value in [('replicates', 100), ('seed', 42), ('confidence', .9)]:
            with self.subTest(field), self.assertRaises(ValidationError):
                packet, evaluation = control()
                packet.protocol['bootstrap'][field] = value
                compare.assess(packet, evaluation)

    def test_explicit_frozen_comparison_blocker_cannot_be_dropped(self):
        packet, evaluation = control()
        packet.protocol['comparison_blockers'] = ['EVIDENCE_POLICY_UNESTABLISHED']
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertEqual(got['decisions']['a']['decision_status'], 'descriptive_only')
        self.assertIn('EVIDENCE_POLICY_UNESTABLISHED', [g['code'] for g in got['pairs'][0]['gates']])

    def test_partition_counts_must_agree_with_cases(self):
        packet, evaluation = control()
        evaluation['arms']['a'].update(H=5, M=2)
        got = compare.assess(packet, evaluation)
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertEqual(got['decisions']['a']['decision_status'], 'not_evaluable')



class FrozenWindowTests(unittest.TestCase):
    """Exercise both setting comparisons with otherwise eligible frozen evidence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = apply_mutation(ROOT / 'fixtures/controls/parent-v2', 'H05', self.base / 'input')
        self.manifest = json.loads((self.root / 'packet.json').read_text())
        self.protocol = json.loads((self.root / 'protocol.json').read_text())

    def assess(self, name='run'):
        write_json(self.root / 'packet.json', self.manifest)
        write_json(self.root / 'protocol.json', self.protocol)
        rehash(self.root)
        source_hash = tree_hash(self.root)
        protocol_bytes = (self.root / 'protocol.json').read_bytes()
        run = ingest.freeze(self.root, adapter='canonical', config_path=ROOT / 'fixtures/config/canonical.json',
                            protocol_path=self.root / 'protocol.json', sources_path=self.root / 'sources.json',
                            out=self.base / name)
        frozen_hash = tree_hash(run)
        packet = ingest.verify_run(run)
        evaluation = score.score_run(run)
        got = compare.assess(packet, evaluation)
        self.assertEqual(tree_hash(self.root), source_hash)
        self.assertEqual(tree_hash(run), frozen_hash)
        self.assertEqual((run / 'protocol.json').read_bytes(), protocol_bytes)
        self.assertEqual(packet.manifest['protocol_sha256'], hashlib.sha256(protocol_bytes).hexdigest())
        for arm in 'ab':
            self.assertEqual(got['arms'][arm]['settings']['actual'], self.manifest['actual_settings'][arm])
            self.assertEqual(got['arms'][arm]['settings']['declared'], self.protocol['arms'][arm])
        self.assertEqual(got['arms']['a']['N'], 4)
        self.assertEqual(got['arms']['b']['N'], 4)
        self.assertTrue(all(check['status'] != 'mismatch' for check in got['reference_checks']))
        return got

    def set_window(self, window, site):
        if site == 'actual-declared':
            for arm in 'ab':
                self.manifest['actual_settings'][arm]['run_window'] = copy.deepcopy(window)
        else:
            self.manifest['actual_settings']['b']['run_window'] = copy.deepcopy(window)
            self.protocol['arms']['b']['run_window'] = copy.deepcopy(window)

    def test_identical_window_encodings_are_eligible(self):
        got = self.assess()
        self.assertEqual(got['pairs'][0]['comparison_status'], 'eligible')
        self.assertEqual(got['pairs'][0]['gates'], [])
        self.assertEqual(got['pairs'][0]['delivered_difference'], 0.0)

    def test_equivalent_instants_match_actual_and_declared_windows(self):
        for index, (start, end) in enumerate([
                ('2026-10-16T00:00:00+00:00', '2026-10-16T02:00:00+00:00'),
                ('2026-10-16T02:00:00+02:00', '2026-10-16T04:00:00+02:00'),
                ('2026-10-15T20:00:00-04:00', '2026-10-15T22:00:00-04:00'),
                ('2026-10-16T00:00:00.000Z', '2026-10-16T02:00:00.000Z'),
                ('2026-10-16T00:00:00.000000000Z', '2026-10-16T02:00:00.000000000Z')]):
            with self.subTest(start=start):
                self.set_window(dict(started_at=start, ended_at=end), 'actual-declared')
                got = self.assess('run-' + str(index))
                self.assertEqual(got['pairs'][0]['comparison_status'], 'eligible', got['pairs'][0]['gates'])
                self.assertEqual(got['decisions']['a']['decision_status'], 'descriptive_only')

    def test_equivalent_instants_match_common_cross_arm_windows(self):
        for index, (start, end) in enumerate([
                ('2026-10-16T00:00:00+00:00', '2026-10-16T02:00:00+00:00'),
                ('2026-10-16T02:00:00+02:00', '2026-10-16T04:00:00+02:00'),
                ('2026-10-15T20:00:00-04:00', '2026-10-15T22:00:00-04:00'),
                ('2026-10-16T00:00:00.000Z', '2026-10-16T02:00:00.000Z'),
                ('2026-10-16T00:00:00.000000000Z', '2026-10-16T02:00:00.000000000Z')]):
            with self.subTest(start=start):
                self.set_window(dict(started_at=start, ended_at=end), 'cross-arm')
                got = self.assess('run-' + str(index))
                self.assertEqual(got['pairs'][0]['comparison_status'], 'eligible', got['pairs'][0]['gates'])

    def test_different_intervals_still_block_at_both_comparison_sites(self):
        original = copy.deepcopy(self.protocol['arms']['a']['run_window'])
        for site, code in [('actual-declared', 'ACTUAL_SETTINGS_MISMATCH'),
                           ('cross-arm', 'COMPARISON_CONDITIONS_MISMATCH')]:
            for endpoint, value in [('started_at', '2026-10-16T00:30:00Z'),
                                     ('ended_at', '2026-10-16T01:30:00Z'),
                                     ('started_at', '2026-10-16T00:00:00.0000001Z')]:
                with self.subTest(site=site, endpoint=endpoint):
                    # Reset the declaration changed by the preceding cross-arm case.
                    for arm in 'ab':
                        self.manifest['actual_settings'][arm]['run_window'] = copy.deepcopy(original)
                        self.protocol['arms'][arm]['run_window'] = copy.deepcopy(original)
                    self.set_window(dict(original, **{endpoint: value}), site)
                    got = self.assess(site + '-' + value.replace(':', '-'))
                    pair = got['pairs'][0]
                    self.assertEqual(pair['comparison_status'], 'blocked')
                    self.assertIn(code, [g['code'] for g in pair['gates']])
                    self.assertIsNone(pair['delivered_difference'])

    def test_unknown_local_offset_is_distinct_from_known_utc_at_both_sites(self):
        original = copy.deepcopy(self.protocol['arms']['a']['run_window'])
        for site, code in [('actual-declared', 'ACTUAL_SETTINGS_MISMATCH'),
                           ('cross-arm', 'COMPARISON_CONDITIONS_MISMATCH')]:
            for endpoint in ('started_at', 'ended_at'):
                with self.subTest(site=site, endpoint=endpoint):
                    for arm in 'ab':
                        self.manifest['actual_settings'][arm]['run_window'] = copy.deepcopy(original)
                        self.protocol['arms'][arm]['run_window'] = copy.deepcopy(original)
                    self.set_window(dict(original, **{endpoint: original[endpoint].replace('Z', '-00:00')}), site)
                    got = self.assess(site + '-' + endpoint)
                    self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
                    self.assertIn(code, [g['code'] for g in got['pairs'][0]['gates']])

    def test_missing_actual_window_still_blocks_comparison(self):
        for arm in 'ab':
            self.manifest['actual_settings'][arm]['run_window'] = None
            self.protocol['arms'][arm]['run_window'] = None
        got = self.assess()
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertIn('UNKNOWN_ACTUAL_SETTINGS', [g['code'] for g in got['pairs'][0]['gates']])
        self.assertEqual(got['decisions']['a']['decision_status'], 'descriptive_only')

    def test_missing_allowed_window_still_blocks_comparison(self):
        self.protocol['comparison_window'] = None
        got = self.assess()
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertIn('UNKNOWN_COMPARISON_WINDOW', [g['code'] for g in got['pairs'][0]['gates']])

    def test_outside_allowed_window_still_blocks_comparison(self):
        outside = dict(started_at='2026-10-17T00:00:00Z', ended_at='2026-10-17T02:00:00Z')
        for arm in 'ab':
            self.manifest['actual_settings'][arm]['run_window'] = copy.deepcopy(outside)
            self.protocol['arms'][arm]['run_window'] = copy.deepcopy(outside)
        got = self.assess()
        self.assertEqual(got['pairs'][0]['comparison_status'], 'blocked')
        self.assertIn('COMPARISON_WINDOW_MISMATCH', [g['code'] for g in got['pairs'][0]['gates']])
        self.assertIn('TIME_WINDOW_MISMATCH', [g['code'] for g in got['pairs'][0]['gates']])


class BootstrapTests(unittest.TestCase):
    def rows(self):
        # Groups differ in size and direction. Group averaging would give 0 instead of -1/3.
        return [dict(task_id='t1', source_group_id='a', a_hit=1, b_hit=0),
                dict(task_id='t2', source_group_id='b', a_hit=0, b_hit=1),
                dict(task_id='t3', source_group_id='b', a_hit=0, b_hit=1)]

    def test_grouped_resampling_is_query_weighted_and_deterministic(self):
        rows = self.rows()
        got = compare.grouped_bootstrap(rows, replicates=2000, seed=0)
        replay = compare.grouped_bootstrap(list(reversed(rows)), replicates=2000, seed=0)
        self.assertEqual(got, replay)
        self.assertEqual(got['n_groups'], 2)
        self.assertEqual(got['n_queries'], 3)
        self.assertAlmostEqual(got['point_estimate'], -1/3)
        self.assertEqual(got['interval'], [-1.0, 1.0])
        self.assertEqual(got['replicates'], 2000)
        self.assertEqual(got['seed'], 0)
        self.assertIn('query', got['estimand'])
        self.assertTrue(got['python_version'])
        self.assertIn('SMALL_GROUP_COUNT', got['qualifications'])
        # The four possible whole-group resamples yield -1, -1/3, -1/3, 1.

    def test_nearest_rank_endpoints_and_all_variants_move_together(self):
        rows = [dict(task_id=f'{g}:{i}', source_group_id=str(g), a_hit=int(g % 3 == 0),
                     b_hit=int(g % 3 == 1)) for g in range(7) for i in range(g + 1)]
        # Independent resamples flatten every query of each chosen group.
        rng = random.Random(0)
        values = []
        for _ in range(2000):
            selected = [str(rng.randrange(7)) for _ in range(7)]
            flattened = [r for group in selected for r in rows if r['source_group_id'] == group]
            values.append(sum(r['a_hit'] - r['b_hit'] for r in flattened) / len(flattened))
        values.sort()
        got = compare.grouped_bootstrap(rows, replicates=2000, seed=0)
        self.assertEqual(got['interval'], [values[49], values[1949]])

    def test_one_group_missing_group_duplicate_tasks_and_empty_unavailable(self):
        for rows in [[], self.rows()[:1], [dict(self.rows()[0], source_group_id=None), self.rows()[1]],
                     [self.rows()[0], dict(self.rows()[1], task_id='t1')]]:
            with self.subTest(rows):
                got = compare.grouped_bootstrap(rows, replicates=2000, seed=0)
                self.assertIsNone(got['interval'])
                self.assertTrue(got['unavailable_reason'])

    def test_v1_rejects_unfrozen_bootstrap_parameters(self):
        for kwargs in [dict(replicates=100, seed=0), dict(replicates=2000, seed=1)]:
            with self.subTest(kwargs), self.assertRaises(ValueError):
                compare.grouped_bootstrap(self.rows(), **kwargs)

    def test_complete_pair_uses_grouped_bootstrap_with_failures_retained(self):
        packet, evaluation = control(n=4, a=('H', 'H', 'F', 'M'), b=('M', 'F', 'H', 'H'))
        got = compare.assess(packet, evaluation)['pairs'][0]
        self.assertEqual(got['comparison_status'], 'eligible')
        self.assertEqual(got['bootstrap']['interval'], [-1.0, 1.0])
        self.assertEqual(got['bootstrap']['n_queries'], 4)
        self.assertEqual(got['bootstrap']['n_groups'], 2)


if __name__ == '__main__':
    unittest.main()
