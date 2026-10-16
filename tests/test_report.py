"""Offline publication/security contracts, exercising real files and HTML parsing."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pilotpack import compare, ingest, report, score
from pilotpack.schema import ValidationError
from support import make_packet, write_json


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.links, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.links.extend(v for k, v in attrs if k == 'href')
        if any(k.startswith('on') or k in ('src', 'srcset') for k, _ in attrs):
            raise AssertionError('Executable attribute or external asset')

    def handle_data(self, data):
        self.text.append(data)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        source = make_packet(self.base)
        config = self.base / 'config.json'
        write_json(config, {'adapter_profile': 'canonical-v1'})
        self.run = ingest.freeze(source, adapter='canonical', config_path=config,
                                 protocol_path=source / 'protocol.json', sources_path=source / 'sources.json',
                                 out=self.base / 'run')
        self.evaluation = compare.assess(ingest.verify_run(self.run), score.score_run(self.run))
        self.verdict = compare.build_verdict(self.evaluation)
        self.out = self.base / 'output'

    def publish(self):
        report.write_json_artifacts(self.out, evaluation=self.evaluation, verdict=self.verdict)

    def test_html_escapes_all_text_and_only_http_links_are_clickable(self):
        evil = '<script title="x">雪 & \' </script>'
        evaluation = copy.deepcopy(self.evaluation)
        evaluation['source_inventory'][0]['title'] = evil
        case = evaluation['cases'][0]
        case['query_text'] = evil
        case['results'] = [dict(url=url, title=evil, snippet=evil) for url in
                           ['javascript:alert(1)', 'data:text/html,boom', 'https://example.org/?a="x"&b=雪',
                            'http://example.org/ok']]
        case['attempts'] = [dict(attempt_id='hidden-attempt', results=[dict(url='javascript:evil', title=evil)])]
        rendered = report.render_html(evaluation, compare.build_verdict(evaluation))
        parser = Inspector()
        parser.feed(rendered)
        self.assertNotIn('script', parser.tags)
        self.assertNotIn('link', parser.tags)
        self.assertNotIn('img', parser.tags)
        self.assertNotIn('<script', rendered)
        self.assertNotIn('</script>', rendered)
        self.assertIn('&quot;', rendered)
        self.assertIn('https://example.org/?a="x"&b=雪', parser.links)
        self.assertIn('http://example.org/ok', parser.links)
        self.assertFalse(any(x.startswith(('javascript:', 'data:')) for x in parser.links))
        text = ''.join(parser.text)
        self.assertIn(evil, text)
        self.assertIn('hidden-attempt', text)
        self.assertIn('javascript:alert(1)', text)

    def test_html_keeps_accounting_metrics_conditions_cases_and_caveats_visible(self):
        rendered = report.render_html(self.evaluation, self.verdict)
        parser = Inspector()
        parser.feed(rendered)
        text = ''.join(parser.text)
        for field in ['reconstructed', 'native_metrics', 'delivered_hit_at_k', 'observed_attempt_rows',
                      'physical_attempt_count_exact', 'unavailable_reason', 'settings', 'actual', 'declared',
                      'decision_status', 'source_ref', 'unknown_reason', 'first_hit_rank']:
            self.assertIn(field, text)
        for case in self.evaluation['cases']:
            self.assertIn(case['assignment_id'], text)
        for caveat in self.evaluation['limitations']:
            self.assertIn(caveat, text)
        self.assertLess(text.index('Provenance'), text.index('Comparisons'))
        self.assertIn('not a purchasing recommendation', text)

    def test_replay_json_and_html_bytes_are_stable_and_report_does_not_score(self):
        self.publish()
        with patch('pilotpack.score.score_run', side_effect=AssertionError('report must not score')):
            html = report.write_report(self.run, self.out / 'evaluation.json', self.out)
        first = {p.name: p.read_bytes() for p in self.out.iterdir()}
        self.publish()
        report.write_report(self.run, self.out / 'evaluation.json', self.out)
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.out.iterdir()})
        self.assertEqual(html, self.out / 'report.html')
        self.assertEqual(json.loads(first['verdict.json']), self.verdict)

    def test_output_reuse_refuses_each_different_identity_and_verdict_disagreement(self):
        self.publish()
        before = (self.out / 'evaluation.json').read_bytes()
        for field in ['run_id', 'content_id', 'protocol_hash']:
            evaluation = copy.deepcopy(self.evaluation)
            evaluation[field] = 'different'
            with self.subTest(field=field), self.assertRaises(ValidationError):
                report.write_json_artifacts(self.out, evaluation=evaluation,
                                            verdict=compare.build_verdict(evaluation))
            self.assertEqual((self.out / 'evaluation.json').read_bytes(), before)
        bad = copy.deepcopy(self.verdict)
        bad['arms']['a']['H'] += 1
        with self.assertRaises(ValidationError):
            report.write_json_artifacts(self.out, evaluation=self.evaluation, verdict=bad)

    def test_report_rejects_wrong_identity_corrupt_or_partial_evaluation_before_publication(self):
        path = self.base / 'evaluation.json'
        for value in ['{', '{}', json.dumps(dict(self.evaluation, protocol_hash='wrong'))]:
            path.write_text(value)
            with self.subTest(value=value[:20]), self.assertRaises((ValueError, ValidationError)):
                report.write_report(self.run, path, self.out)
            self.assertFalse(self.out.exists())

    def test_interrupted_publication_retains_previous_complete_output_or_no_output(self):
        for existing in [False, True]:
            with self.subTest(existing=existing):
                if existing:
                    self.publish()
                before = {p.name: p.read_bytes() for p in self.out.iterdir()} if existing else None
                with patch('pilotpack.report.os.replace', side_effect=OSError('interrupted')):
                    with self.assertRaises(OSError):
                        self.publish()
                if existing:
                    self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})
                else:
                    self.assertFalse(self.out.exists())

    def test_second_publication_rename_failure_restores_previous_complete_directory(self):
        self.publish()
        report.write_report(self.run, self.out / 'evaluation.json', self.out)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        import os
        replace = os.replace
        def interrupted(source, target):
            if '.staging-' in Path(source).name:
                raise OSError('interruption after backup rename')
            return replace(source, target)
        with patch('pilotpack.report.os.replace', side_effect=interrupted):
            with self.assertRaises(OSError):
                self.publish()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})

    def test_malformed_nested_records_fail_with_structured_validation_before_publication(self):
        for field, value in [('cases', [None]), ('reference_checks', [None]), ('diagnostics', [None]),
                             ('pairs', [None]), ('cases', [{'classification': 'H'}])]:
            bad = copy.deepcopy(self.evaluation)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                report.write_json_artifacts(self.out, evaluation=bad, verdict=compare.build_verdict(bad))
            self.assertFalse(self.out.exists())

    def test_report_never_writes_inside_or_over_frozen_run(self):
        self.publish()
        for out in [self.run, self.run / 'derived', self.base]:
            with self.subTest(out=out), self.assertRaises(ValidationError):
                report.write_report(self.run, self.out / 'evaluation.json', out)
        ingest.verify_run(self.run)

    def test_reference_mismatch_cannot_be_published_or_rendered_from_file(self):
        bad = copy.deepcopy(self.evaluation)
        bad['diagnostics'].append(dict(code='REFERENCE_MISMATCH', severity='block', scope='run',
                                       source_refs=[], message='disagreement'))
        with self.assertRaises(ValidationError):
            report.write_json_artifacts(self.out, evaluation=bad, verdict=compare.build_verdict(bad))
        path = self.base / 'evaluation.json'
        write_json(path, bad)
        with self.assertRaises(ValidationError):
            report.write_report(self.run, path, self.out)
        self.assertFalse(self.out.exists())
