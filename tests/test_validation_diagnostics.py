"""Ordinary regressions for stable spec diagnostics, independent of frozen recipes."""
import copy
from pathlib import Path
import tempfile
import unittest
from pilotpack import compare,ingest,score
from support import ROOT,make_packet,write_rows,rehash
from test_compare import control


class StableDiagnostics(unittest.TestCase):
    def test_actual_setting_and_time_gates_emit_spec_codes(self):
        packet,evaluation=control()
        packet.manifest['actual_settings']['a']['mode']='changed'
        got=compare.assess(packet,evaluation)
        self.assertIn('SETTINGS_MISMATCH',{d['code'] for d in got['diagnostics']})
        packet,evaluation=control()
        packet.protocol['comparison_window']=dict(started_at='2025-01-01T00:00:00Z',ended_at='2025-01-02T00:00:00Z')
        self.assertIn('TIME_WINDOW_MISMATCH',{d['code'] for d in compare.assess(packet,evaluation)['diagnostics']})

    def test_non_dispatch_has_stable_runner_failure_finding(self):
        outcome=dict(observation_kind='not_dispatched',terminal_status='runner_failure',selected_attempt_id=None,results=[])
        delivery=score.select_delivery(dict(assignment_id='a:t',source_ref='src#$'),outcome,(),{})
        self.assertEqual(delivery['classification'],'U')
        self.assertIn('RUNNER_FAILURE',{d['code'] for d in delivery['diagnostics']})

    def test_reconciled_missing_outcome_retains_diagnostic_after_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=make_packet(Path(tmp))
            rows=[__import__('json').loads(s) for s in (root/'outcomes.jsonl').read_text().splitlines()]
            write_rows(root/'outcomes.jsonl',rows[1:]);rehash(root)
            run=ingest.freeze(root,adapter='canonical',config_path=ROOT/'fixtures/config/canonical.json',protocol_path=root/'protocol.json',sources_path=root/'sources.json',out=Path(tmp)/'run')
            self.assertIn('MISSING_OUTCOME',{d['code'] for d in score.score_run(run)['diagnostics']})

    def test_forged_reported_rank_has_reference_mismatch_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=make_packet(Path(tmp))
            rows=[__import__('json').loads(s) for s in (root/'outcomes.jsonl').read_text().splitlines()]
            rows[1]['results'][0]['url']='https://example.org/miss'
            write_rows(root/'outcomes.jsonl',rows);rehash(root)
            run=ingest.freeze(root,adapter='canonical',config_path=ROOT/'fixtures/config/canonical.json',protocol_path=root/'protocol.json',sources_path=root/'sources.json',out=Path(tmp)/'run')
            self.assertIn('REFERENCE_MISMATCH',{d['code'] for d in score.score_run(run)['diagnostics']})

    def test_unavailable_total_cost_has_explicit_limitation(self):
        packet,evaluation=control()
        got=compare.assess(packet,evaluation)
        self.assertIsNone(got['arms']['a']['cost']['total'])
        self.assertIn('INCOMPLETE_COST',{d['code'] for d in got['diagnostics']})

    def test_marginal_latency_cannot_be_presented_as_paired(self):
        from unittest.mock import patch
        packet,evaluation=control()
        marginal=dict(paired=None,linked_attempt_observations=[],marginal=[dict(samples_ms=[1,2])],support_status='marginal_only',unavailable_reason='No links')
        with patch.object(compare,'_latency',return_value=marginal):
            got=compare.assess(packet,evaluation)
        self.assertIsNone(got['pairs'][0]['latency']['paired'])
        self.assertIn('UNPAIRED_LATENCY',{d['code'] for d in got['diagnostics']})
