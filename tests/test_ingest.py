"""Freeze contracts: identity, retained evidence, reconciliation and atomic publication."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pilotpack import ingest
from pilotpack.schema import ValidationError
from reference.prepare_packet import prepare_run
from support import ROOT, make_packet, rehash, write_json, write_rows


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def freeze_canonical(self, source=None, out=None):
        source = source or make_packet(self.base)
        config = self.base / 'config.json'
        write_json(config, {'adapter_profile': 'canonical-v1'})
        return ingest.freeze(source, adapter='canonical', config_path=config,
                             protocol_path=source / 'protocol.json', sources_path=source / 'sources.json',
                             out=out or self.base / 'run')

    def freeze_a(self, out=None):
        return ingest.freeze(ROOT / 'fixtures/real/packet-a', adapter='needle-scholar',
                             config_path=ROOT / 'fixtures/config/packet-a.json', protocol_path=ROOT / 'protocol.json',
                             sources_path=ROOT / 'sources.json', out=out or self.base / 'run')

    def fault(self, code, action):
        with self.assertRaises(ValidationError) as cm:
            action()
        self.assertIn(code, [d['code'] for d in cm.exception.diagnostics])

    def test_canonical_keeps_equal_text_distinct_ids_and_attempts(self):
        run = self.freeze_canonical()
        packet = ingest.verify_run(run)
        self.assertEqual([r['task_id'] for r in packet.tasks], ['t1', 't2'])
        self.assertEqual(len(packet.assignments), 4)
        self.assertEqual(len(packet.attempts), 1)
        self.assertEqual(len({t['query_text'] for t in packet.tasks}), 1)

    def test_logical_only_does_not_create_attempts(self):
        source = make_packet(self.base)
        write_rows(source / 'attempts.jsonl', [])
        rows = [json.loads(x) for x in (source / 'outcomes.jsonl').read_text().splitlines()]
        for row in rows:
            row['selected_attempt_id'] = None
            row['observation_kind'] = 'archive_logical'
        write_rows(source / 'outcomes.jsonl', rows)
        manifest = json.loads((source / 'packet.json').read_text())
        manifest['attempt_history'] = {'a': 'unknown', 'b': 'unknown'}
        write_json(source / 'packet.json', manifest)
        rehash(source)
        packet = ingest.verify_run(self.freeze_canonical(source))
        self.assertEqual(packet.attempts, ())
        self.assertEqual(packet.manifest['attempt_history']['a'], 'unknown')

    def test_missing_intended_outcome_is_explicit_reconciliation(self):
        source = make_packet(self.base)
        lines = (source / 'outcomes.jsonl').read_text().splitlines()
        (source / 'outcomes.jsonl').write_text('\n'.join(lines[1:]) + '\n')
        rehash(source)
        packet = ingest.verify_run(self.freeze_canonical(source))
        row = next(r for r in packet.outcomes if r['assignment_id'] == 'a:t1')
        self.assertEqual(row['terminal_status'], 'unknown')
        self.assertEqual(row['observation_kind'], 'unobserved')
        self.assertIsNone(row['selected_attempt_id'])
        self.assertIn('MISSING_OUTCOME', row['limitations'])
        self.assertTrue(row['source_ref'].startswith('normalization-reconciliation#'))

    def test_canonical_identity_is_stable_under_record_reordering(self):
        source = make_packet(self.base)
        first = self.freeze_canonical(source, self.base / 'one')
        for name in ('tasks', 'assignments', 'outcomes', 'attempts'):
            path = source / (name + '.jsonl')
            write_rows(path, list(reversed([json.loads(x) for x in path.read_text().splitlines()])))
        rehash(source)
        second = self.freeze_canonical(source, self.base / 'two')
        a, b = ingest.verify_run(first), ingest.verify_run(second)
        self.assertEqual(a.manifest['content_id'], b.manifest['content_id'])
        self.assertEqual(a.manifest['normalized_table_digest'], b.manifest['normalized_table_digest'])

    def test_existing_destination_and_interrupted_staging(self):
        source = make_packet(self.base)
        out = self.base / 'run'
        out.mkdir()
        (out / 'keep').write_text('unchanged')
        with self.assertRaises(FileExistsError):
            self.freeze_canonical(source, out)
        self.assertEqual((out / 'keep').read_text(), 'unchanged')
        shutil.rmtree(out)
        with patch('pilotpack.ingest.create_ledger', side_effect=OSError('interruption')):
            with self.assertRaises(OSError):
                self.freeze_canonical(source, out)
        self.assertFalse(out.exists())
        self.assertEqual(list(self.base.glob('.run.staging-*')), [])

    def test_invalid_raw_bytes_and_unsafe_paths(self):
        source = make_packet(self.base)
        (source / 'raw/evidence.json').write_text('{}')
        self.fault('HASH_MISMATCH', lambda: self.freeze_canonical(source))
        shutil.rmtree(source)
        source = make_packet(self.base)
        inventory = json.loads((source / 'sources.json').read_text())
        inventory['sources'][0]['local_path'] = '../escape'
        write_json(source / 'sources.json', inventory)
        rehash(source)
        self.fault('UNSAFE_SOURCE_PATH', lambda: self.freeze_canonical(source))

    def test_escaping_symlink(self):
        source = make_packet(self.base)
        original = source / 'raw/evidence.json'
        outside = self.base / 'outside.json'
        outside.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(outside)
        self.fault('UNSAFE_SOURCE_PATH', lambda: self.freeze_canonical(source))

    def test_source_fragments_resolve_against_retained_bytes(self):
        for fragment in ('line=2', '$.missing', '$[1]', '$.request[999]'):
            with self.subTest(fragment=fragment):
                place = self.base / str(len(list(self.base.iterdir())))
                place.mkdir()
                source = make_packet(place)
                rows = [json.loads(x) for x in (source / 'tasks.jsonl').read_text().splitlines()]
                rows[0]['source_ref'] = 'src#' + fragment
                write_rows(source / 'tasks.jsonl', rows)
                rehash(source)
                self.fault('INVALID_SOURCE_REF', lambda: self.freeze_canonical(source))

    def test_manifest_only_edit_is_detected_and_verify_does_not_write(self):
        run = self.freeze_canonical()
        before = {str(p.relative_to(run)): (p.read_bytes(), p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
        ingest.verify_run(run)
        after = {str(p.relative_to(run)): (p.read_bytes(), p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        for field, value in [('origin', 'new_run'), ('intended_count', {'a': 200, 'b': 2}),
                             ('actual_settings', {**json.loads(before['packet.json'][0])['actual_settings'],
                                                  'a': {**json.loads(before['packet.json'][0])['actual_settings']['a'], 'mode': 'invented'}})]:
            manifest = json.loads(before['packet.json'][0])
            manifest[field] = value
            write_json(run / 'packet.json', manifest)
            self.fault('MANIFEST_INTEGRITY_MISMATCH', lambda: ingest.verify_run(run))
        (run / 'packet.json').write_bytes(before['packet.json'][0])

    def test_new_run_manifest_timestamp_must_precede_dispatch(self):
        source = make_packet(self.base)
        manifest = json.loads((source / 'packet.json').read_text())
        manifest.update(origin='new_run', assignment_manifest_frozen_at='2027-01-02T00:00:00Z',
                        assignment_manifest_sha256=manifest['hashes']['assignments.jsonl'])
        write_json(source / 'packet.json', manifest)
        rehash(source)
        self.fault('MANIFEST_AFTER_DISPATCH', lambda: self.freeze_canonical(source))

    def test_duplicate_and_orphan_canonical_rows(self):
        source = make_packet(self.base)
        path = source / 'tasks.jsonl'
        original = path.read_text()
        path.write_text(original + original.splitlines()[0] + '\n')
        rehash(source)
        self.fault('DUPLICATE_RECORD', lambda: self.freeze_canonical(source))
        path.write_text(original)
        rows = [json.loads(x) for x in (source / 'assignments.jsonl').read_text().splitlines()]
        rows[0]['task_id'] = 'absent'
        write_rows(source / 'assignments.jsonl', rows)
        rehash(source)
        self.fault('ORPHAN_RECORD', lambda: self.freeze_canonical(source))

    def test_packet_a_matches_independent_export_and_twenty_examples(self):
        run = self.freeze_a()
        packet = ingest.verify_run(run)
        baseline = self.base / 'reference'
        prepare_run(ROOT / 'fixtures/real/packet-a', ROOT / 'fixtures/config/packet-a.json', baseline)
        for name in ('tasks', 'assignments', 'outcomes', 'attempts'):
            self.assertEqual((run / (name + '.jsonl')).read_bytes(), (baseline / (name + '.jsonl')).read_bytes(), name)
        expected = json.loads((ROOT / 'fixtures/expected/packet-a.json').read_text())['examples']
        outcomes = {r['assignment_id']: r for r in packet.outcomes}
        for example in expected:
            row = outcomes[example['arm_id'] + ':' + example['task_id']]
            self.assertEqual(row['reported_hit_rank'], example['expected_first_hit_rank'])
            self.assertEqual(len(row['results']), example['expected_result_count'])
            self.assertEqual(row['terminal_status'], 'provider_error' if example['expected_partition'] == 'F' else 'completed')
        self.assertEqual((len(packet.tasks), len(packet.assignments), len(packet.outcomes)), (324, 972, 972))
        self.assertEqual(len({r['source_group_id'] for r in packet.tasks}), 81)
        self.assertEqual(packet.attempts, ())
        self.assertEqual(packet.manifest['intended_count'], dict.fromkeys(('bing', 'keenable', 'perplexity'), 324))
        self.assertFalse(any(r['arm_id'] == 'ultimate' for r in packet.assignments))
        self.assertEqual(packet.manifest['extensions']['baseline_source_ids'], {'native': 'baseline-native', 'oracle': 'baseline-oracle', 'check': 'baseline-check'})
        sources = {s['source_id']: s for s in packet.sources}
        self.assertFalse(any('packet-b' in sid for sid in sources))
        for sid in ('baseline-native', 'baseline-oracle', 'baseline-check', 'needle-source', 'metadata-packet-a-inventory.json'):
            self.assertIn(sid, sources)
        registry = json.loads((ROOT / 'sources.json').read_text())['sources']
        for source in registry:
            if source['source_id'] in sources:
                self.assertEqual(hashlib.sha256((run / sources[source['source_id']]['local_path']).read_bytes()).hexdigest(), source['sha256'])
        summary = json.loads((run / sources['packet-a-summary']['local_path']).read_text())
        self.assertIn('ultimate', summary['engines'])
        exclusions = json.loads((run / 'raw/exclusions.json').read_text())
        self.assertEqual(exclusions['excluded_tasks'], json.loads((ROOT / 'fixtures/expected/packet-a-exclusions.json').read_text())['excluded_tasks'])
        for settings in packet.manifest['actual_settings'].values():
            for key in ('mode', 'endpoint', 'query_parameters', 'retry_policy', 'timeout_s', 'concurrency', 'run_window'):
                self.assertIsNone(settings[key])
        proc = subprocess.run([sys.executable, '-c', 'from pathlib import Path; from pilotpack.ingest import verify_run; import sys; print(len(verify_run(Path(sys.argv[1])).tasks))', str(run)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), '324')

    def test_archive_reconstruction_requires_versioned_authoritative_gold(self):
        config = json.loads((ROOT / 'fixtures/config/packet-a.json').read_text())
        config['assignment_evidence'] = None
        self.fault('UNRECONSTRUCTABLE_ASSIGNMENTS', lambda: ingest.import_needle_scholar(ROOT / 'fixtures/real/packet-a', config))

    def test_archive_full_join_missing_and_duplicate_rows(self):
        source = self.base / 'archive'
        shutil.copytree(ROOT / 'fixtures/real/packet-a', source)
        config = json.loads((ROOT / 'fixtures/config/packet-a.json').read_text())
        config['_context'] = {'protocol': json.loads((ROOT / 'protocol.json').read_text()), 'source_root': str(ROOT)}
        registry = json.loads((ROOT / 'sources.json').read_text())
        config['_context']['sources'] = registry
        engine_path = source / 'scholar/bing.json'
        engine = json.loads(engine_path.read_text())
        first = engine['per_query'].pop(0)
        write_json(engine_path, engine)
        # A changed archive needs an explicit new acquisition inventory and protocol hash.
        for row in registry['sources']:
            if row['source_id'] == 'packet-a-bing':
                row.update(sha256=hashlib.sha256(engine_path.read_bytes()).hexdigest(), bytes=engine_path.stat().st_size)
                config['_context']['protocol']['packets']['packet-a']['source_sha256']['packet-a-bing'] = row['sha256']
        packet = ingest.import_needle_scholar(source, config)
        missing = next(r for r in packet.outcomes if r['assignment_id'] == 'bing:d342a579431d638b_2026-10-14T12')
        self.assertEqual(missing['terminal_status'], 'unknown')
        engine['per_query'].extend([first, first])
        write_json(engine_path, engine)
        for row in registry['sources']:
            if row['source_id'] == 'packet-a-bing':
                row.update(sha256=hashlib.sha256(engine_path.read_bytes()).hexdigest(), bytes=engine_path.stat().st_size)
                config['_context']['protocol']['packets']['packet-a']['source_sha256']['packet-a-bing'] = row['sha256']
        self.fault('DUPLICATE_RECORD', lambda: ingest.import_needle_scholar(source, config))

    def test_unsupported_conversion_cohort_is_rejected(self):
        config = json.loads((ROOT / 'fixtures/config/packet-a.json').read_text())
        config['gold_namespace_required'] = 'pmid'
        self.fault('MISSING_MATCH_EVIDENCE', lambda: ingest.import_needle_scholar(ROOT / 'fixtures/real/packet-a', config))

    def test_atomic_publication_refuses_destination_created_at_reservation(self):
        source = make_packet(self.base)
        out = self.base / 'run'
        original = Path.mkdir
        def racing_mkdir(path, *args, **kwargs):
            if path == out:
                original(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', racing_mkdir):
            with self.assertRaises(FileExistsError):
                self.freeze_canonical(source, out)
        self.assertTrue(out.is_dir())
        self.assertEqual(list(out.iterdir()), [])
        self.assertEqual(list(self.base.glob('.run.staging-*')), [])

    def test_intended_count_must_match_authoritative_assignments(self):
        source = make_packet(self.base)
        manifest = json.loads((source / 'packet.json').read_text())
        manifest['intended_count']['a'] = 100
        write_json(source / 'packet.json', manifest)
        rehash(source)
        self.fault('COUNT_MISMATCH', lambda: self.freeze_canonical(source))

    def test_new_run_manifest_hash_matches_retained_assignment_manifest(self):
        source = make_packet(self.base)
        manifest = json.loads((source / 'packet.json').read_text())
        manifest.update(origin='new_run', assignment_manifest_frozen_at='2026-01-01T00:00:00Z',
                        assignment_manifest_sha256='0' * 64)
        write_json(source / 'packet.json', manifest)
        rehash(source)
        self.fault('MANIFEST_HASH_MISMATCH', lambda: self.freeze_canonical(source))

    def test_direct_archive_context_and_gold_version_are_explicit(self):
        config = json.loads((ROOT / 'fixtures/config/packet-a.json').read_text())
        self.fault('MISSING_IMPORT_CONTEXT', lambda: ingest.import_needle_scholar(ROOT / 'fixtures/real/packet-a', config))
        config['_context'] = dict(protocol=json.loads((ROOT / 'protocol.json').read_text()),
                                  sources=json.loads((ROOT / 'sources.json').read_text()), source_root=ROOT)
        packet = ingest.import_needle_scholar(ROOT / 'fixtures/real/packet-a', config)
        self.assertEqual(len(packet.tasks), 324)
        config['assignment_evidence']['revision'] = 'invented-revision'
        self.fault('GOLD_VERSION_MISMATCH', lambda: ingest.import_needle_scholar(ROOT / 'fixtures/real/packet-a', config))

    def test_archive_orphan_tuple_is_rejected(self):
        source = self.base / 'archive'
        shutil.copytree(ROOT / 'fixtures/real/packet-a', source)
        config = json.loads((ROOT / 'fixtures/config/packet-a.json').read_text())
        registry = json.loads((ROOT / 'sources.json').read_text())
        policy = json.loads((ROOT / 'protocol.json').read_text())
        config['_context'] = dict(protocol=policy, sources=registry, source_root=ROOT)
        path = source / 'scholar/bing.json'
        engine = json.loads(path.read_text())
        engine['per_query'][0]['paper_key'] = 'orphan-group'
        write_json(path, engine)
        for row in registry['sources']:
            if row['source_id'] == 'packet-a-bing':
                row.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
                policy['packets']['packet-a']['source_sha256']['packet-a-bing'] = row['sha256']
        self.fault('ORPHAN_RECORD', lambda: ingest.import_needle_scholar(source, config))

    def test_valid_new_run_retains_original_predispatch_manifest_bytes(self):
        source = make_packet(self.base)
        original = (source / 'assignments.jsonl').read_bytes()
        manifest = json.loads((source / 'packet.json').read_text())
        manifest.update(origin='new_run', assignment_manifest_frozen_at='2026-01-01T00:00:00Z',
                        assignment_manifest_sha256=hashlib.sha256(original).hexdigest())
        write_json(source / 'packet.json', manifest)
        rehash(source)
        run = self.freeze_canonical(source)
        packet = ingest.verify_run(run)
        self.assertEqual((run / 'raw/assignment-manifest.jsonl').read_bytes(), original)
        self.assertEqual(packet.manifest['assignment_manifest_sha256'], hashlib.sha256(original).hexdigest())

    def test_archive_equal_query_text_uses_full_group_bucket_tuple(self):
        source = self.base / 'archive'
        shutil.copytree(ROOT / 'fixtures/real/packet-a', source)
        config = json.loads((ROOT / 'fixtures/config/packet-a.json').read_text())
        registry = json.loads((ROOT / 'sources.json').read_text())
        policy = json.loads((ROOT / 'protocol.json').read_text())
        config['_context'] = dict(protocol=policy, sources=registry, source_root=ROOT)
        gold_path = source / 'scholar.jsonl'
        gold = [json.loads(line) for line in gold_path.read_text().splitlines()]
        old_query = gold[4]['query_text']
        self.assertNotEqual(json.loads(gold[0]['gold'])['paper_key'], json.loads(gold[4]['gold'])['paper_key'])
        gold[4]['query_text'] = gold[0]['query_text']
        write_rows(gold_path, gold)
        changed = {'packet-a-gold': gold_path}
        for arm in config['arms']:
            path = source / 'scholar' / (arm + '.json')
            data = json.loads(path.read_text())
            self.assertEqual(data['per_query'][4]['query'], old_query)
            data['per_query'][4]['query'] = gold[0]['query_text']
            write_json(path, data)
            changed['packet-a-' + arm] = path
        for row in registry['sources']:
            if row['source_id'] in changed:
                path = changed[row['source_id']]
                row.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
                policy['packets']['packet-a']['source_sha256'][row['source_id']] = row['sha256']
        packet = ingest.import_needle_scholar(source, config)
        tasks = {r['task_id']: r for r in packet.tasks}
        self.assertEqual(tasks[gold[0]['query_id']]['query_text'], tasks[gold[4]['query_id']]['query_text'])
        self.assertEqual(len(packet.tasks), 324)
        self.assertEqual(len(packet.outcomes), 972)

    def test_verification_rejects_unlisted_escaping_raw_symlink(self):
        run = self.freeze_canonical()
        external = self.base / 'external.json'
        external.write_text('{"private":"outside the run"}\n')
        (run / 'raw/escape.json').symlink_to(external)
        self.fault('UNSAFE_SOURCE_PATH', lambda: ingest.verify_run(run))

    def test_core_canonical_symlink_is_rejected_before_decoding(self):
        source = make_packet(self.base)
        external = self.base / 'not-json.jsonl'
        external.write_text('must never decode outside bytes')
        (source / 'tasks.jsonl').unlink()
        (source / 'tasks.jsonl').symlink_to(external)
        self.fault('UNSAFE_SOURCE_PATH', lambda: self.freeze_canonical(source))

    def test_verify_catches_retained_raw_and_ledger_digest_tampering(self):
        run = self.freeze_canonical()
        path = run / 'raw/src.json'
        original = path.read_bytes()
        path.write_bytes(b'{}')
        self.fault('HASH_MISMATCH', lambda: ingest.verify_run(run))
        path.write_bytes(original)
        manifest = json.loads((run / 'packet.json').read_text())
        manifest['normalized_table_digest'] = '0' * 64
        write_json(run / 'packet.json', manifest)
        self.fault('LEDGER_INTEGRITY_MISMATCH', lambda: ingest.verify_run(run))
