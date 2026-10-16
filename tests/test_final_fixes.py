"""Review regressions outside the frozen historical validation suites."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from pilotpack import compare, ingest, report, score
from pilotpack.schema import ValidationError, validate_packet
from reference.oracle import evaluate_run
from support import ROOT, apply_mutation, rehash, write_json, write_rows


class FinalFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = apply_mutation(ROOT / 'fixtures/controls/parent-v2', 'H05', self.base / 'input')

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def rows(self, name):
        return [json.loads(line) for line in (self.root / (name + '.jsonl')).read_text().splitlines()]

    def freeze(self):
        rehash(self.root)
        return ingest.freeze(self.root, adapter='canonical', config_path=ROOT / 'fixtures/config/canonical.json',
                             protocol_path=self.root / 'protocol.json', sources_path=self.root / 'sources.json',
                             out=self.base / 'run')

    def remove_dispatch(self, kind):
        outcomes = self.rows('outcomes')
        if kind == 'missing':
            outcomes = [row for row in outcomes if row['assignment_id'] != 'a:c1']
        else:
            row = next(row for row in outcomes if row['assignment_id'] == 'a:c1')
            row.update(observation_kind=kind, terminal_status='runner_failure' if kind == 'not_dispatched' else 'unknown',
                       selected_attempt_id=None, results=[], reported_hit_rank=None)
        write_rows(self.root / 'outcomes.jsonl', outcomes)
        attempts = [row for row in self.rows('attempts') if row['assignment_id'] != 'a:c1']
        # Retain a nonzero evidenced subtotal to distinguish unavailable total from lost costs.
        row = next(row for row in attempts if row['assignment_id'].startswith('a:'))
        row['cost']['amount'] = '0.25'
        sid = row['cost']['source_ref'].split('#')[0]
        sources = self.read('sources.json')
        source = next(source for source in sources['sources'] if source['source_id'] == sid)
        receipt = self.read(source['local_path'])
        receipt['amount'] = '0.25'
        write_json(self.root / source['local_path'], receipt)
        import hashlib
        source.update(bytes=(self.root / source['local_path']).stat().st_size,
                      sha256=hashlib.sha256((self.root / source['local_path']).read_bytes()).hexdigest())
        write_json(self.root / 'sources.json', sources)
        write_rows(self.root / 'attempts.jsonl', attempts)

    def test_missing_dispatch_product_cannot_claim_exact_requests_or_total_cost(self):
        self.remove_dispatch('missing')
        run = self.freeze()
        evaluation = compare.assess(ingest.verify_run(run), score.score_run(run))
        arm = evaluation['arms']['a']
        self.assertEqual(arm['unknown_reasons']['missing_record'], 1)
        self.assertEqual(arm['attempts']['observed_attempt_rows'], 3)
        self.assertEqual(arm['attempts']['physical_attempt_count_lower_bound'], 3)
        self.assertIsNone(arm['attempts']['physical_attempt_count_exact'])
        self.assertIsNone(arm['cost']['total'])
        self.assertFalse(arm['cost']['history_complete'])
        self.assertEqual(arm['cost']['known_subtotal'], '0.25')
        self.assertIn('UNKNOWN_ATTEMPT_HISTORY', [d['code'] for d in evaluation['diagnostics'] if d['scope'] == 'arm:a'])
        self.assertTrue(all(check['status'] != 'mismatch' for check in evaluation['reference_checks']))

    def test_missing_dispatch_oracle_independently_withholds_exact_requests(self):
        self.remove_dispatch('missing')
        got = evaluate_run(self.freeze())['arms']['a']
        self.assertEqual(got['unknown_subcounts']['missing_record'], 1)
        self.assertEqual(got['observed_attempt_rows'], 3)
        self.assertEqual(got['physical_attempt_count_lower_bound'], 3)
        self.assertIsNone(got['physical_attempt_count_exact'])

    def test_unobserved_dispatch_is_unknown_but_witnessed_non_dispatch_is_zero(self):
        for kind, exact in [('unobserved', None), ('not_dispatched', 3)]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                saved_root, saved_base = self.root, self.base
                self.base = Path(tmp)
                self.root = shutil.copytree(saved_root, self.base / 'input')
                try:
                    self.remove_dispatch(kind)
                    run = self.freeze()
                    evaluation = compare.assess(ingest.verify_run(run), score.score_run(run))
                    arm = evaluation['arms']['a']
                    self.assertEqual(arm['attempts']['physical_attempt_count_exact'], exact)
                    self.assertEqual(evaluate_run(run)['arms']['a']['physical_attempt_count_exact'], exact)
                    self.assertEqual(arm['cost']['total'], '0.25' if exact is not None else None)
                    self.assertEqual(arm['cost']['known_subtotal'], '0.25')
                finally:
                    self.root, self.base = saved_root, saved_base

    def test_assignment_settings_cannot_select_another_arm_for_either_basis(self):
        manifest, protocol = self.read('packet.json'), self.read('protocol.json')
        manifest['actual_settings']['b']['mode'] = protocol['arms']['b']['mode'] = 'pro'
        rows = self.rows('assignments')
        rows[0]['settings_id'] = 'b'
        write_rows(self.root / 'assignments.jsonl', rows)
        for basis in ['reconstructed', 'predeclared']:
            manifest['assignment_basis'] = protocol['assignment_basis'] = basis
            write_json(self.root / 'packet.json', manifest)
            write_json(self.root / 'protocol.json', protocol)
            rehash(self.root)
            with self.subTest(basis=basis):
                with self.assertRaises(ValidationError) as caught:
                    validate_packet(self.root)
                self.assertEqual(caught.exception.diagnostics[0]['code'], 'ASSIGNMENT_SETTINGS_MISMATCH')

    def unsupported_profile(self, location):
        manifest, protocol = self.read('packet.json'), self.read('protocol.json')
        if location == 'protocol':
            protocol['matching_profile'] = 'unsupported-exact-doi-only'
        elif location == 'declared':
            protocol['arms']['a']['matching_profile'] = 'unsupported-exact-doi-only'
        elif location == 'actual':
            manifest['actual_settings']['a']['matching_profile'] = 'unsupported-exact-doi-only'
        write_json(self.root / 'packet.json', manifest)
        write_json(self.root / 'protocol.json', protocol)
        rehash(self.root)

    def test_unsupported_profiles_rejected_at_every_declaration(self):
        for location in ['protocol', 'declared', 'actual']:
            original = {name: (self.root / name).read_bytes() for name in ['packet.json', 'protocol.json']}
            self.unsupported_profile(location)
            with self.subTest(location=location):
                with self.assertRaises(ValidationError) as caught:
                    validate_packet(self.root)
                self.assertEqual(caught.exception.diagnostics[0]['code'], 'UNSUPPORTED_MATCHING_PROFILE')
            for name, value in original.items():
                (self.root / name).write_bytes(value)

    def test_oracle_rejects_unsupported_profiles_independently(self):
        for location in ['protocol', 'declared', 'actual']:
            original = {name: (self.root / name).read_bytes() for name in ['packet.json', 'protocol.json']}
            self.unsupported_profile(location)
            with self.subTest(location=location), self.assertRaisesRegex(ValueError, 'unsupported matching profile'):
                evaluate_run(self.root)
            for name, value in original.items():
                (self.root / name).write_bytes(value)

    def test_both_supported_profile_identifiers_retain_literal_matching(self):
        for profile in ['literal-v1', 'needle-scholar-73c7f810']:
            manifest, protocol = self.read('packet.json'), self.read('protocol.json')
            protocol['matching_profile'] = profile
            for arm in ['a', 'b']:
                manifest['actual_settings'][arm]['matching_profile'] = protocol['arms'][arm]['matching_profile'] = profile
            write_json(self.root / 'packet.json', manifest)
            write_json(self.root / 'protocol.json', protocol)
            rehash(self.root)
            with self.subTest(profile=profile):
                validate_packet(self.root)
                self.assertEqual(evaluate_run(self.root)['arms']['a']['H'], 2)

    def test_oracle_legacy_export_still_rejects_explicit_unsupported_profile(self):
        self.unsupported_profile('actual')
        manifest = self.read('packet.json')
        manifest.pop('protocol_sha256')
        manifest.pop('hashes')
        write_json(self.root / 'packet.json', manifest)
        (self.root / 'protocol.json').unlink()
        with self.assertRaisesRegex(ValueError, 'unsupported matching profile'):
            evaluate_run(self.root)

    def test_oracle_cannot_downgrade_missing_declared_protocol_to_legacy(self):
        run = self.freeze()
        (run / 'protocol.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing declared protocol'):
            evaluate_run(run)

    def test_report_rejects_inconsistent_rate_and_bounds_and_preserves_output(self):
        run = self.freeze()
        evaluation = compare.assess(ingest.verify_run(run), score.score_run(run))
        out = self.base / 'output'
        report.write_json_artifacts(out, evaluation=evaluation, verdict=compare.build_verdict(evaluation))
        report.write_report(run, out / 'evaluation.json', out)
        before = {path.name: path.read_bytes() for path in out.iterdir()}
        for changes in [dict(delivered_hit_at_k=1.0), dict(missingness_range=[1.0, 1.0]),
                        dict(delivered_hit_at_k=None), dict(missingness_range=None)]:
            bad = copy.deepcopy(evaluation)
            bad['arms']['a'].update(changes)
            path = self.base / 'inconsistent.json'
            write_json(path, bad)
            with self.subTest(changes=changes):
                with patch('pilotpack.score.score_run', side_effect=AssertionError('no rescoring')):
                    with self.assertRaises(ValidationError):
                        report.write_report(run, path, out)
                self.assertEqual(before, {path.name: path.read_bytes() for path in out.iterdir()})

    def test_report_requires_null_metrics_for_zero_or_unknown_denominator(self):
        run = self.freeze()
        evaluation = compare.assess(ingest.verify_run(run), score.score_run(run))
        for n in [0, None]:
            empty = copy.deepcopy(evaluation)
            empty['cases'] = [case for case in empty['cases'] if case['arm_id'] != 'a']
            empty['arms']['a'].update(N=n, H=0, M=0, F=0, U=0,
                                      delivered_hit_at_k=None, missingness_range=None)
            with self.subTest(n=n):
                report._validate(empty, compare.build_verdict(empty))
            for changes in [dict(delivered_hit_at_k=0.0), dict(missingness_range=[0.0, 0.0])]:
                bad = copy.deepcopy(empty)
                bad['arms']['a'].update(changes)
                with self.subTest(n=n, changes=changes), self.assertRaises(ValidationError):
                    report._validate(bad, compare.build_verdict(bad))

    def test_criteria_extensions_are_descriptive_and_do_not_become_thresholds(self):
        protocol = self.read('protocol.json')
        protocol['decision_criteria'] = {'a': {'extensions': {'note': 'annotation'}},
                                       'b': {'min_delivered_hit_rate': .5, 'max_provider_failure_rate': .25,
                                             'max_unknown_rate': 0, 'extensions': {'note': 'annotation'}}}
        write_json(self.root / 'protocol.json', protocol)
        run = self.freeze()
        evaluation = compare.assess(ingest.verify_run(run), score.score_run(run))
        self.assertEqual(evaluation['decisions']['a']['decision_status'], 'descriptive_only')
        self.assertEqual(evaluation['decisions']['a']['criteria'], {})
        self.assertEqual(evaluation['decisions']['b']['decision_status'], 'meets_criteria')
        self.assertEqual(len(evaluation['decisions']['b']['reasons']), 3)
        self.assertEqual(ingest.verify_run(run).protocol['decision_criteria']['a']['extensions']['note'], 'annotation')
