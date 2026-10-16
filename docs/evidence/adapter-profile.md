# Acquired profile: needle-scholar-2026-10-14-v1

Packet A is `runs/2026-10-14T1506Z` at dataset revision
`fc40441e7d6d521dc2dbec7e46e76ed9ba1fe6f4`. Selection is the two latest
run-index entries containing both `scholar.json` and `scholar.jsonl`, with
A the earlier date and B reserved. Engine selection is the fixed list `bing`,
`keenable`, `perplexity`: small SERP artifact, named project engine, smallest
additional artifact in inventory. Selection used filenames/sizes, not scores.
B provider bytes are retained without JSON decoding or viewing.

## Actual fields and correspondence

`scholar.jsonl` is UTF-8 JSONL: `query_id`, `query_hash`, `query_text`,
`query_source`, `query_origin`, `gold`, `hour_ts`. The last two structured
columns `query_origin` and `gold` are themselves JSON strings, decoded once.
`gold.ids` holds scalar identifiers; `gold.paper_key` supplies source group;
`query_origin.bucket` is `title`, `body`, `clue`, or `tot`.
`hour_ts` is query generation time, not a request timestamp.

The slim report has `num_queries=384`, `num_results=10`, `snippet_chars=2000`,
and `engines.<name>.per_query_path`. Each selected engine file has
`per_query[]` with `query`, `paper_key`, `bucket`, `hit_rank`, `n_results`,
`results`, `search_error`, and `score`. Results contain `url`, `title`,
`snippet`, `ids`, `matched`. The join is the full tuple
`(query_text, gold.paper_key, query_origin.bucket)` to
`(query, paper_key, bucket)`, never query text alone. All 384 tuples and
query IDs are unique; all three arms have exactly 384 matching tuples in
identical order, with no orphan/duplicate/missing terminal rows. Task ID
is source `query_id`; assignment ID is `<engine>:<query_id>`.

This establishes run-local gold linkage through co-archival, the pinned
publisher's byte-copy rule, and exact 1:1 tuple correspondence. It is a
reconstructed intended manifest, not a collection-time dispatch manifest.
Repeated text in future packets is allowed only when full tuple remains
unique; ambiguous tuple joins are rejected rather than repaired.

## Selection and evidence limits

The supported baseline cohort is every row whose gold contains `arxiv`:
324 tasks, 81 paper groups, four buckets with 81 rows each. The 60 remaining
PMID tasks are retained in raw bytes and excluded explicitly because no
historical PMC-to-PMID conversion cache was archived. Result `ids` and
`matched` are cached derived fields, never independent conversion evidence.
No map is needed for this arXiv cohort. An available DOI in arXiv gold is
also matched literally. Full PMID replay remains unsupported until a
provenanced map is supplied; do not perform fresh online conversion.

Native entry point is unchanged `needle.scholar.score.run_papers`, which
calls `needle.shared.recall.run_known_item_eval`, `recall_summary`, and
`group_recall`. The replay supplies stored URL/title/snippet and error through
an in-memory SearchClient; cached IDs, matched flags, and ranks are discarded.
The bounded export uses the same raw join but independent literal matcher.

Native summary in pinned source includes every per-query row in `num_scored`,
including search errors; the all-error arm is the key denominator witness.
README exclusion prose is not the behavior of this revision. Exact values
and replay evidence are in native-baseline.md.

No physical attempt rows, task-linked latency, cost, request start/end,
endpoint credential choice, or actual request parameter logs exist. Sorted
`latency.samples_ms` are marginal and cannot be paired. Do not create
attempts from terminal rows. Exact attempt counts, paired latency, observed
cost totals remain null. The GitHub job bounds are workflow bounds, not
per-request times. Report settings establish k/count/snippet budget. Pinned
workflow/source support declared modes/retry defaults; actual overrides and
credential endpoint are not proven, and remain unknown. Retrieval comparison
is blocked until comparison-critical actual settings are evidenced.

The native synthetic `ultimate` is excluded from real assignments. Its
original all-engine ceiling remains in raw slim summary; selected-engine
replay produces a separately labeled subset ceiling. Original miss
classification depends on all engines and is not promised to match subset
replay. No live search, judgment, or automatic fallback is needed for the
supported archive cohort.

## Reference canonical shape

The declared canonical cohort contains 324 arXiv tasks and 972 assignments,
not all 384 tasks with synthetic unknown outcomes. Every excluded task ID
and source line is frozen in `fixtures/expected/packet-a-exclusions.json`.
The reference export follows spec section 5 task/assignment/outcome/result
fields. Source refs are strings `<source-id>#line=N` or
`<source-id>#$.per_query[I]`; `gold_ids` is namespace to sorted lists.
It copies every downloaded source byte to `raw/`; outcomes preserve returned
IDs for inspection but the oracle ignores them. `attempts.jsonl` is empty.
Reference `packet.json` adds `native_profile=needle-scholar-all-rows-v1` to
name the denominator proved here; this is a reference annotation, not a
new requirement for product schema. `hashes.json` freezes its bytes. This
bounded export is not a product freeze: it does not create SQLite, protocol,
or a general strict-schema validator. Task 2 should use the spec's full
contract and explicit source inventory, not treat this lightweight driver
as the finished importer.

The synthetic ten-assignment fixture stores ranked lists in all outcomes;
unknown judgment/missing match evidence is explicitly named in limitations,
with known dispatch evidenced by physical attempt records. The initial
reference experiment used null result lists; these were corrected to the
canonical list shape in a subsequent recorded RED/GREEN cycle. Native
metrics are unsupported on synthetic fixtures without a replay profile.
