"""Literal scoring, retry and independent reconciliation regressions."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pilotpack import ingest, score
from pilotpack.schema import ValidationError
from support import ROOT, make_packet, rehash, write_json, write_rows


def result(url='https://example.org', rank=1, **extra):
    return dict(dict(rank=rank, url=url, title=None, snippet=None, returned_ids={}), **extra)


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def freeze(self, mutate=None, ten=False, identifier_map=None):
        source = make_packet(self.base)
        manifest = json.loads((source / 'packet.json').read_text())
        protocol = json.loads((source / 'protocol.json').read_text())
        data = {n: [json.loads(x) for x in (source / (n + '.jsonl')).read_text().splitlines()]
                for n in ('tasks', 'assignments', 'outcomes', 'attempts')}
        if ten:
            for n in data:
                data[n] = [json.loads(x) for x in (ROOT / 'fixtures/canonical/ten-assignments' / (n + '.jsonl')).read_text().splitlines()]
                for row in data[n]:
                    row['source_ref'] = 'src#$'
                    if n == 'attempts':
                        row['limitations'] = ['MISSING_COST']
                    for item in row.get('results', []):
                        item['returned_ids'] = {}
            manifest['intended_count'] = {'a': 10}
            manifest['actual_settings'] = {'a': manifest['actual_settings']['a']}
            manifest['attempt_history'] = {'a': 'complete'}
            protocol['arms'] = {'a': protocol['arms']['a']}
            protocol['retry_selection'] = 'first_completed'
        if mutate:
            mutate(data, manifest, protocol)
        if identifier_map is not None:
            map_path = source / 'identifier-map.json'
            write_json(map_path, identifier_map)
            inventory = json.loads((source / 'sources.json').read_text())
            inventory['sources'].append(dict(inventory['sources'][0], source_id='conversion-map',
                local_path='identifier-map.json', role='identifier-conversion-map', parents=['src'],
                bytes=map_path.stat().st_size, sha256=hashlib.sha256(map_path.read_bytes()).hexdigest()))
            protocol['conversion_map_sha256'] = hashlib.sha256(map_path.read_bytes()).hexdigest()
            write_json(source / 'sources.json', inventory)
        for n, rows in data.items():
            write_rows(source / (n + '.jsonl'), rows)
        write_json(source / 'packet.json', manifest)
        write_json(source / 'protocol.json', protocol)
        rehash(source)
        config = self.base / 'config.json'
        write_json(config, {'adapter_profile': 'canonical-v1'})
        return ingest.freeze(source, adapter='canonical', config_path=config,
                             protocol_path=source / 'protocol.json', sources_path=source / 'sources.json',
                             out=self.base / 'run')

    def test_literal_extraction_ignores_cached_match_fields(self):
        fixture = json.loads((ROOT / 'fixtures/expected/identifier-cases.json').read_text())
        for case in fixture['cases']:
            with self.subTest(case['name']):
                self.assertEqual(score.match_rank(case['gold'], [dict(rank=1, **case['result'])],
                                                 k=2, snippet_chars=2000, identifier_map=None), case['rank'])

    def test_snippet_budget_title_and_rank_boundaries_preserve_duplicates(self):
        gold = {'arxiv': ['2101.00001']}
        hit = result('https://arxiv.org/abs/2101.00001')
        rows = [result(rank=1), result(rank=2), dict(hit, rank=3)]
        self.assertIsNone(score.match_rank(gold, rows, k=2, snippet_chars=0, identifier_map=None))
        self.assertEqual(score.match_rank(gold, rows, k=3, snippet_chars=0, identifier_map=None), 3)
        text = [result(snippet='xxx arXiv:2101.00001')]
        self.assertIsNone(score.match_rank(gold, text, k=1, snippet_chars=3, identifier_map=None))
        self.assertEqual(score.match_rank(gold, text, k=1, snippet_chars=0, identifier_map=None), 1)
        text[0]['title'] = 'arXiv:2101.00001'
        self.assertEqual(score.match_rank(gold, text, k=1, snippet_chars=3, identifier_map=None), 1)

    def test_frozen_conversion_and_missing_map_never_fabricate_match(self):
        rows = [result('https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/')]
        gold = {'pmid': ['12345678']}
        self.assertIsNone(score.match_rank(gold, rows, k=1, snippet_chars=0, identifier_map=None))
        self.assertEqual(score.match_rank(gold, rows, k=1, snippet_chars=0,
                                         identifier_map={'pmc_to_pmid': {'12345': '12345678'}}), 1)

    def test_ten_assignment_partition_and_physical_count(self):
        evaluation = score.score_run(self.freeze(ten=True))
        arm = evaluation['arms']['a']
        self.assertEqual([arm[x] for x in ('N', 'H', 'M', 'F', 'U')], [10, 4, 2, 1, 3])
        self.assertEqual(arm['delivered_hit_at_k'], 0.4)
        self.assertEqual(arm['missingness_range'], [0.4, 0.7])
        self.assertEqual(arm['unknown_reasons']['completed_unknown'], 3)
        self.assertEqual(arm['attempts']['observed_attempt_rows'], 10)
        self.assertEqual(arm['attempts']['physical_attempt_count_exact'], 10)
        self.assertEqual(evaluation['reference_checks'][0]['status'], 'passed')

    def test_empty_and_unreconstructable_denominators(self):
        def mutate(data, manifest, protocol):
            for name in data:
                data[name] = []
            manifest['intended_count'] = {'a': 0, 'b': 0}
        evaluation = score.score_run(self.freeze(mutate))
        self.assertIsNone(evaluation['arms']['a']['delivered_hit_at_k'])
        self.assertIsNone(evaluation['arms']['a']['missingness_range'])
        self.assertIn('EMPTY_COHORT', [d['code'] for d in evaluation['diagnostics']])
        # A separate frozen source is required for the other identity.
        self.tmp.cleanup()
        self.setUp()
        def unknown(data, manifest, protocol):
            manifest['assignment_basis'] = 'unreconstructable'
            manifest['intended_count'] = {'a': None, 'b': None}
            protocol['assignment_basis'] = 'unreconstructable'
        evaluation = score.score_run(self.freeze(unknown))
        self.assertIsNone(evaluation['arms']['a']['N'])
        self.assertIsNone(evaluation['arms']['a']['missingness_range'])

    def test_provider_error_runner_nondispatch_and_true_empty(self):
        def mutate(data, manifest, protocol):
            data['attempts'] = []
            for i, row in enumerate(data['outcomes']):
                row.update(results=[], reported_hit_rank=None, selected_attempt_id=None,
                           observation_kind='archive_logical')
                if i == 0:
                    row['terminal_status'] = 'provider_error'
                elif i == 1:
                    row.update(terminal_status='runner_failure', observation_kind='not_dispatched')
        evaluation = score.score_run(self.freeze(mutate))
        self.assertEqual([r['partition'] for r in evaluation['cases']], ['F', 'U', 'M', 'M'])
        self.assertEqual(evaluation['arms']['a']['unknown_reasons']['runner_not_dispatched'], 1)

    def test_missing_conversion_only_marks_affected_completed_case_unknown(self):
        def mutate(data, manifest, protocol):
            manifest['extensions'] = {'native_profile': 'needle-scholar-all-rows-v1'}
            data['tasks'][0]['gold_ids'] = {'pmid': ['12345678']}
            data['attempts'] = []
            for row in data['outcomes']:
                row.update(observation_kind='archive_logical', selected_attempt_id=None, reported_hit_rank=None)
                if row['assignment_id'] == 'a:t1':
                    row['results'] = [result('https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/')]
                if row['assignment_id'] == 'b:t1':
                    row['results'] = [result('https://pubmed.ncbi.nlm.nih.gov/12345678/')]
        evaluation = score.score_run(self.freeze(mutate))
        self.assertEqual([r['partition'] for r in evaluation['cases']], ['U', 'H', 'H', 'H'])
        self.assertIn('MISSING_MATCH_EVIDENCE', [d['code'] for d in evaluation['diagnostics']])
        self.assertEqual(evaluation['native_metrics']['a']['num_scored'], 2)
        self.assertEqual(evaluation['native_metrics']['a']['search_errors'], 0)
        self.assertIsNone(evaluation['native_metrics']['a']['recall_at_k'])
        self.assertEqual(evaluation['native_metrics']['b']['recall_at_k'], 1.0)

    def test_native_archived_null_rank_cannot_hide_recomputed_hit(self):
        def mutate(data, manifest, protocol):
            manifest['extensions'] = {'native_profile': 'needle-scholar-all-rows-v1'}
            data['outcomes'][1]['reported_hit_rank'] = None
        evaluation = score.score_run(self.freeze(mutate))
        row = next(c for c in evaluation['cases'] if c['assignment_id'] == 'a:t2')
        self.assertEqual(row['partition'], 'H')
        self.assertIn('NATIVE_RANK_MISMATCH', [d['code'] for d in row['diagnostics']])

    def test_cached_rank_forgery_is_diagnosed_and_not_used(self):
        def mutate(data, manifest, protocol):
            data['outcomes'][1]['results'][0]['url'] = 'https://example.org'
            data['outcomes'][1]['results'][0]['returned_ids'] = {'arxiv': ['1234.56789']}
        evaluation = score.score_run(self.freeze(mutate))
        row = next(x for x in evaluation['cases'] if x['assignment_id'] == 'a:t2')
        self.assertEqual(row['partition'], 'M')
        self.assertIn('NATIVE_RANK_MISMATCH', [d['code'] for d in evaluation['diagnostics']])

    def test_native_all_rows_denominator_is_not_conditional(self):
        def mutate(data, manifest, protocol):
            manifest['extensions'] = {'native_profile': 'needle-scholar-all-rows-v1'}
            data['outcomes'][3].update(terminal_status='provider_error', results=[], reported_hit_rank=None)
        evaluation = score.score_run(self.freeze(mutate))
        native = evaluation['native_metrics']['b']
        self.assertEqual(native['support_status'], 'supported')
        self.assertEqual(native['num_scored'], 2)
        self.assertEqual(native['recall_at_k'], 0.5)
        self.assertEqual(native['mrr_at_k'], 0.5)
        self.assertEqual(native['search_errors'], 1)

    def test_reference_tolerance_and_exact_counts(self):
        run = self.freeze()
        evaluation = score.score_run(run)
        near = copy.deepcopy(evaluation)
        near['arms']['a']['delivered_hit_at_k'] += 1e-10
        near['arms']['a']['missingness_range'][0] += 1e-10
        self.assertEqual(score.check_reference(run, near), [])
        far = copy.deepcopy(evaluation)
        far['arms']['a']['delivered_hit_at_k'] += 1e-8
        self.assertIn('REFERENCE_MISMATCH', [d['code'] for d in score.check_reference(run, far)])
        far = copy.deepcopy(evaluation)
        far['arms']['a']['N'] += 1
        self.assertIn('REFERENCE_MISMATCH', [d['code'] for d in score.check_reference(run, far)])

    def test_reference_binds_case_and_run_identities(self):
        run = self.freeze()
        evaluation = score.score_run(run)
        for field in ('content_id', 'protocol_hash'):
            edited = copy.deepcopy(evaluation)
            edited[field] = '0' * 64
            self.assertIn('REFERENCE_MISMATCH', [d['code'] for d in score.check_reference(run, edited)])
        edited = copy.deepcopy(evaluation)
        edited['cases'][0]['task_id'] = 'different'
        self.assertIn('REFERENCE_MISMATCH', [d['code'] for d in score.check_reference(run, edited)])

    def test_physical_lower_bound_sums_distinct_dispatch_evidence(self):
        def mutate(data, manifest, protocol):
            manifest['attempt_history']['a'] = 'complete'
        evaluation = score.score_run(self.freeze(mutate))
        arm = evaluation['arms']['a']['attempts']
        self.assertEqual(arm['observed_attempt_rows'], 1)
        self.assertEqual(arm['physical_attempt_count_lower_bound'], 2)
        self.assertIsNone(arm['physical_attempt_count_exact'])
        self.assertIn('UNKNOWN_ATTEMPT_HISTORY', [d['code'] for d in evaluation['diagnostics'] if d['scope'] == 'arm:a'])

    def test_direct_hit_survives_missing_conversion_but_exact_rank_does_not(self):
        def mutate(data, manifest, protocol):
            manifest['extensions'] = {'native_profile': 'needle-scholar-all-rows-v1'}
            data['tasks'][0]['gold_ids'] = {'pmid': ['12345678']}
            data['attempts'] = []
            for row in data['outcomes']:
                row.update(observation_kind='archive_logical', selected_attempt_id=None, reported_hit_rank=None)
                if row['assignment_id'].endswith('t1'):
                    row['results'] = [result('https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/'),
                                      result('https://pubmed.ncbi.nlm.nih.gov/12345678/', rank=2)]
        evaluation = score.score_run(self.freeze(mutate))
        row = evaluation['cases'][0]
        self.assertEqual(row['partition'], 'H')
        self.assertEqual(row['confirmed_hit_rank'], 2)
        self.assertIsNone(row['first_hit_rank'])
        self.assertEqual(evaluation['native_metrics']['a']['recall_at_k'], 1.0)
        self.assertIsNone(evaluation['native_metrics']['a']['mrr_at_k'])
        self.assertEqual(evaluation['native_metrics']['a']['support_status'], 'partial')

    def test_unknown_snippet_budget_is_not_uncapped(self):
        def mutate(data, manifest, protocol):
            manifest['actual_settings']['a']['snippet_chars'] = None
            data['attempts'] = []
            for row in data['outcomes']:
                row.update(observation_kind='archive_logical', selected_attempt_id=None, reported_hit_rank=None)
                row['results'] = [result(snippet='See arXiv:1234.56789')]
        evaluation = score.score_run(self.freeze(mutate))
        self.assertEqual(evaluation['arms']['a']['U'], 2)
        self.assertEqual(evaluation['arms']['b']['H'], 2)

    def test_review_internal_attempt_gap_invalidates_exact_physical_history(self):
        def mutate(data, manifest, protocol):
            manifest['attempt_history']['a'] = 'complete'
            protocol['retry_selection'] = 'first_completed'
            request = dict(data['attempts'][0], cost=dict(amount=None, currency=None, kind='missing',
                           scope='attempt', source_ref=None), limitations=['MISSING_COST'])
            data['attempts'] = [dict(request, attempt_id='gap-1', attempt_index=1, status='provider_error', results=[]),
                                dict(request, attempt_id='gap-3', attempt_index=3),
                                dict(request, assignment_id='a:t2', attempt_id='other-1', attempt_index=1)]
            data['outcomes'][0]['selected_attempt_id'] = 'gap-3'
            data['outcomes'][1].update(selected_attempt_id='other-1', observation_kind='attempt_backed')
        run = self.freeze(mutate)
        evaluation = score.score_run(run)
        physical = evaluation['arms']['a']['attempts']
        self.assertEqual(physical['observed_attempt_rows'], 3)
        self.assertEqual(physical['physical_attempt_count_lower_bound'], 4)
        self.assertIsNone(physical['physical_attempt_count_exact'])
        self.assertIn('UNKNOWN_ATTEMPT_HISTORY', [d['code'] for d in evaluation['diagnostics'] if d['scope']=='arm:a'])
        oracle = json.loads(subprocess.check_output([sys.executable, str(ROOT / 'reference/oracle.py'), '--run', str(run)], text=True))
        self.assertEqual(oracle['arms']['a']['physical_attempt_count_lower_bound'], 4)
        self.assertIsNone(oracle['arms']['a']['physical_attempt_count_exact'])
        self.assertFalse(any(d['code']=='REFERENCE_MISMATCH' for d in evaluation['diagnostics']))

    def test_review_empty_delivery_needs_no_snippet_budget_but_unknown_judgments_stay_unknown(self):
        def mutate(data, manifest, protocol):
            manifest['actual_settings']['a']['snippet_chars'] = None
            data['attempts'] = []
            for i, row in enumerate(data['outcomes']):
                row.update(observation_kind='archive_logical', selected_attempt_id=None,
                           reported_hit_rank=None, results=[], limitations=[])
                if i==2:
                    row['limitations'] = ['UNKNOWN_JUDGMENT']
                if i==3:
                    row.update(observation_kind='unobserved', terminal_status='unknown', limitations=['MISSING_OUTCOME'])
        run = self.freeze(mutate)
        evaluation = score.score_run(run)
        self.assertEqual([evaluation['arms']['a'][k] for k in ('N','H','M','F','U')], [2,0,2,0,0])
        self.assertEqual(evaluation['arms']['a']['missingness_range'], [0.0,0.0])
        self.assertEqual([c['partition'] for c in evaluation['cases']], ['M','M','U','U'])
        oracle = json.loads(subprocess.check_output([sys.executable, str(ROOT / 'reference/oracle.py'), '--run', str(run)], text=True))
        self.assertEqual(oracle['arms']['a']['M'], 2)
        self.assertEqual(oracle['arms']['a']['U'], 0)
        self.assertFalse(any(d['code']=='REFERENCE_MISMATCH' for d in evaluation['diagnostics']))

    def test_review_url_hit_survives_unknown_budget_with_rank_qualified_when_needed(self):
        def mutate(data, manifest, protocol):
            manifest['actual_settings']['a']['snippet_chars'] = None
            manifest['extensions'] = {'native_profile':'needle-scholar-all-rows-v1'}
            data['attempts'] = []
            for row in data['outcomes']:
                row.update(observation_kind='archive_logical', selected_attempt_id=None)
            data['outcomes'][1].update(results=[result(snippet='arXiv:1234.56789'),
                result('https://arxiv.org/abs/1234.56789', rank=2)], reported_hit_rank=None)
        run = self.freeze(mutate)
        evaluation = score.score_run(run)
        first, later = evaluation['cases'][:2]
        self.assertEqual(first['partition'], 'H')
        self.assertEqual(first['first_hit_rank'], 1)
        self.assertEqual(later['partition'], 'H')
        self.assertEqual(later['confirmed_hit_rank'], 2)
        self.assertIsNone(later['first_hit_rank'])
        self.assertFalse(later['rank_supported'])
        self.assertEqual(evaluation['native_metrics']['a']['recall_at_k'], 1.0)
        self.assertIsNone(evaluation['native_metrics']['a']['mrr_at_k'])
        oracle = json.loads(subprocess.check_output([sys.executable, str(ROOT / 'reference/oracle.py'), '--run', str(run)], text=True))
        self.assertEqual(oracle['assignments']['a:t1']['first_hit_rank'], 1)
        self.assertEqual(oracle['assignments']['a:t2']['partition'], 'H')
        self.assertIsNone(oracle['assignments']['a:t2']['first_hit_rank'])
        self.assertFalse(any(d['code']=='REFERENCE_MISMATCH' for d in evaluation['diagnostics']))

    def test_complete_history_without_request_rows_cannot_claim_exact_zero(self):
        def mutate(data, manifest, protocol):
            data['attempts'] = []
            manifest['attempt_history'] = {'a':'complete', 'b':'complete'}
            for row in data['outcomes']:
                row.update(observation_kind='archive_logical', selected_attempt_id=None)
        evaluation = score.score_run(self.freeze(mutate))
        self.assertIsNone(evaluation['arms']['a']['attempts']['physical_attempt_count_exact'])
        self.assertEqual(evaluation['arms']['a']['attempts']['physical_attempt_count_lower_bound'], 2)

    def test_retry_history_is_reconciled_independently_end_to_end(self):
        def mutate(data, manifest, protocol):
            protocol['retry_selection'] = 'first_completed'
            request = data['attempts'][0]
            request['cost'] = dict(amount=None, currency=None, kind='missing', scope='attempt', source_ref=None)
            request['limitations'] = ['MISSING_COST']
            data['attempts'] = [dict(request, attempt_id='error', attempt_index=1, status='provider_error', results=[]),
                                dict(request, attempt_id='empty', attempt_index=2, results=[]),
                                dict(request, attempt_id='later-hit', attempt_index=3)]
            data['outcomes'][0].update(selected_attempt_id='empty', results=[], reported_hit_rank=None)
        evaluation = score.score_run(self.freeze(mutate))
        self.assertEqual(evaluation['cases'][0]['selected_attempt_id'], 'empty')
        self.assertEqual(evaluation['cases'][0]['partition'], 'M')
        self.assertFalse(any(d['code'] == 'REFERENCE_MISMATCH' for d in evaluation['diagnostics']))

    def test_map_types_are_not_coerced_to_identifiers(self):
        for mapping in ({'pmc_to_pmid': {'123': True}}, {'pmc_to_pmid': {'123': 456}},
                        {'pmc_to_pmid': {'PMC123': '456'}}, {'different': {}}):
            with self.subTest(mapping=mapping), self.assertRaises(ValidationError) as cm:
                score.match_rank({'pmid':['456']}, [], k=1, snippet_chars=0, identifier_map=mapping)
            self.assertEqual(cm.exception.diagnostics[0]['code'], 'INVALID_IDENTIFIER_MAP')

    def test_provenanced_frozen_map_scores_offline_and_cites_evidence(self):
        def mutate(data, manifest, protocol):
            data['tasks'][0]['gold_ids'] = {'pmid':['12345678']}
            data['attempts'] = []
            for row in data['outcomes']:
                row.update(observation_kind='archive_logical', selected_attempt_id=None, reported_hit_rank=None)
                if row['assignment_id'].endswith('t1'):
                    row['results'] = [result('https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/')]
        evaluation = score.score_run(self.freeze(mutate, identifier_map={'pmc_to_pmid':{'12345':'12345678'}}))
        self.assertEqual(evaluation['cases'][0]['partition'], 'H')
        self.assertIn('conversion-map#$', evaluation['cases'][0]['source_refs'])
        self.assertFalse(any(d['code'] == 'REFERENCE_MISMATCH' for d in evaluation['diagnostics']))

    def test_explicit_unavailable_map_preserves_unaffected_metrics(self):
        def mutate(data, manifest, protocol):
            protocol['conversion_map_sha256'] = 'a' * 64
            manifest['extensions'] = {'conversion_map':dict(status='unavailable', source_id=None, reason='Not archived')}
        evaluation = score.score_run(self.freeze(mutate))
        self.assertEqual(evaluation['arms']['a']['H'], 2)
        self.assertEqual(evaluation['arms']['b']['H'], 2)
        self.assertEqual(evaluation['arms']['a']['U'], 0)
        self.assertIn('MISSING_MATCH_EVIDENCE', [d['code'] for d in evaluation['diagnostics']])


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.assignment = dict(assignment_id='a:t', task_id='t', arm_id='a', source_ref='src#$')
        self.protocol = dict(retry_selection='first_completed', actual_retry_policy={'max_attempts': 3})
        self.attempts = tuple(dict(attempt_id='attempt-' + str(i), assignment_id='a:t', attempt_index=i,
                                   status='provider_error' if i == 1 else 'completed', source_ref='src#$',
                                   results=[] if i < 3 else [result('https://arxiv.org/abs/2101.00001')])
                              for i in (1, 2, 3))
        self.outcome = dict(assignment_id='a:t', terminal_status='completed', observation_kind='attempt_backed',
                            selected_attempt_id='attempt-2', results=[], limitations=[], source_ref='src#$')

    def test_first_completed_empty_beats_later_hit(self):
        delivery = score.select_delivery(self.assignment, self.outcome, tuple(reversed(self.attempts)), self.protocol)
        self.assertEqual(delivery['selected_attempt_id'], 'attempt-2')
        self.assertEqual(delivery['classification'], 'M')
        self.assertEqual(delivery['results'], [])

    def test_all_terminal_errors_are_failures(self):
        attempts = tuple(dict(x, status='provider_error', results=[]) for x in self.attempts)
        outcome = dict(self.outcome, terminal_status='provider_error', selected_attempt_id='attempt-3')
        self.assertEqual(score.select_delivery(self.assignment, outcome, attempts, self.protocol)['classification'], 'F')

    def test_interrupted_retry_blocks_even_when_terminal_outcome_claims_error(self):
        attempts = (self.attempts[0], dict(self.attempts[1], status='unresolved'))
        outcome = dict(self.outcome, terminal_status='provider_error', selected_attempt_id=None)
        delivery = score.select_delivery(self.assignment, outcome, attempts, self.protocol)
        self.assertEqual(delivery['classification'], 'U')
        self.assertIn('INTERRUPTED_RETRY', [d['code'] for d in delivery['diagnostics']])

    def test_gap_before_completed_attempt_cannot_prove_first_delivery(self):
        attempts = (self.attempts[0], self.attempts[2])
        outcome = dict(self.outcome, selected_attempt_id='attempt-3', results=self.attempts[2]['results'])
        delivery = score.select_delivery(self.assignment, outcome, attempts, self.protocol)
        self.assertEqual(delivery['classification'], 'U')
        self.assertIn('UNKNOWN_ATTEMPT_HISTORY', [d['code'] for d in delivery['diagnostics']])

    def test_better_retry_or_contradictory_response_is_blocked(self):
        for outcome in (dict(self.outcome, selected_attempt_id='attempt-3'),
                        dict(self.outcome, results=self.attempts[2]['results'])):
            delivery = score.select_delivery(self.assignment, outcome, self.attempts, self.protocol)
            self.assertEqual(delivery['classification'], 'U')
            self.assertIn('RETRY_SELECTION_MISMATCH', [d['code'] for d in delivery['diagnostics']])


class AllSupportedARegression(unittest.TestCase):
    def test_every_supported_rank_and_metric_against_oracle_and_unchanged_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = ingest.freeze(ROOT / 'fixtures/real/packet-a', adapter='needle-scholar',
                                config_path=ROOT / 'fixtures/config/packet-a.json', protocol_path=ROOT / 'protocol.json',
                                sources_path=ROOT / 'sources.json', out=Path(tmp) / 'run')
            evaluation = score.score_run(run)
            self.assertTrue(all(c['status'] == 'passed' for c in evaluation['reference_checks']))
            self.assertEqual(evaluation['reference_checks'][0]['assignment_count'], 972)
            self.assertEqual(len(evaluation['cases']), 972)
            self.assertEqual(len({c['task_id'] for c in evaluation['cases']}), 324)
            self.assertEqual(len({c['source_group_id'] for c in evaluation['cases']}), 81)
            self.assertEqual([evaluation['arms']['perplexity'][x] for x in ('N','H','M','F','U')], [324,0,0,324,0])
            self.assertEqual(evaluation['native_metrics']['perplexity']['num_scored'], 324)
            self.assertEqual(evaluation['native_metrics']['bing']['reported']['num_scored'], 384)
            self.assertNotIn('ultimate', evaluation['arms'])
            self.assertIn('selected_engine_ultimate', evaluation['native_metrics']['ceilings'])
            for arm in evaluation['arms'].values():
                self.assertEqual(arm['attempts']['observed_attempt_rows'], 0)
                self.assertIsNone(arm['attempts']['physical_attempt_count_exact'])
            oracle = json.loads(subprocess.check_output([sys.executable, str(ROOT / 'reference/oracle.py'), '--run', str(run)], text=True))
            native = json.loads((run / 'raw/baseline-native.json').read_text())
            tasks = [json.loads(x) for x in (run / 'tasks.jsonl').read_text().splitlines()]
            ordered = sorted(tasks, key=lambda t: int(t['source_ref'].split('line=')[1]))
            by_id = {c['assignment_id']: c for c in evaluation['cases']}
            for arm_id, arm in evaluation['arms'].items():
                ranks = [by_id[arm_id + ':' + t['task_id']]['first_hit_rank'] for t in ordered]
                self.assertEqual(ranks, native['engines'][arm_id]['per_query_hit_ranks'])
                self.assertEqual(arm['N'], oracle['arms'][arm_id]['N'])
                for metric in ('num_scored', 'search_errors', 'recall_at_k', 'mrr_at_k'):
                    self.assertAlmostEqual(evaluation['native_metrics'][arm_id][metric], native['engines'][arm_id][metric], delta=1e-9)


if __name__ == '__main__':
    unittest.main()
