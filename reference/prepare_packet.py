"""Bounded export for the acquired Scholar archive shape, independent of product code."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


def _dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')


def prepare_run(source: Path, config_path: Path, out: Path) -> None:
    if out.exists():
        raise FileExistsError(f'refusing existing run: {out}')
    config = json.loads(config_path.read_text())
    gold_raw = [json.loads(line) for line in (source / config['gold_path']).read_text().splitlines()]
    tasks, assignments, outcomes = [], [], []
    gold_by_key = {}
    for line, row in enumerate(gold_raw, 1):
        gold = json.loads(row['gold'])
        origin = json.loads(row['query_origin'])
        key = (row['query_text'], gold['paper_key'], origin['bucket'])
        if key in gold_by_key:
            raise ValueError(f'ambiguous gold tuple at line {line}')
        gold_by_key[key] = (row, gold, origin, line)
    if len({r['query_id'] for r in gold_raw}) != len(gold_raw):
        raise ValueError('duplicate task ID')
    selected = {key: value for key, value in gold_by_key.items()
                if config['gold_namespace_required'] in value[1]['ids']}
    for row, gold, origin, line in selected.values():
        tasks.append(dict(task_id=row['query_id'], source_group_id=gold['paper_key'],
                          cohort_id=config['cohort_id'], query_text=row['query_text'],
                          gold_ids={k: [str(v)] for k, v in sorted(gold['ids'].items())},
                          bucket=origin['bucket'], source_ref=f"{config['run_id']}-gold#line={line}"))
    for arm in config['arms']:
        engine = json.loads((source / 'scholar' / f'{arm}.json').read_text())
        observed = {}
        for index, pq in enumerate(engine['per_query']):
            key = (pq['query'], pq['paper_key'], pq['bucket'])
            if key in observed or key not in gold_by_key:
                raise ValueError(f'duplicate/orphan tuple for {arm} row {index}')
            observed[key] = (pq, index)
        if observed.keys() != gold_by_key.keys():
            raise ValueError(f'incomplete gold correspondence for {arm}')
        for key, (row, gold, origin, line) in selected.items():
            pq, index = observed[key]
            if pq['n_results'] != len(pq['results']):
                raise ValueError(f'result-count mismatch for {arm} row {index}')
            aid = arm + ':' + row['query_id']
            ref = f"{config['run_id']}-{arm}#$.per_query[{index}]"
            assignments.append(dict(assignment_id=aid, task_id=row['query_id'], arm_id=arm,
                                    settings_id=arm, source_ref=f"{config['run_id']}-gold#line={line}"))
            results = [dict(rank=n, url=r['url'], title=r.get('title'), snippet=r.get('snippet'),
                            returned_ids=r.get('ids', {})) for n, r in enumerate(pq['results'], 1)]
            outcomes.append(dict(assignment_id=aid, observation_kind='archive_logical',
                                 terminal_status='provider_error' if pq['search_error'] is not None else 'completed',
                                 selected_attempt_id=None, results=results,
                                 reported_hit_rank=pq['hit_rank'], source_ref=ref,
                                 limitations=['UNKNOWN_ATTEMPT_HISTORY', 'MISSING_COST',
                                              'MISSING_TASK_TIMESTAMPS', 'UNKNOWN_ACTUAL_SETTINGS']))
    out.mkdir(parents=True)
    try:
        shutil.copytree(source, out / 'raw')
        for name, rows, key in [('tasks.jsonl', tasks, 'task_id'),
                                ('assignments.jsonl', assignments, 'assignment_id'),
                                ('outcomes.jsonl', outcomes, 'assignment_id')]:
            (out / name).write_text(''.join(json.dumps(r, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'
                                           for r in sorted(rows, key=lambda r: r[key])))
        (out / 'attempts.jsonl').write_bytes(b'')
        _dump(out / 'packet.json', dict(schema_version=1, run_id=config['run_id'], origin='archive',
                                       adapter_profile=config['adapter_profile'], native_profile='needle-scholar-all-rows-v1',
                                       assignment_basis='reconstructed',
                                       intended_count={a: len(tasks) for a in config['arms']},
                                       actual_settings=config['actual_settings'],
                                       attempt_history={a: 'unknown' for a in config['arms']},
                                       excluded_task_count=len(gold_raw) - len(tasks),
                                       limitations=['PMID_COHORT_EXCLUDED_MISSING_CONVERSION_MAP']))
        # Freeze every exported byte; this baseline is not the product immutable ledger.
        _dump(out / 'hashes.json', {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(out.rglob('*')) if p.is_file()})
    except Exception:
        shutil.rmtree(out)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare_run(args.input, args.config, args.out)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'prepare_packet: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
