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

    def test_review_comparison_ids_require_strings_before_lookup(self):
        for field, value in [('arm_a', []), ('arm_b', {}), ('arm_a', '')]:
            with self.subTest(field=field, value=value):
                pair = dict(arm_a='a', arm_b='b')
                pair[field] = value
                self.mutate('protocol.json', lambda x: x.update(requested_comparisons=[pair]))
                self.rejects('INVALID_SCHEMA', 'protocol.json:$.requested_comparisons[0].' + field)

    def test_review_transformation_parents_require_strings_before_lookup(self):
        for value in [{}, [], '']:
            with self.subTest(value=value):
                self.mutate('sources.json', lambda x: x['sources'][0].update(parents=[value]))
                self.rejects('INVALID_SCHEMA', 'sources.json:$.sources[0].parents[0]')

    def test_review_valid_unknown_parent_retains_orphan_diagnostic(self):
        self.mutate('sources.json', lambda x: x['sources'][0].update(parents=['unknown']))
        self.rejects('ORPHAN_RECORD', 'sources.json')

    def test_review_limitations_are_lists_wherever_accepted(self):
        cases = [
            ('sources.json', lambda x: x['sources'][0].update(limitations='not-a-list'), '.sources[0].limitations'),
            ('protocol.json', lambda x: x.update(limitations={'x': 1}), '.limitations'),
            ('protocol.json', lambda x: x['arms']['a'].update(limitations={'x': 1}), '.arms.a.limitations'),
            ('packet.json', lambda x: x['actual_settings']['a'].update(limitations={'x': 1}), '.actual_settings.a.limitations'),
        ]
        for file, change, location in cases:
            with self.subTest(file=file, location=location):
                original = json.loads((self.root / file).read_text())
                self.mutate(file, change)
                try:
                    self.rejects('INVALID_SCHEMA', file + ':$' + location)
                finally:
                    write_json(self.root / file, original)
                    rehash(self.root)

    def test_review_settings_source_refs_require_reference_lists(self):
        for value in [42, {}, [''], ['src'], [False]]:
            with self.subTest(value=value):
                self.mutate('protocol.json', lambda x: x['arms']['a'].update(source_refs=value))
                self.rejects('INVALID_SCHEMA', 'protocol.json:$.arms.a.source_refs')

    def test_review_protocol_status_requires_nonempty_string(self):
        self.mutate('protocol.json', lambda x: x.update(status=[]))
        self.rejects('INVALID_SCHEMA', 'protocol.json:$.status')

    def test_review_optional_packet_metadata_has_declared_types(self):
        base = dict(archive_run_id='control', source_sha256={}, cohort_selector='all')
        for field, value in [('excluded_task_manifest', []), ('supported_task_count', True),
                             ('supported_source_group_count', '2'), ('protected', 1),
                             ('outcomes_inspected', []), ('comparison_window', [])]:
            with self.subTest(field=field):
                packet = dict(base, **{field: value})
                self.mutate('protocol.json', lambda x: x.update(packets={'control': packet}))
                self.rejects('INVALID_SCHEMA', 'protocol.json:$.packets.control.' + field)

    def test_review_valid_optional_evidence_keeps_unknown_archive_fields(self):
        self.mutate('protocol.json', lambda x: x.update(status='acquired', limitations=['UNKNOWN_ACTUAL_SETTINGS']))
        self.mutate('protocol.json', lambda x: x['arms']['a'].update(
                    limitations=['UNKNOWN_ACTUAL_SETTINGS'], source_refs=['src#$']))
        self.mutate('packet.json', lambda x: x['actual_settings']['a'].update(
                    limitations=['UNKNOWN_ACTUAL_SETTINGS'], source_refs=['src#$']))
        packet = validate_packet(self.root)
        self.assertIsNone(packet.sources[0]['revision'])
        self.assertIn('NO_IMMUTABLE_REVISION', packet.sources[0]['limitations'])
        self.assertIsNone(packet.manifest['actual_settings']['a']['endpoint'])

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


class JsonlPhysicalLineTests(unittest.TestCase):
    def test_literal_unicode_separators_are_inside_one_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'unicode.jsonl'
            row = {'text': 'left\u2028middle\u0085right'}
            path.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
            self.assertEqual(load_jsonl(path), (row,))

    def test_physical_lf_crlf_empty_and_optional_final_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'physical.jsonl'
            for raw, expected in [(b'', ()), (b'{}', ({},)), (b'{}\n', ({},)),
                                  (b'{}\r\n{}\r\n', ({}, {}))]:
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    self.assertEqual(load_jsonl(path), expected)
            for raw, line in [(b'\n', 1), (b'{}\n\n', 2), (b'{}\n \n', 2)]:
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(ValidationError) as caught:
                        load_jsonl(path)
                    self.assertEqual(caught.exception.diagnostics[0]['code'], 'INVALID_JSON')
                    self.assertIn(f':{line}:$', caught.exception.diagnostics[0]['scope'])
