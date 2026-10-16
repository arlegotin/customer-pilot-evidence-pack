"""Observed request cost and latency cannot invent missing physical evidence."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from pilotpack import compare
from test_compare import control


def request(amount='0.10', currency='USD', kind='observed', ref='receipt#$', index=1):
    return dict(attempt_id=f'r{index}', assignment_id='a:t0', attempt_index=index,
                status='completed', latency_ms=10 * index,
                cost=dict(amount=amount, currency=currency, kind=kind, source_ref=ref, scope='attempt'),
                source_ref='src#$')


class CostTests(unittest.TestCase):
    def test_decimal_exact_total_and_coverage(self):
        got = compare.observed_cost((request(), request('0.20', index=2)), history_complete=True)
        self.assertEqual(got['total'], '0.30')
        self.assertEqual(got['currency'], 'USD')
        self.assertEqual(got['known_subtotal'], '0.30')
        self.assertEqual(got['coverage']['observed'], 2)
        self.assertEqual(got['coverage']['attempt_rows'], 2)
        self.assertEqual(got['support_status'], 'supported')

    def test_known_zero_requires_evidence_and_empty_ledger_is_unknown(self):
        self.assertEqual(compare.observed_cost((request('0'),), history_complete=True)['total'], '0')
        self.assertIsNone(compare.observed_cost((request('0', ref=None),), history_complete=True)['total'])
        self.assertIsNone(compare.observed_cost((), history_complete=False)['total'])
        self.assertIsNone(compare.observed_cost((), history_complete=True)['total'])

    def test_incomplete_estimated_missing_and_mixed_currency_never_total(self):
        cases = [((request(),), False, {'USD': '0.10'}),
                 ((request(), request('0.20', kind='estimated', index=2)), True, {'USD': '0.10'}),
                 ((request(), request(None, None, 'missing', None, 2)), True, {'USD': '0.10'}),
                 ((request(), request('0.20', 'EUR', index=2)), True, {'USD': '0.10', 'EUR': '0.20'})]
        for attempts, complete, subtotals in cases:
            with self.subTest(attempts):
                got = compare.observed_cost(attempts, history_complete=complete)
                self.assertIsNone(got['total'])
                self.assertEqual(got['known_subtotals'], subtotals)
                self.assertTrue(got['unavailable_reason'])

    def test_wrong_scope_cannot_supply_request_cost(self):
        row = request()
        row['cost']['scope'] = 'agent'
        self.assertIsNone(compare.observed_cost((row,), history_complete=True)['total'])

    def test_assess_uses_effective_complete_history_not_manifest_claim(self):
        packet, evaluation = control()
        packet.manifest['attempt_history']['a'] = 'complete'
        row = request()
        packet = replace(packet, attempts=(row,))
        # Scorer found absent physical rows: a manifest assertion cannot override it.
        got = compare.assess(packet, evaluation)
        self.assertIsNone(got['arms']['a']['cost']['total'])
        self.assertEqual(got['arms']['a']['cost']['known_subtotal'], '0.10')

    def test_marginal_sorted_samples_never_become_task_paired_latency(self):
        packet, evaluation = control()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'engine.json').write_text(json.dumps(dict(latency=dict(n=3, samples_ms=[1, 2, 3]),
                                                            num_scored=99, search_errors=2)))
            packet = replace(packet, root=root, sources=(dict(source_id='src', role='engine-terminal-results',
                                                              local_path='engine.json'),))
            got = compare.assess(packet, evaluation)
        self.assertIsNone(got['arms']['a']['latency']['paired'])
        self.assertIsNone(got['pairs'][0]['latency']['paired'])
        marginal = got['arms']['a']['latency']['marginal'][0]
        self.assertEqual(marginal['native_eligibility']['num_scored'], 99)
        self.assertEqual(marginal['source_refs'], ['src#$.latency'])
        self.assertEqual(marginal['samples_ms'], [1, 2, 3])

    def test_only_selected_response_linked_latency_can_pair(self):
        packet, evaluation = control(n=2, a=('H', 'M'), b=('M', 'H'))
        attempts = []
        for i, case in enumerate(evaluation['cases']):
            row = request(index=i+1)
            row['assignment_id'] = case['assignment_id']
            row['latency_ms'] = [10, 20, 30, 40][i]
            case['selected_attempt_id'] = row['attempt_id']
            attempts.append(row)
        packet = replace(packet, attempts=tuple(attempts))
        got = compare.assess(packet, evaluation)['pairs'][0]['latency']
        self.assertEqual([r['difference_ms'] for r in got['paired']], [-20, -20])
        self.assertEqual(got['n_tasks'], 2)


if __name__ == '__main__':
    unittest.main()
