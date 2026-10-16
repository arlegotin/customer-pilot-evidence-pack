"""Deterministic, escaped offline reports and complete-directory publication."""
from html import escape
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from urllib.parse import urlsplit

from .compare import build_verdict
from .ingest import verify_run
from .schema import ValidationError

JsonObject = dict[str, Any]
_IDENTITIES = ('run_id', 'content_id', 'protocol_hash')
_FIELDS = ('schema_version', *_IDENTITIES, 'source_inventory', 'accounting', 'arms', 'cases',
           'native_metrics', 'reference_checks', 'pairs', 'decisions', 'diagnostics', 'limitations')
_CAVEATS = ('Retrieval is not answer quality or citation support.',
            'A miss does not prove index absence.',
            'Missingness bounds are not confidence intervals.',
            'The demonstration is too small to resolve tiny provider differences.')


def _fail(message: str) -> None:
    raise ValidationError([dict(code='INVALID_REPORT_INPUT', severity='error', scope='report',
                                source_refs=[], message=message)])


def _read(path: Path) -> JsonObject:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique,
                       parse_constant=lambda value: _fail('Nonfinite JSON number: ' + value))
    if not isinstance(value, dict):
        _fail('Expected an object in ' + str(path))
    return value


def _bytes(value: JsonObject) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def _validate(evaluation: JsonObject, verdict: JsonObject) -> None:
    if not isinstance(evaluation, dict) or any(field not in evaluation for field in _FIELDS):
        _fail('Evaluation is missing required fields.')
    if evaluation['schema_version'] != 1 or any(not isinstance(evaluation[k], str) or not evaluation[k]
                                               for k in _IDENTITIES):
        _fail('Invalid evaluation version or identity.')
    for field in ('source_inventory', 'cases', 'reference_checks', 'pairs', 'diagnostics', 'limitations'):
        if not isinstance(evaluation[field], list):
            _fail('Expected list: ' + field)
    for field in ('accounting', 'arms', 'native_metrics', 'decisions'):
        if not isinstance(evaluation[field], dict):
            _fail('Expected object: ' + field)
    for field in ('source_inventory', 'cases', 'reference_checks', 'pairs', 'diagnostics'):
        if any(not isinstance(row, dict) for row in evaluation[field]):
            _fail('Expected object records: ' + field)
    case_fields = ('assignment_id', 'task_id', 'arm_id', 'classification', 'query_text', 'attempts',
                   'results', 'source_refs')
    for case in evaluation['cases']:
        if (any(k not in case for k in case_fields) or case['classification'] not in ('H', 'M', 'F', 'U')
                or not isinstance(case['attempts'], list) or not isinstance(case['source_refs'], list)
                or any(not isinstance(a, dict) for a in case['attempts'])):
            _fail('Malformed case or attempt record.')
    if any(not isinstance(arm, dict) for arm in evaluation['arms'].values()):
        _fail('Expected arm summary objects.')
    if verdict != build_verdict(evaluation):
        _fail('Verdict must be the documented evaluation subset.')
    checks = evaluation['reference_checks']
    if (not any(c.get('reference') == 'independent_oracle' and c.get('status') == 'passed' for c in checks)
            or any(c.get('status') == 'mismatch' for c in checks)
            or any(d.get('code') == 'REFERENCE_MISMATCH' for d in evaluation['diagnostics'])):
        _fail('Independent reference reconciliation must pass before publication.')
    if any(p.get('comparison_status') not in ('eligible', 'blocked') for p in evaluation['pairs']):
        _fail('Invalid comparison status.')
    _bytes(evaluation)
    _bytes(verdict)


def ensure_output_location(run: Path, out: Path) -> None:
    """Derived publication must never rename, replace or alter frozen evidence."""
    run, out = Path(run).resolve(), Path(out).resolve()
    if run == out or run in out.parents or out in run.parents:
        _fail('Output and frozen evidence directories must not overlap.')


def _existing(out: Path, evaluation: JsonObject) -> None:
    if out.is_symlink():
        _fail('Output directory must not be a symlink.')
    if not out.exists():
        return
    if not out.is_dir():
        _fail('Output is not a directory.')
    names = {p.name for p in out.iterdir()}
    if not names:
        return
    if not {'evaluation.json', 'verdict.json'} <= names or names - {'evaluation.json', 'verdict.json', 'report.html'}:
        _fail('Refusing to replace an incomplete or unrelated output directory.')
    if any(p.is_symlink() or not p.is_file() for p in out.iterdir()):
        _fail('Derived files must be regular files.')
    previous = _read(out / 'evaluation.json')
    _validate(previous, _read(out / 'verdict.json'))
    if any(previous[field] != evaluation[field] for field in _IDENTITIES):
        _fail('Output belongs to a different run/content/protocol identity.')


