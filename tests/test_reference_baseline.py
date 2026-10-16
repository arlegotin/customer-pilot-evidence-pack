"""Independent literal expectations; bugs caught: denominator loss and ID/rank mistakes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from reference.oracle import evaluate_run

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'fixtures'


class ReferenceBaselineTests(unittest.TestCase):
    def test_ten_assignments_keeps_failures_and_unknowns(self):
        result = evaluate_run(FIXTURES / 'canonical' / 'ten-assignments')
        arm = result['arms']['a']
        self.assertEqual([arm[x] for x in ('N', 'H', 'M', 'F', 'U')], [10, 4, 2, 1, 3])
        self.assertEqual(arm['delivered_hit_at_k'], 0.4)
        self.assertEqual(arm['missingness_range'], [0.4, 0.7])
        self.assertEqual(arm['physical_attempt_count_exact'], 10)
        self.assertEqual(arm['observed_attempt_rows'], 10)

    def test_literal_aliases_first_rank_empty_and_unknown(self):
        records = evaluate_run(FIXTURES / 'canonical' / 'ten-assignments')['assignments']
        self.assertEqual([records['a:' + key]['first_hit_rank'] for key in
                          ('one', 'two', 'three', 'four')], [1, 2, 1, 1])
        self.assertEqual(records['a:five']['partition'], 'M')
        self.assertEqual(records['a:six']['partition'], 'M')
        self.assertEqual(records['a:eight']['partition'], 'U')
        self.assertEqual(records['a:nine']['partition'], 'U')

    def test_synthetic_native_metrics_are_unsupported_without_replay_profile(self):
        arm = evaluate_run(FIXTURES / 'canonical' / 'ten-assignments')['arms']['a']
        self.assertIsNone(arm['native_metrics']['recall_at_k'])
        self.assertEqual(arm['native_metrics']['support_status'], 'unsupported')

    def test_oracle_cli_diagnostic_and_exit_code(self):
        good = subprocess.run([sys.executable, 'reference/oracle.py', '--run',
                               str(FIXTURES / 'canonical' / 'ten-assignments')],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)['arms']['a']['H'], 4)
        with tempfile.TemporaryDirectory() as tmp:
            bad = subprocess.run([sys.executable, 'reference/oracle.py', '--run', tmp],
                                 cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(bad.stdout, '')
        self.assertTrue(bad.stderr)

class AcquiredPacketTests(unittest.TestCase):
    def test_bounded_export_reconciles_frozen_examples_without_physical_fabrication(self):
        from reference.prepare_packet import prepare_run
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'
            prepare_run(FIXTURES / 'real' / 'packet-a', FIXTURES / 'config' / 'packet-a.json', run)
            scored = evaluate_run(run)
            expected = json.loads((FIXTURES / 'expected' / 'packet-a.json').read_text())
            for item in expected['examples']:
                row = scored['assignments'][item['arm_id'] + ':' + item['task_id']]
                self.assertEqual(row['partition'], item['expected_partition'], item)
                self.assertEqual(row['first_hit_rank'], item['expected_first_hit_rank'], item)
                self.assertEqual(row['result_count'], item['expected_result_count'], item)
            self.assertEqual(scored['task_count'], 324)
            self.assertEqual(scored['source_group_count'], 81)
            self.assertEqual([scored['arms']['perplexity'][k] for k in ('N', 'H', 'M', 'F', 'U')],
                             [324, 0, 0, 324, 0])
            self.assertIsNone(scored['arms']['bing']['physical_attempt_count_exact'])
            self.assertEqual(scored['arms']['bing']['observed_attempt_rows'], 0)
            with self.assertRaises(FileExistsError):
                prepare_run(FIXTURES / 'real' / 'packet-a', FIXTURES / 'config' / 'packet-a.json', run)

    def test_unchanged_native_scorer_replays_rank_and_denominator(self):
        native_python = ROOT / '.cache/native-venv/bin/python'
        if not native_python.exists():
            self.skipTest('native isolated environment not retained; see native-baseline.md')
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([str(native_python), 'reference/needle_replay.py', '--packet',
                                   str(FIXTURES / 'real/packet-a'), '--checkout', '.cache/needle-pinned',
                                   '--out', str(Path(tmp) / 'native.json')], cwd=ROOT,
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            replay = json.loads((Path(tmp) / 'native.json').read_text())
            self.assertEqual(replay['discrepancies'], [])
            self.assertEqual(replay['engines']['perplexity']['num_scored'], 324)
            self.assertEqual(replay['engines']['perplexity']['search_errors'], 324)
            self.assertEqual(replay['engines']['perplexity']['recall_at_k'], 0.0)


if __name__ == '__main__':
    unittest.main()
