# Reconciliation

Raw A: 384 gold tasks / 96 paper groups, 384 terminal rows in each of three
selected engines. Join keys and query IDs are unique; no duplicate, orphan
or missing terminal row exists. Every gold row is retained in raw evidence.
Canonical intended assignments explicitly select 324 arXiv tasks / 81 groups,
972 assignments; all 60 excluded PMID task IDs/reasons are frozen separately.
Each bucket contributes 81 selected tasks. Physical attempt ledger is empty,
because terminal rows cannot establish physical history.

`fixtures/expected/packet-a.json` freezes 20 independently inspected examples:
8 bing rows over the first two papers/four buckets; 4 keenable rows over the
first paper/four buckets; 4 real terminal 401 quota errors from perplexity;
2 later-rank bing hits; and 2 valid empty bing responses. Cached native flags
were available for inspection, but expected ranks were confirmed from literal
URL/title/snippet evidence and fixed by hand before oracle execution.
No expected outcomes are calculated with oracle/product/native helpers.

- First paper is arXiv `2610.18787`. Keenable's four first URLs contain that
  identifier under native arxiv.org forms, all rank 1. Bing's matching-title
  metadata and `papers.cool/arxiv/...` URL do not satisfy the pinned matcher;
  its four rows are misses. This does not establish index absence.
- Second paper is `2610.15184`. Bing title has rank-1 arxiv.org identity;
  its body/clue/tot responses lack a matching literal identity and are misses.
- Bing source index 73 (`356e89cadccd0272_2026-10-14T12`) first matches
  `https://arxiv.org/pdf/2605.26368v1` at rank 4; preceding URLs are nexusmods,
  convertico and Unity. Index 74 (`62a0b85d9d975283_2026-10-14T12`) first
  matches `https://arxiv.org/abs/2605.26368` at rank 2, after pager360.
- Bing indices 161 and 225 have actual `results=[]`, `n_results=0`, and
  `search_error=null`; these are known misses, not unknown records.
- Perplexity first four rows have actual terminal HTTP 401 quota-error
  evidence and no results; they are F. This is an operational failure in
  this archive, not evidence of inherent retrieval capability.

There are no real completed-unknown judgments or unknown terminal outcomes
in the selected source rows; that class is absent, not invented. Missing
conversion evidence is handled as explicit cohort exclusion. Known-dispatched
unknown outcomes are covered only by the hand-authored synthetic fixture,
never represented as real A cases.

All 20 fixed examples pass independent rank/state/result-count assertions.
The ten-assignment synthetic fixture independently establishes
N/H/M/F/U=10/4/2/1/3, delivered hit=0.4, bounds=[0.4,0.7], DOI/arXiv aliases,
first-hit rank, empty delivery and unknown evidence. The oracle reads direct
canonical JSONL, imports no product/native code, ignores returned IDs/ranks,
and computes matching and counts independently. Native metrics are only
supported when the reference packet names the native profile proved here.
