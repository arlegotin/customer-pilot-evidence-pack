"""Strict input contracts: identity, corruption and explicit evidence gaps."""
import json
from pathlib import Path
import tempfile
import unittest

from support import make_packet, rehash, write_json, write_rows
from pilotpack.schema import Packet, ValidationError, load_json, load_jsonl, validate_packet


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.root = make_packet(self.tmp)

    def mutate(self, file, change):
        path = self.root / file
        if file.endswith('.jsonl'):
            rows = [json.loads(x) for x in path.read_text().splitlines()]
            change(rows)
            write_rows(path, rows)
        else:
            value = json.loads(path.read_text())
            change(value)
            write_json(path, value)
        rehash(self.root)

    def rejects(self, code, file):
        with self.assertRaises(ValidationError) as caught:
            validate_packet(self.root)
        diag = caught.exception.diagnostics[0]
        self.assertEqual(diag['code'], code)
        self.assertIn(file, diag['message'])
        self.assertTrue(':' in diag['message'] or '$' in diag['message'])

    def test_same_text_remains_two_tasks_and_four_assignments(self):
        packet = validate_packet(self.root)
        self.assertIsInstance(packet, Packet)
        self.assertEqual(len(packet.tasks), 2)
        self.assertEqual(len(packet.assignments), 4)
        self.assertEqual(packet.protocol['decision_criteria'], {})
        self.assertEqual(packet.protocol['arms']['a']['snippet_chars'], 0)
        self.assertTrue(any(d['code'] == 'UNKNOWN_ATTEMPT_HISTORY' for d in packet.diagnostics))

    def test_json_ambiguity_is_invalid_json(self):
        for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '[]']:
            with self.subTest(raw=raw):
                path = self.tmp / 'bad.json'
                path.write_text(raw)
                with self.assertRaises(ValidationError) as caught:
                    load_json(path)
                self.assertEqual(caught.exception.diagnostics[0]['code'], 'INVALID_JSON')
                self.assertIn('bad.json', str(caught.exception))

    def test_jsonl_blank_line_has_line_diagnostic(self):
        path = self.tmp / 'bad.jsonl'
        path.write_text('{}\n\n')
        with self.assertRaises(ValidationError) as caught:
            load_jsonl(path)
        self.assertIn(':2', str(caught.exception))
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'INVALID_JSON')

    def test_unknown_core_rejected_extensions_accepted(self):
        self.mutate('tasks.jsonl', lambda x: x[0].update(extensions={'anything': 1}))
        validate_packet(self.root)
        self.mutate('tasks.jsonl', lambda x: x[0].update(typo=True))
        self.rejects('INVALID_SCHEMA', 'tasks.jsonl')

    def test_required_ids_and_source_references(self):
        self.mutate('tasks.jsonl', lambda x: x[0].pop('task_id'))
        self.rejects('INVALID_SCHEMA', 'tasks.jsonl')

    def test_missing_source_reference(self):
        self.mutate('tasks.jsonl', lambda x: x[0].pop('source_ref'))
        self.rejects('INVALID_SCHEMA', 'tasks.jsonl')

    def test_invalid_outcome_identity_type(self):
        self.mutate('outcomes.jsonl', lambda x: x[0].update(assignment_id=[]))
        self.rejects('INVALID_SCHEMA', 'outcomes.jsonl')

    def test_invalid_attempt_assignment_type(self):
        self.mutate('attempts.jsonl', lambda x: x[0].update(assignment_id=[]))
        self.rejects('INVALID_SCHEMA', 'attempts.jsonl')

    def test_unknown_source(self):
        self.mutate('tasks.jsonl', lambda x: x[0].update(source_ref='absent#line=1'))
        self.rejects('ORPHAN_RECORD', 'tasks.jsonl')

    def test_orphan_assignment(self):
        self.mutate('assignments.jsonl', lambda x: x[0].update(task_id='absent'))
        self.rejects('ORPHAN_RECORD', 'assignments.jsonl')

    def test_duplicate_logical_assignment(self):
        self.mutate('assignments.jsonl', lambda x: x.append(dict(x[0], assignment_id='other')))
        self.rejects('DUPLICATE_ASSIGNMENT', 'assignments.jsonl')

    def test_result_rank_order(self):
        self.mutate('outcomes.jsonl', lambda x: x[0]['results'][0].update(rank=2))
        self.rejects('INVALID_SCHEMA', 'outcomes.jsonl')

    def test_invalid_k_and_thresholds(self):
        for value in [0, 3, True]:
            with self.subTest(k=value):
                self.mutate('protocol.json', lambda x: x['arms']['a'].update(k=value))
                self.rejects('INVALID_SCHEMA', 'protocol.json')
        self.mutate('protocol.json', lambda x: x['arms']['a'].update(k=2))
        self.mutate('protocol.json', lambda x: x.update(decision_criteria={'unknown': {}}))
        self.rejects('INVALID_SCHEMA', 'protocol.json')
        for value in [-0.1, 1.1, True, '0.5']:
            self.mutate('protocol.json', lambda x: x.update(decision_criteria={'a': {'min_delivered_hit_rate': value}}))
            self.rejects('INVALID_SCHEMA', 'protocol.json')

    def test_nullable_and_boundary_thresholds(self):
        self.mutate('protocol.json', lambda x: x.update(decision_criteria={'a': {
            'min_delivered_hit_rate': 0, 'max_provider_failure_rate': 1, 'max_unknown_rate': None}}))
        validate_packet(self.root)

    def test_negative_latency(self):
        self.mutate('attempts.jsonl', lambda x: x[0].update(latency_ms=-1))
        self.rejects('INVALID_SCHEMA', 'attempts.jsonl')

    def test_negative_cost(self):
        self.mutate('attempts.jsonl', lambda x: x[0]['cost'].update(amount='-1'))
        self.rejects('INVALID_SCHEMA', 'attempts.jsonl')

    def test_observed_zero_requires_amount_currency_and_request_evidence(self):
        packet = validate_packet(self.root)
        self.assertEqual(packet.attempts[0]['cost']['amount'], '0')
        self.mutate('attempts.jsonl', lambda x: x[0]['cost'].update(source_ref='src#line=1'))
        self.rejects('INVALID_COST_PROVENANCE', 'attempts.jsonl')

    def test_timestamps_require_zone_and_nonnegative_duration(self):
        self.mutate('attempts.jsonl', lambda x: x[0].update(started_at='2026-10-16T01:00:00'))
        self.rejects('INVALID_SCHEMA', 'attempts.jsonl')
        self.mutate('attempts.jsonl', lambda x: x[0].update(started_at='2026-10-16T01:00:01Z'))
        self.rejects('INVALID_SCHEMA', 'attempts.jsonl')

    def test_missing_source_id_is_structural(self):
        self.mutate('sources.json', lambda x: x['sources'][0].pop('source_id'))
        self.rejects('INVALID_SCHEMA', 'sources.json')

    def test_null_results_is_structural(self):
        self.mutate('outcomes.jsonl', lambda x: x[0].update(results=None))
        self.rejects('INVALID_SCHEMA', 'outcomes.jsonl')

    def test_source_symlink_escape(self):
        outside = self.tmp / 'outside.json'
        outside.write_text('{}')
        source = self.root / 'raw/evidence.json'
        source.unlink()
        source.symlink_to(outside)
        self.rejects('UNSAFE_SOURCE_PATH', 'sources.json')

    def test_hash_mismatch(self):
        with (self.root / 'raw/evidence.json').open('a') as stream:
            stream.write(' ')
        self.rejects('HASH_MISMATCH', 'sources.json')

    def test_new_run_manifest_after_dispatch(self):
        self.mutate('packet.json', lambda x: x.update(origin='new_run',
                    assignment_manifest_frozen_at='2026-10-16T01:01:00Z',
                    assignment_manifest_sha256=x['hashes']['assignments.jsonl']))
        self.rejects('MANIFEST_AFTER_DISPATCH', 'packet.json')

    def test_present_nullable_settings_do_not_become_defaults(self):
        self.mutate('protocol.json', lambda x: x['arms']['a'].update(snippet_chars=None))
        self.mutate('packet.json', lambda x: x['actual_settings']['a'].update(snippet_chars=None))
        packet = validate_packet(self.root)
        self.assertIsNone(packet.protocol['arms']['a']['snippet_chars'])
        self.assertTrue(any(d['code'] == 'UNKNOWN_ACTUAL_SETTINGS' for d in packet.diagnostics))

    def test_missing_measurements_require_limitation(self):
        self.mutate('attempts.jsonl', lambda x: x[0].update(latency_ms=None))
        self.rejects('INVALID_SCHEMA', 'attempts.jsonl')

    def test_cost_provenance_identifies_physical_request(self):
        self.mutate('attempts.jsonl', lambda x: x[0].update(attempt_id='different-request'))
        self.rejects('INVALID_COST_PROVENANCE', 'attempts.jsonl')

    def test_observed_cost_without_source_is_cost_provenance_fault(self):
        self.mutate('attempts.jsonl', lambda x: x[0]['cost'].update(source_ref=None))
        self.rejects('INVALID_COST_PROVENANCE', 'attempts.jsonl')

    def test_archive_unknown_measurements_with_explicit_limitations(self):
        def incomplete(rows):
            rows[0].update(started_at=None, ended_at=None, latency_ms=None,
                           cost=dict(amount=None, currency=None, kind='missing', source_ref=None, scope='attempt'),
                           limitations=['MISSING_REQUEST_MEASUREMENTS'])
        self.mutate('attempts.jsonl', incomplete)
        packet = validate_packet(self.root)
        self.assertIsNone(packet.attempts[0]['latency_ms'])
        self.assertEqual(packet.attempts[0]['cost']['kind'], 'missing')

    def test_checked_in_acquisition_protocol_nulls_are_valid(self):
        from support import ROOT
        policy = json.loads((ROOT / 'protocol.json').read_text())
        write_json(self.root / 'protocol.json', policy)
        for name in ('tasks', 'assignments', 'outcomes', 'attempts'):
            write_rows(self.root / (name + '.jsonl'), [])
        manifest = json.loads((self.root / 'packet.json').read_text())
        manifest.update(actual_settings=policy['arms'], intended_count={a: 0 for a in policy['arms']},
                        attempt_history={a: 'unknown' for a in policy['arms']})
        write_json(self.root / 'packet.json', manifest)
        rehash(self.root)
        packet = validate_packet(self.root)
        self.assertIsNone(packet.protocol['arms']['bing']['retry_policy'])
        self.assertEqual(packet.protocol['decision_criteria'], {})

    def test_orphan_outcome(self):
        self.mutate('outcomes.jsonl', lambda x: x[0].update(assignment_id='absent'))
        self.rejects('ORPHAN_RECORD', 'outcomes.jsonl')

    def test_orphan_attempt(self):
        self.mutate('attempts.jsonl', lambda x: x[0].update(assignment_id='absent'))
        self.rejects('ORPHAN_RECORD', 'attempts.jsonl')

    def test_unsupported_version(self):
        self.mutate('packet.json', lambda x: x.update(schema_version=2))
        self.rejects('UNSUPPORTED_VERSION', 'packet.json')

    def test_source_path_traversal(self):
        self.mutate('sources.json', lambda x: x['sources'][0].update(local_path='../escape'))
        self.rejects('UNSAFE_SOURCE_PATH', 'sources.json')

    def test_missing_outcome_survives_as_explicit_block(self):
        self.mutate('outcomes.jsonl', lambda x: x.pop())
        packet = validate_packet(self.root)
        self.assertTrue(any(d['code'] == 'MISSING_OUTCOME' and d['severity'] == 'block' for d in packet.diagnostics))
