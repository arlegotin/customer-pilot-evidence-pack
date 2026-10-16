"""Independent, stdlib-only canonical baseline. No product or native imports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


def _read_rows(root: Path, name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (root / name).read_text().splitlines()]


def _literal_ids(result: dict[str, Any], cap: int) -> dict[str, set[str]]:
    # Deliberately inspect URL/title/snippet, never cached returned_ids or hit flags.
    url = result.get('url') or ''
    snippet = result.get('snippet') or ''
    text = (result.get('title') or '') + ' ' + (snippet[:cap] if cap > 0 else snippet)
    arxiv = set()
    identity = r'([a-z-]+/\d{7}|\d{4}\.\d{4,5})'
    for pattern in (r'arxiv\.org/(?:abs|pdf|html)/' + identity,
                    r'arxiv[:\s]+' + identity, r'10\.48550/arxiv\.' + identity):
        for value in (url, text):
            arxiv.update(x.lower() for x in re.findall(pattern, value, re.I))
    doi = set()
    for value in (url, text):
        for raw in re.findall(r'10\.\d{4,9}/[-._;()/:a-z0-9]+', value, re.I):
            cleaned = raw.rstrip('.)').rstrip(',')
            doi.add(re.sub(r'/(?:full|pdf|epdf|html|meta|abstract|citations?)$', '', cleaned,
                           flags=re.I).lower())
    pmid = set()
    for pattern in (r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)',
                    r'ncbi\.nlm\.nih\.gov/pubmed/(\d+)',
                    r'europepmc\.org/(?:article|abstract)/MED/(\d+)'):
        pmid.update(re.findall(pattern, url, re.I))
    pmid.update(re.findall(r'\bPMID[:\s]*(\d{6,9})\b', text, re.I))
    return {'arxiv': arxiv, 'doi': doi, 'pmid': pmid}


def evaluate_run(root: Path) -> dict[str, Any]:
    packet = json.loads((root / 'packet.json').read_text())
    tasks = {r['task_id']: r for r in _read_rows(root, 'tasks.jsonl')}
    assignments = _read_rows(root, 'assignments.jsonl')
    observations = {r['assignment_id']: r for r in _read_rows(root, 'outcomes.jsonl')}
    attempts = _read_rows(root, 'attempts.jsonl')
    arms: dict[str, Any] = {}
    records: dict[str, Any] = {}
    for assignment in assignments:
        aid, arm_id = assignment['assignment_id'], assignment['arm_id']
        arm = arms.setdefault(arm_id, dict(N=0, H=0, M=0, F=0, U=0,
                                          reciprocal_rank_sum=0.0,
                                          unknown_subcounts={'completed_unknown': 0, 'missing_record': 0,
                                                             'unresolved_dispatch': 0, 'runner_not_dispatched': 0}))
        arm['N'] += 1
        outcome = observations.get(aid)
        settings = packet['actual_settings'][arm_id]
        rank = None
        reason = None
        if outcome is None:
            state, reason = 'U', 'missing_record'
        elif outcome['terminal_status'] == 'provider_error':
            state = 'F'
        elif outcome['terminal_status'] == 'runner_failure' or outcome['observation_kind'] == 'not_dispatched':
            state, reason = 'U', 'runner_not_dispatched'
        elif (outcome['terminal_status'] != 'completed' or outcome['results'] is None
              or {'MISSING_MATCH_EVIDENCE', 'UNKNOWN_JUDGMENT'} & set(outcome['limitations'])):
            state = 'U'
            reason = 'completed_unknown' if outcome['observation_kind'] != 'unobserved' else 'unresolved_dispatch'
        else:
            gold = tasks[assignment['task_id']]['gold_ids']
            for result in outcome['results'][:settings['k']]:
                found = _literal_ids(result, settings['snippet_chars'])
                if any(set(values) & found.get(namespace, set()) for namespace, values in gold.items()):
                    rank = result['rank']
                    break
            state = 'H' if rank is not None else 'M'
        arm[state] += 1
        if rank is not None:
            arm['reciprocal_rank_sum'] += 1.0 / rank
        if reason:
            arm['unknown_subcounts'][reason] += 1
        records[aid] = dict(partition=state, first_hit_rank=rank,
                            result_count=len(outcome['results']) if outcome and outcome['results'] is not None else None)
    for arm_id, arm in arms.items():
        known_basis = packet['assignment_basis'] != 'unreconstructable'
        n = arm['N'] if known_basis else None
        arm['N'] = n
        arm['delivered_hit_at_k'] = arm['H'] / n if n else None
        arm['missingness_range'] = [arm['H'] / n, (arm['H'] + arm['U']) / n] if n else None
        arm['observed_attempt_rows'] = sum(r['assignment_id'] in records and
                                           r['assignment_id'] in {a['assignment_id'] for a in assignments if a['arm_id'] == arm_id}
                                           for r in attempts)
        arm['physical_attempt_count_exact'] = (arm['observed_attempt_rows']
                                               if packet['attempt_history'][arm_id] == 'complete' else None)
        # This profile's native eligible denominator was established by unchanged replay.
        native_supported = (packet.get('native_profile') == 'needle-scholar-all-rows-v1'
                            and n is not None and not arm['U'])
        arm['native_metrics'] = dict(support_status='supported' if native_supported else 'unsupported',
                                     num_scored=n if native_supported else None,
                                     recall_at_k=arm['H'] / n if n and native_supported else None,
                                     mrr_at_k=arm['reciprocal_rank_sum'] / n if n and native_supported else None,
                                     search_errors=arm['F'] if native_supported else None)
    return dict(run_id=packet['run_id'], task_count=len(tasks),
                source_group_count=len({t['source_group_id'] for t in tasks.values()}),
                arms=arms, assignments=records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_run(args.run)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'oracle: {error}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