def _publish(out: Path, evaluation: JsonObject, verdict: JsonObject, html: str | None = None) -> None:
    """Stage the entire output; a failed write never exposes a partial final set.

    Existing complete output is moved to a sibling backup before the staged
    directory is renamed. During that rename boundary the final name can be absent,
    never mixed. A process kill leaves the complete previous backup recoverable.
    Ordinary exceptions restore it. Concurrent publication fails closed via a lock.
    """
    out = Path(out).absolute()
    _validate(evaluation, verdict)
    _existing(out, evaluation)
    out.parent.mkdir(parents=True, exist_ok=True)
    lock = out.parent / ('.' + out.name + '.publishing')
    lock.mkdir()
    stage = None
    backup = None
    try:
        _existing(out, evaluation)
        stage = Path(tempfile.mkdtemp(prefix='.' + out.name + '.staging-', dir=out.parent))
        for name, data in [('evaluation.json', _bytes(evaluation)), ('verdict.json', _bytes(verdict))]:
            with (stage / name).open('wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        if html is not None:
            with (stage / 'report.html').open('w', encoding='utf-8', newline='\n') as handle:
                handle.write(html)
                handle.flush()
                os.fsync(handle.fileno())
        if out.exists():
            backup = Path(tempfile.mkdtemp(prefix='.' + out.name + '.previous-', dir=out.parent))
            backup.rmdir()
            os.replace(out, backup)
        os.replace(stage, out)
        stage = None
    except BaseException:
        if backup is not None and backup.exists() and not out.exists():
            os.rename(backup, out)
        raise
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        if backup is not None and backup.exists() and out.exists():
            shutil.rmtree(backup)
        lock.rmdir()


def _value(value: Any) -> str:
    if isinstance(value, dict):
        return '<dl>' + ''.join('<dt>' + escape(str(k), quote=True) + '</dt><dd>' + _value(v) + '</dd>'
                                for k, v in sorted(value.items())) + '</dl>'
    if isinstance(value, list):
        return '<ol>' + ''.join('<li>' + _value(v) + '</li>' for v in value) + '</ol>' if value else '<span>[]</span>'
    if value is None:
        return '<span>unavailable (null)</span>'
    text = str(value) if not isinstance(value, bool) else str(value).lower()
    safe = escape(text, quote=True)
    try:
        parsed = urlsplit(text)
        link = parsed.scheme.lower() in ('http', 'https') and bool(parsed.netloc)
    except ValueError:
        link = False
    if link:
        return '<a href="' + safe + '" rel="noreferrer noopener">' + safe + '</a>'
    return '<span>' + safe + '</span>'


def render_html(evaluation: JsonObject, verdict: JsonObject) -> str:
    """Render all imported values as escaped text; no executable or remote assets."""
    _validate(evaluation, verdict)
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; base-uri \'none\'; form-action \'none\'">',
             '<title>Pilot evidence report</title></head><body><h1>Pilot evidence report</h1>',
             '<h2>Provenance and qualifications</h2>',
             _value({key: evaluation[key] for key in _IDENTITIES}),
             '<h3>source_inventory</h3>', _value(evaluation['source_inventory']),
             '<h3>accounting</h3>', _value(evaluation['accounting']),
             '<ul>' + ''.join('<li>' + escape(c) + '</li>' for c in _CAVEATS) + '</ul>',
             '<p>A descriptive result is not a purchasing recommendation. '
             'Null means unavailable; missing cost is never zero. '
             'Physical request lower bounds do not establish exact retry history. '
             'Case records do not establish a causal explanation for a miss.</p>',
             '<h3>limitations</h3>', _value(evaluation['limitations']),
             '<h3>reference_checks</h3>', _value(evaluation['reference_checks']),
             '<h2>Native versus delivered metrics</h2><h3>native_metrics</h3>', _value(evaluation['native_metrics'])]
    for arm, data in sorted(evaluation['arms'].items()):
        parts.extend(['<h3>Arm ' + escape(arm) + '</h3>', _value(data)])
    parts.extend(['<h2>Comparisons: settings and gates</h2>',
                  _value(evaluation['pairs']) if evaluation['pairs'] else '<p>No comparison requested.</p>',
                  '<h2>Independent arm decisions</h2>', _value(evaluation['decisions']),
                  '<h2>diagnostics</h2>', _value(evaluation['diagnostics']),
                  '<h2>Inspectable cases and all evidenced attempts</h2>'])
    for case in evaluation['cases']:
        parts.extend(['<details><summary>' + escape(str(case['assignment_id'])) + ': '
                      + escape(str(case['classification'])) + '</summary>', _value(case), '</details>'])
    parts.append('</body></html>\n')
    return '\n'.join(parts)


def write_json_artifacts(out: Path, *, evaluation: JsonObject, verdict: JsonObject) -> None:
    """Publish evaluation and its verdict together; old HTML is invalidated."""
    _publish(out, evaluation, verdict)


def write_report(run: Path, evaluation_path: Path, out: Path) -> Path:
    """Verify frozen identity and render supplied evaluation, without scoring."""
    packet = verify_run(Path(run))
    ensure_output_location(run, out)
    evaluation = _read(Path(evaluation_path))
    verdict = build_verdict(evaluation) if all(k in evaluation for k in _FIELDS) else {}
    _validate(evaluation, verdict)
    expected = dict(run_id=packet.manifest['run_id'], content_id=packet.manifest['content_id'],
                    protocol_hash=packet.manifest['protocol_sha256'])
    if any(evaluation[k] != expected[k] for k in _IDENTITIES):
        _fail('Evaluation does not belong to this frozen run/protocol/content.')
    assignments = {a['assignment_id']: a for a in packet.assignments}
    cases = evaluation['cases']
    if (len(cases) != len(assignments) or {c.get('assignment_id') for c in cases} != set(assignments)
            or any(c.get('task_id') != assignments[c['assignment_id']]['task_id']
                   or c.get('arm_id') != assignments[c['assignment_id']]['arm_id'] for c in cases)):
        _fail('Evaluation case identities differ from frozen assignments.')
    _publish(out, evaluation, verdict, render_html(evaluation, verdict))
    return Path(out) / 'report.html'
