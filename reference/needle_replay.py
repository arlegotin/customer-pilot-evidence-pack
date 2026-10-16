"""Run unchanged pinned NEEDLE with stored-response clients; network is denied."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import socket
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--checkout', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads((Path(__file__).parent / 'native-source-manifest.json').read_text())
        for name, expected in manifest['files'].items():
            if hashlib.sha256((args.checkout / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f'pinned source differs: {name}')
        sys.path.insert(0, str(args.checkout.resolve() / 'src'))
        from needle.scholar.score import GoldPaper, run_papers
        from needle.shared.recall import recall_summary
        from needle.shared.search.base import SearchResult

        def denied(*args, **kwargs):
            raise RuntimeError('offline native replay prohibits networking')
        socket.socket.connect = denied
        socket.create_connection = denied
        socket.getaddrinfo = denied

        raw_gold = [json.loads(line) for line in (args.packet / 'scholar.jsonl').read_text().splitlines()]
        selected = []
        selected_keys = []
        all_keys = []
        for row in raw_gold:
            gold, origin = json.loads(row['gold']), json.loads(row['query_origin'])
            key = (row['query_text'], gold['paper_key'], origin['bucket'])
            all_keys.append(key)
            if 'arxiv' in gold['ids']:
                selected.append(GoldPaper(row['query_text'], gold['paper_key'], gold['ids'], origin['bucket']))
                selected_keys.append(key)
        if len(set(all_keys)) != len(all_keys):
            raise ValueError('ambiguous source gold tuple')
        names = ['bing', 'keenable', 'perplexity']
        originals = {name: json.loads((args.packet / 'scholar' / f'{name}.json').read_text()) for name in names}
        stored = {}
        for name, engine in originals.items():
            keyed = {(r['query'], r['paper_key'], r['bucket']): r for r in engine['per_query']}
            if len(keyed) != len(engine['per_query']) or keyed.keys() != set(all_keys):
                raise ValueError(f'invalid correspondence: {name}')
            stored[name] = [keyed[key] for key in selected_keys]

        class StoredClient:
            def __init__(self, rows):
                self.rows = iter(rows)
                self.latencies_ms = []  # Archive samples cannot be paired to this subset.

            async def search(self, query, *, num_results):
                row = next(self.rows)
                if row['query'] != query:
                    raise ValueError('stored response/query mismatch')
                return ([SearchResult(url=r['url'], title=r.get('title'), snippet=r.get('snippet'))
                         for r in row['results']], row['search_error'])

        slim = json.loads((args.packet / 'scholar.json').read_text())
        replay = asyncio.run(run_papers(selected, {n: StoredClient(stored[n]) for n in names},
                                        num_results=slim['num_results'], snippet_chars=slim['snippet_chars'],
                                        idconv=None, concurrent_search=False))
        discrepancies = []
        engines = {}
        for name in names:
            actual = replay['engines'][name]
            expected = recall_summary(copy.deepcopy(stored[name]), None)
            for index, (got, want) in enumerate(zip(actual['per_query'], stored[name], strict=True)):
                if got['hit_rank'] != want['hit_rank']:
                    discrepancies.append(dict(engine=name, selected_index=index,
                                              replay_rank=got['hit_rank'], archived_rank=want['hit_rank']))
            for metric in ('recall_at_k', 'mrr_at_k', 'num_scored', 'search_errors'):
                if abs(actual[metric] - expected[metric]) > 1e-9:
                    discrepancies.append(dict(engine=name, metric=metric, actual=actual[metric], expected=expected[metric]))
            # Full-original denominator witness uses unchanged reporting over cached native rows;
            # this is not a claim of full PMID re-extraction.
            original_summary = recall_summary(copy.deepcopy(originals[name]['per_query']), None)
            for metric in ('recall_at_k', 'mrr_at_k', 'num_scored', 'search_errors'):
                if abs(original_summary[metric] - originals[name][metric]) > 1e-9:
                    discrepancies.append(dict(engine=name, full_cached_summary_metric=metric))
            engines[name] = {k: v for k, v in actual.items() if k not in ('per_query', 'latency')}
            engines[name]['per_query_hit_ranks'] = [q['hit_rank'] for q in actual['per_query']]
            engines[name]['full_archive_cached_summary'] = {k: original_summary[k] for k in
                                                           ('recall_at_k', 'mrr_at_k', 'num_scored', 'search_errors')}
        result = dict(scorer_revision=manifest['revision'], network='disabled', cohort='gold.ids.arxiv present',
                      num_queries=len(selected), excluded_pmid_tasks=len(raw_gold)-len(selected),
                      engines=engines, selected_engine_ultimate={k: v for k, v in replay['engines']['ultimate'].items()
                                                               if k not in ('per_query', 'latency')},
                      original_all_engine_ultimate=slim['engines']['ultimate'], discrepancies=discrepancies)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')
        return 2 if discrepancies else 0
    except (OSError, ValueError, KeyError, TypeError, ImportError, RuntimeError) as error:
        print(f'needle_replay: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
