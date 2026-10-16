# Protected B release

B was released for Task 9 after the separate v2 protocol/corruption freeze at
`fca5ccd` and its recorded 20/20, 12/12 critical, 8/8 healthy results. The
original v1 10/20, 5/12 critical failure remains separately recorded in
[validation.md](validation.md). Product code, schema, profile, tests and
protocol have not changed for this import.

All five B files were copied byte-for-byte from the acquisition reservation
to `fixtures/real/packet-b`; lengths and SHA-256s match the original
`sources.json` and frozen `protocol.json` entries. Source registry paths and
roles now describe the released originals. The original acquisition command
and timestamp remain intact. The frozen B `protected: true` and
`outcomes_inspected: false` flags describe the state at protocol freeze;
this release record describes the later authorized inspection. Those policy
bytes were not edited to change history.

Before product import, the unchanged `reference/prepare_packet.py`, standalone
oracle and pinned native replay were run with B paths. The only B config edit
adds three explicit baseline source references. The new provenance entries
hash the resulting native, oracle and reconciliation sidecars with pinned
source parents. No raw row, product code, adapter rule, schema, profile or
policy edit was needed. Exact commands appear in
[sources.json](../../sources.json), and the full clean replay recipe follows
in the Task 9 reproduction handoff.

B has 384 raw tasks, 328 supported arXiv tasks, 82 groups, and 984 reconstructed
assignments across the three selected arms. The 56 excluded PMID tasks remain
in raw evidence and [the derived exclusion sidecar](packet-b-exclusions.json).
The independent/native comparison checks every one of 984 selected ranks
exactly and native count/error/recall/MRR metrics within absolute `1e-9`, with
zero discrepancies ([check](packet-b-reference-check.json)). Every product
reference check passes. Freeze exits 0; evaluate and report exit 3 with
qualified artifacts because the requested Bing/Keenable pair is blocked by
unknown actual settings, retry policy and comparison window. Each arm remains
`descriptive_only` without purchasing thresholds. No physical attempts or
cost receipts are invented.

| B arm | N | H | M | F | U | Native recall@10 | Native MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bing | 328 | 155 | 173 | 0 | 0 | 0.4725609756097561 | 0.4363313008130081 |
| keenable | 328 | 273 | 55 | 0 | 0 | 0.8323170731707317 | 0.7935031939605108 |
| perplexity | 328 | 248 | 80 | 0 | 0 | 0.7560975609756098 | 0.6480860433604335 |

These descriptive archive observations are separate from A's cohort and
cannot establish a fair provider comparison or general retrieval quality.
The deduplicated cross-packet engineering inventory is 649 query identities
and 160 source groups; [coverage.json](coverage.json) defines identities and
retains overlap source references. A and B metrics are never pooled.

The pre-commit full suite ran 190 tests, all passing with no skips; console
output is retained in [workspace-suite-console.txt](reproduction/workspace-suite-console.txt).
