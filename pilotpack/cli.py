"""Install-free offline freeze, evaluate and report commands."""
import argparse
from pathlib import Path
import sys

from . import compare, ingest, report, score
from .schema import ValidationError


def _diagnostic(error: Exception) -> None:
    if isinstance(error, ValidationError):
        for item in error.diagnostics:
            print(f"{item['code']} [{item['scope']}]: {item['message']}", file=sys.stderr)
    else:
        print(str(error), file=sys.stderr)


def _exit(evaluation: dict) -> int:
    return 3 if any(p['comparison_status'] == 'blocked' for p in evaluation['pairs']) else 0


def evaluate_run(run: Path, out: Path) -> int:
    """Verify, score (one reference invocation), qualify, then publish."""
    try:
        packet = ingest.verify_run(run)
        report.ensure_output_location(run, out)
        evaluation = score.score_run(run)
        if (any(d['code'] == 'REFERENCE_MISMATCH' for d in evaluation['diagnostics'])
                or any(c['status'] == 'mismatch' for c in evaluation['reference_checks'])):
            raise ValidationError([dict(code='REFERENCE_MISMATCH', severity='error', scope='run',
                                        source_refs=[], message='Reference disagreement; no artifacts published.')])
        evaluation = compare.assess(packet, evaluation)
        report.write_json_artifacts(out, evaluation=evaluation, verdict=compare.build_verdict(evaluation))
        for item in evaluation['diagnostics']:
            print(f"{item['code']} [{item['scope']}]: {item['message']}", file=sys.stderr)
        return _exit(evaluation)
    except (OSError, ValueError, KeyError, TypeError) as error:
        _diagnostic(error)
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='pilotpack', description='Local offline pilot evidence reports')
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze', help='Validate and freeze immutable local evidence')
    freeze.add_argument('--adapter', required=True, choices=['needle-scholar', 'canonical'])
    for flag in ('input', 'config', 'protocol', 'sources', 'out'):
        freeze.add_argument('--' + flag, required=True, type=Path)
    evaluate = commands.add_parser('evaluate', help='Score and qualify a verified frozen run')
    for flag in ('run', 'out'):
        evaluate.add_argument('--' + flag, required=True, type=Path)
    render = commands.add_parser('report', help='Render a verified evaluation without rescoring')
    for flag in ('run', 'evaluation', 'out'):
        render.add_argument('--' + flag, required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'freeze':
            ingest.freeze(args.input, adapter=args.adapter, config_path=args.config, protocol_path=args.protocol,
                          sources_path=args.sources, out=args.out)
            return 0
        if args.command == 'evaluate':
            return evaluate_run(args.run, args.out)
        report.write_report(args.run, args.evaluation, args.out)
        return _exit(report._read(args.evaluation))
    except (OSError, ValueError, KeyError, TypeError) as error:
        _diagnostic(error)
        return 2
