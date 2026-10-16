"""Independent, stdlib-only canonical baseline. No product or native imports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


def _read_rows(root: Path, name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (root / name).read_text().split('\n') if line]


def _literal_ids(result: dict[str, Any], cap: int) -> dict[str, set[str]]:
    # Deliberately inspect URL/title/snippet, never cached returned_ids or hit flags.
    url = result.get('url') or ''
    snippet = result.get('snippet') or ''
    if cap is None:
        snippet = ''  # URL and title evidence is independent of an unknown snippet cap.
    elif cap > 0:
        snippet = snippet[:cap]
    text = (result.get('title') or '') + ' ' + snippet
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
    for pattern, flags in ((r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', 0),
                           (r'ncbi\.nlm\.nih\.gov/pubmed/(\d+)', 0),
                           (r'europepmc\.org/(?:article|abstract)/MED/(\d+)', re.I)):
        pmid.update(re.findall(pattern, url, flags))
    pmid.update(re.findall(r'\bPMID[:\s]*(\d{6,9})\b', text, re.I))
    pmc = set()
    for pattern in (r'(?:pmc\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov/pmc)/articles?/PMC(\d+)',
                    r'europepmc\.org/article/PMC/PMC(\d+)'):
        pmc.update(re.findall(pattern, url, re.I))
    return {'arxiv': arxiv, 'doi': doi, 'pmid': pmid, 'pmcid': pmc}


def _observation(outcome, requests):
    """Resolve physical evidence independently before inspecting gold identifiers."""
    if outcome is None:
        return 'U', 'missing_record', None
    kind, terminal = outcome['observation_kind'], outcome['terminal_status']
    if kind == 'not_dispatched' or terminal == 'runner_failure':
        return 'U', 'runner_not_dispatched', outcome['results']
    if kind == 'unobserved':
        reason = 'missing_record' if 'MISSING_OUTCOME' in outcome['limitations'] else 'unresolved_dispatch'
        return 'U', reason, outcome['results']
    response = outcome['results']
    if kind == 'attempt_backed':
        requests = sorted(requests, key=lambda row: row['attempt_index'])
        if not requests:
            return 'U', 'unresolved_dispatch', response
        candidate = None
        interrupted = False
        for request in requests:
            if request['status'] == 'unresolved':
                interrupted = True
            elif request['status'] == 'completed':
                candidate = request
                break
        if interrupted:
            return 'U', 'unresolved_dispatch', response
        relevant_indices = [r['attempt_index'] for r in requests
                            if candidate is None or r['attempt_index'] <= candidate['attempt_index']]
        if relevant_indices != list(range(1, len(relevant_indices) + 1)):
            return 'U', 'unresolved_dispatch', response
        if candidate:
            response = candidate['results']
            if (outcome['selected_attempt_id'] != candidate['attempt_id'] or terminal != 'completed'
                    or outcome['results'] != response):
                return 'U', 'unresolved_dispatch', response
        elif (terminal != 'provider_error' or any(r['status'] != 'provider_error' for r in requests)
              or outcome['selected_attempt_id'] not in (None, requests[-1]['attempt_id'])):
            return 'U', 'unresolved_dispatch', response
    elif kind == 'archive_logical' and requests:
        return 'U', 'unresolved_dispatch', response
    if terminal == 'provider_error':
        return 'F', None, response
    if terminal != 'completed' or response is None:
        return 'U', 'completed_unknown' if terminal == 'completed' else 'unresolved_dispatch', response
    if {'MISSING_MATCH_EVIDENCE', 'UNKNOWN_JUDGMENT'} & set(outcome['limitations']):
        return 'U', 'completed_unknown', response
    return 'M', None, response


def evaluate_run(root: Path) -> dict[str, Any]:
    packet = json.loads((root / 'packet.json').read_text())
    tasks = {r['task_id']: r for r in _read_rows(root, 'tasks.jsonl')}
    assignments = _read_rows(root, 'assignments.jsonl')
    observations = {r['assignment_id']: r for r in _read_rows(root, 'outcomes.jsonl')}
    attempts = _read_rows(root, 'attempts.jsonl')
    map_path = root / 'identifier-map.json'
    mapping = json.loads(map_path.read_text())['pmc_to_pmid'] if map_path.exists() else {}
    if any(not isinstance(key, str) or not re.fullmatch('[0-9]+', key)
           or value is not None and (not isinstance(value, str) or not re.fullmatch('[0-9]+', value))
           for key, value in mapping.items()):
        raise ValueError('invalid conversion identifier types')
    empty_arm = lambda: dict(N=0, H=0, M=0, F=0, U=0, reciprocal_rank_sum=0.0,
                             ranks_supported=True, unknown_subcounts={'completed_unknown': 0, 'missing_record': 0,
                                                                    'unresolved_dispatch': 0, 'runner_not_dispatched': 0})
    arms: dict[str, Any] = {name: empty_arm() for name in packet.get('intended_count', {})}
    records: dict[str, Any] = {}
    for assignment in assignments:
        aid, arm_id = assignment['assignment_id'], assignment['arm_id']
        arm = arms.setdefault(arm_id, empty_arm())
        arm['N'] += 1
        outcome = observations.get(aid)
        settings = packet['actual_settings'][arm_id]
        rank = None
        physical = [row for row in attempts if row['assignment_id'] == aid]
        state, reason, response = _observation(outcome, physical)
        if state == 'M' and response:
            gold = tasks[assignment['task_id']]['gold_ids']
            if not gold:
                state, reason = 'U', 'completed_unknown'
            else:
                unresolved_evidence = False
                for position, result in enumerate(response[:settings['k']], 1):
                    found = _literal_ids(result, settings['snippet_chars'])
                    missing = settings['snippet_chars'] is None and bool(result.get('snippet'))
                    if gold.get('pmid') and found['pmcid'] and not found['pmid']:
                        for pmc in found['pmcid']:
                            if mapping.get(pmc) is None:
                                missing = True
                            else:
                                found['pmid'].add(mapping[pmc])
                    if any(set(values) & found.get(namespace, set()) for namespace, values in gold.items()):
                        state = 'H'
                        if unresolved_evidence:
                            arm['ranks_supported'] = False
                        else:
                            rank = position
                        break
                    unresolved_evidence |= missing
                if state != 'H' and unresolved_evidence:
                    state, reason = 'U', 'completed_unknown'
        arm[state] += 1
        if rank is not None:
            arm['reciprocal_rank_sum'] += 1.0 / rank
        if reason:
            arm['unknown_subcounts'][reason] += 1
        records[aid] = dict(partition=state, first_hit_rank=rank,
                            result_count=len(response) if response is not None else None)
    for arm_id, arm in arms.items():
        known_basis = packet['assignment_basis'] != 'unreconstructable'
        n = arm['N'] if known_basis else None
        arm['N'] = n
        arm['delivered_hit_at_k'] = arm['H'] / n if n else None
        arm['missingness_range'] = [arm['H'] / n, (arm['H'] + arm['U']) / n] if n else None
        arm['observed_attempt_rows'] = sum(r['assignment_id'] in records and
                                           r['assignment_id'] in {a['assignment_id'] for a in assignments if a['arm_id'] == arm_id}
                                           for r in attempts)
        arm['physical_attempt_count_lower_bound'] = 0
        all_requests_present = True
        for assignment in assignments:
            if assignment['arm_id'] != arm_id:
                continue
            aid = assignment['assignment_id']
            request_indices = sorted(row['attempt_index'] for row in attempts if row['assignment_id'] == aid)
            observed_count = len(request_indices)
            all_requests_present &= request_indices == list(range(1, observed_count + 1))
            outcome = observations.get(aid)
            dispatch = (outcome and outcome['terminal_status'] in ('completed', 'provider_error')
                        and outcome['observation_kind'] != 'not_dispatched')
            arm['physical_attempt_count_lower_bound'] += max(observed_count, request_indices[-1] if request_indices else 0,
                                                              int(bool(dispatch)))
        arm['physical_attempt_count_exact'] = (arm['observed_attempt_rows']
                                               if packet['attempt_history'][arm_id] == 'complete'
                                               and all_requests_present
                                               and arm['observed_attempt_rows'] == arm['physical_attempt_count_lower_bound'] else None)
        # This profile's native eligible denominator was established by unchanged replay.
        profile = packet.get('extensions', {}).get('native_profile', packet.get('native_profile'))
        source_observations = [observations.get(a['assignment_id']) for a in assignments if a['arm_id'] == arm_id]
        denominator_supported = (profile == 'needle-scholar-all-rows-v1' and n is not None
                                 and all(o and o['terminal_status'] in ('completed', 'provider_error')
                                         and o['observation_kind'] not in ('unobserved', 'not_dispatched')
                                         for o in source_observations))
        native_supported = denominator_supported and not arm['U']
        ranks_supported = arm.pop('ranks_supported')
        arm['native_metrics'] = dict(support_status='supported' if native_supported and ranks_supported else 'partial' if denominator_supported else 'unsupported',
                                     num_scored=n if denominator_supported else None,
                                     recall_at_k=(arm['H'] / n if n else 0.0) if native_supported else None,
                                     mrr_at_k=(arm['reciprocal_rank_sum'] / n if n else 0.0) if native_supported and ranks_supported else None,
                                     search_errors=sum(o['terminal_status'] == 'provider_error' for o in source_observations) if denominator_supported else None)
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
