"""Real install-free subprocess commands with socket networking disabled."""
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pilotpack import cli, score
from support import ROOT, make_packet, rehash, write_json, write_rows


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = make_packet(self.base)
        self.config = self.base / 'config.json'
        write_json(self.config, {'adapter_profile': 'canonical-v1'})
        self.run, self.out = self.base / 'run', self.base / 'output'
        guard = self.base / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text(
            'import socket\ndef denied(*args, **kwargs):\n raise RuntimeError("network disabled")\n'
            'socket.socket = denied\nsocket.create_connection = denied\n')
        self.env = dict(os.environ, PYTHONPATH=str(guard) + os.pathsep + str(ROOT), PYTHONDONTWRITEBYTECODE='1')

    def command(self, *args):
        return subprocess.run([sys.executable, '-m', 'pilotpack', *map(str, args)], cwd=ROOT,
                              env=self.env, capture_output=True, text=True)

    def freeze(self):
        result = self.command('freeze', '--adapter', 'canonical', '--input', self.source, '--config', self.config,
                              '--protocol', self.source / 'protocol.json', '--sources', self.source / 'sources.json',
                              '--out', self.run)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_documents_all_three_commands_and_required_flags(self):
        for args in [('--help',), ('freeze', '--help'), ('evaluate', '--help'), ('report', '--help')]:
            result = self.command(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('needle-scholar', self.command('freeze', '--help').stdout)
        for command, flags in [('freeze', ['--adapter', '--input', '--config', '--protocol', '--sources', '--out']),
                               ('evaluate', ['--run', '--out']), ('report', ['--run', '--evaluation', '--out'])]:
            for flag in flags:
                self.assertIn(flag, self.command(command, '--help').stdout)

    def test_real_freeze_evaluate_report_replays_with_identical_bytes(self):
        self.freeze()
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 0)
        rendered = self.command('report', '--run', self.run, '--evaluation', self.out / 'evaluation.json', '--out', self.out)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        self.assertEqual(len(json.loads(before['evaluation.json'])['cases']), 4)
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 0)
        self.assertEqual(self.command('report', '--run', self.run, '--evaluation', self.out / 'evaluation.json',
                                      '--out', self.out).returncode, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})
        frozen = self.command('freeze', '--adapter', 'canonical', '--input', self.source, '--config', self.config,
                              '--protocol', self.source / 'protocol.json', '--sources', self.source / 'sources.json',
                              '--out', self.run)
        self.assertEqual(frozen.returncode, 2)

    def test_requested_blocked_comparison_emits_verdict_and_html_with_exit_three(self):
        protocol = json.loads((self.source / 'protocol.json').read_text())
        protocol['requested_comparisons'] = [dict(arm_a='a', arm_b='b')]
        write_json(self.source / 'protocol.json', protocol)
        rehash(self.source)
        self.freeze()
        result = self.command('evaluate', '--run', self.run, '--out', self.out)
        self.assertEqual(result.returncode, 3, result.stderr)
        verdict = json.loads((self.out / 'verdict.json').read_text())
        self.assertEqual(verdict['pairs'][0]['comparison_status'], 'blocked')
        result = self.command('report', '--run', self.run, '--evaluation', self.out / 'evaluation.json', '--out', self.out)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn('blocked', (self.out / 'report.html').read_text())

    def test_missing_corrupt_inputs_and_invalid_flags_leave_no_publication(self):
        for args in [('evaluate', '--run', self.run, '--out', self.out),
                     ('report', '--run', self.run, '--evaluation', self.base / 'missing', '--out', self.out),
                     ('freeze', '--adapter', 'wrong'), ('evaluate', '--wat')]:
            result = self.command(*args)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(result.stderr)
            self.assertFalse(self.out.exists())
        self.freeze()
        (self.run / 'tasks.jsonl').write_text('corrupt')
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 2)
        self.assertFalse(self.out.exists())

    def test_reference_checked_once_and_mismatch_rejects_before_publication(self):
        self.freeze()
        real = score.check_reference
        with redirect_stderr(io.StringIO()), patch('pilotpack.score.check_reference', wraps=real) as check:
            self.assertEqual(cli.evaluate_run(self.run, self.out), 0)
            self.assertEqual(check.call_count, 1)
        before = (self.out / 'evaluation.json').read_bytes()
        mismatch = dict(code='REFERENCE_MISMATCH', severity='block', scope='run', source_refs=[], message='test mismatch')
        with redirect_stderr(io.StringIO()), patch('pilotpack.score.check_reference', return_value=[mismatch]):
            self.assertEqual(cli.evaluate_run(self.run, self.out), 2)
        self.assertEqual(before, (self.out / 'evaluation.json').read_bytes())

    def test_corrupt_empty_arm_summaries_exit_two_without_new_artifacts(self):
        self.freeze()
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 0)
        self.assertEqual(self.command('report', '--run', self.run, '--evaluation', self.out / 'evaluation.json',
                                      '--out', self.out).returncode, 0)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        bad = json.loads(before['evaluation.json'])
        bad['arms'] = {}
        path = self.base / 'corrupt.json'
        write_json(path, bad)
        for out in [self.base / 'fresh', self.out]:
            with self.subTest(out=out):
                result = self.command('report', '--run', self.run, '--evaluation', path, '--out', out)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('INVALID_REPORT_INPUT', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((self.base / 'fresh').exists())
                self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})

    def test_oracle_subprocess_failures_exit_two_without_replacing_prior_output(self):
        self.freeze()
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 0)
        self.assertEqual(self.command('report', '--run', self.run, '--evaluation', self.out / 'evaluation.json',
                                      '--out', self.out).returncode, 0)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        errors = [subprocess.TimeoutExpired(['independent-oracle'], 60),
                  subprocess.CalledProcessError(1, ['independent-oracle'], stderr='oracle failed')]
        for error in errors:
            for out in [self.base / 'fresh', self.out]:
                stderr = io.StringIO()
                with self.subTest(error=type(error).__name__, out=out), redirect_stderr(stderr), \
                        patch('pilotpack.score.check_reference', side_effect=error):
                    result = cli.main(['evaluate', '--run', str(self.run), '--out', str(out)])
                    self.assertEqual(result, 2)
                self.assertIn('REFERENCE_FAILURE', stderr.getvalue())
                self.assertNotIn('Traceback', stderr.getvalue())
                self.assertFalse((self.base / 'fresh').exists())
                self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})

    def test_threshold_failure_does_not_change_success_exit(self):
        protocol = json.loads((self.source / 'protocol.json').read_text())
        protocol['decision_criteria'] = {'b': {'max_provider_failure_rate': 0}}
        rows = [json.loads(line) for line in (self.source / 'outcomes.jsonl').read_text().splitlines()]
        rows[-1].update(terminal_status='provider_error', results=[], reported_hit_rank=None)
        write_rows(self.source / 'outcomes.jsonl', rows)
        write_json(self.source / 'protocol.json', protocol)
        rehash(self.source)
        self.freeze()
        result = self.command('evaluate', '--run', self.run, '--out', self.out)
        self.assertEqual(result.returncode, 0, result.stderr)
        verdict = json.loads((self.out / 'verdict.json').read_text())
        self.assertEqual(verdict['decisions']['b']['decision_status'], 'fails_criteria')

    def test_derived_report_mutations_reject_before_fresh_or_existing_publication(self):
        from report_mutations import mutations
        from support import tree_hash
        protocol = json.loads((self.source / 'protocol.json').read_text())
        protocol['requested_comparisons'] = [dict(arm_a='a', arm_b='b')]
        write_json(self.source / 'protocol.json', protocol)
        rehash(self.source)
        self.freeze()
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 3)
        self.assertEqual(self.command('report', '--run', self.run, '--evaluation', self.out / 'evaluation.json',
                                      '--out', self.out).returncode, 3)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        frozen = tree_hash(self.run)
        for label, value in mutations(json.loads(before['evaluation.json'])):
            path = self.base / 'mutated.json'
            write_json(path, value)
            for out in [self.base / 'fresh', self.out]:
                with self.subTest(mutation=label, existing=out == self.out):
                    result = self.command('report', '--run', self.run, '--evaluation', path, '--out', out)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn('INVALID_REPORT_INPUT', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertFalse((self.base / 'fresh').exists())
                    self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})
                    self.assertEqual(tree_hash(self.run), frozen)

    def test_report_exit_uses_verified_published_snapshot_when_input_is_replaced(self):
        # Timing fault injection only: real verification/scoring/publication all execute.
        from pilotpack import report
        protocol = json.loads((self.source / 'protocol.json').read_text())
        protocol['requested_comparisons'] = [dict(arm_a='a', arm_b='b')]
        write_json(self.source / 'protocol.json', protocol)
        rehash(self.source)
        self.freeze()
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 3)
        path = self.base / 'supplied.json'
        path.write_bytes((self.out / 'evaluation.json').read_bytes())
        publish = report._publish
        def replace_after_publication(*args, **kwargs):
            publish(*args, **kwargs)
            value = json.loads(path.read_text())
            value['pairs'] = []
            write_json(path, value)
        with patch('pilotpack.report._publish', side_effect=replace_after_publication):
            result = cli.main(['report', '--run', str(self.run), '--evaluation', str(path), '--out', str(self.out)])
        self.assertEqual(result, 3)
        self.assertEqual(json.loads((self.out / 'evaluation.json').read_text())['pairs'][0]['comparison_status'], 'blocked')

    def test_invalid_evaluation_json_has_structured_diagnostic_and_preserves_output(self):
        self.freeze()
        self.assertEqual(self.command('evaluate', '--run', self.run, '--out', self.out).returncode, 0)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        valid = (self.out / 'evaluation.json').read_text()
        for text in ['{', '{"pairs":[],"pairs":[]}', valid.replace('"schema_version": 1', '"schema_version": NaN'),
                     valid.replace('"schema_version": 1', '"schema_version": 1e999')]:
            path = self.base / 'bad.json'
            path.write_text(text)
            for out in (self.out, self.base / 'fresh'):
                with self.subTest(text=text[:30], existing=out == self.out):
                    p = self.command('report', '--run', self.run, '--evaluation', path, '--out', out)
                    self.assertEqual(p.returncode, 2)
                    self.assertIn('INVALID_REPORT_INPUT', p.stderr)
                    self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})
                    self.assertFalse((self.base / 'fresh').exists())

    def test_eligible_zero_cost_control_and_threshold_failure_publish_with_exit_zero(self):
        import shutil
        from support import apply_mutation
        shutil.rmtree(self.source)
        apply_mutation(ROOT / 'fixtures/controls/parent-v2', 'H05', self.source)
        protocol = json.loads((self.source / 'protocol.json').read_text())
        protocol['decision_criteria'] = {'a': {'max_provider_failure_rate': 0}}
        write_json(self.source / 'protocol.json', protocol)
        rehash(self.source)
        self.freeze()
        p = self.command('evaluate', '--run', self.run, '--out', self.out)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.command('report', '--run', self.run, '--evaluation', self.out / 'evaluation.json', '--out', self.out)
        self.assertEqual(p.returncode, 0, p.stderr)
        e = json.loads((self.out / 'evaluation.json').read_text())
        self.assertEqual(e['pairs'][0]['comparison_status'], 'eligible')
        self.assertEqual(e['arms']['a']['cost']['total'], '0')
        self.assertEqual(e['arms']['a']['cost']['support_status'], 'supported')
        self.assertEqual(e['decisions']['a']['decision_status'], 'fails_criteria')
