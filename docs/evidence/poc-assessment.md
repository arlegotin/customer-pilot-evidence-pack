# PoC assessment

**Workflow result: neutral.** The supported real-data accounting/replay path
works for both packets and reproduces offline, but the independently run
baseline already accepts B with generic path/configuration arguments. Both
have zero B-specific bespoke conversion/analysis actions and zero source-row
edits. The required reduction is absent. This is evidence for reuse of the
thin accounting/validation boundary, not a positive efficiency, adoption or
commercial claim.

| Acceptance item | Actual result | Evidence |
| --- | --- | --- |
| Real unchanged source packets and lineage | A/B originals committed; all reserved lengths/hashes match; no manual row changes | `sources.json`, [B release](packet-b-release.md) |
| B configuration-only import | Passed using frozen adapter/schema/profile/product/tests/policy; only existing config/provenance shape completed | `9474fdd`, [B release](packet-b-release.md) |
| Supported native and independent reference agreement | A972 and B984 exact selected ranks/counts; max metric difference `2.220446049250313e-16`, below absolute `1e-9`; all product reference checks passed | [replay results](reproduction/results.json), [A check](reference-check.json), [B check](packet-b-reference-check.json) |
| Known logical accounting and unavailable physical history | A324 and B328 reconstructed assignments per arm; no lost selected rows; zero observed physical rows, exact totals null, missing costs unavailable | Fresh oracle/evaluation and retained raw sources |
| Protected validation | v2:20/20 total,12/12 critical,8/8 healthy with0 unexpected; earlier v1:10/20 and5/12 critical remains a failed attempt | [validation.md](validation.md) |
| Two packets and engineering counts | A324/81, B328/82;3 repeated query identities/3 repeated groups; deduplicated total649 queries/160groups, above200/50 | [coverage.json](coverage.json) |
| Clean offline replay | Passed from committed `9474fdd`; fresh pinned checkout/native environment from hashed retained tar/wheels; no old run/output/database/environment copied; inherited child network guard | [reproduction.md](reproduction.md), [export inventory](reproduction/input-export.json) |
| Stable equality | Canonical records, normalized ledger digest/records, all non-SQLite run bytes, complete evaluation/diagnostic/verdict/report bytes and fresh reference bytes identical | [results.json](reproduction/results.json) |
| Full suite in clean directory |190 tests,0 failures/errors/skips; native baseline test executed | [clean console](reproduction/clean-suite-console.txt) |
| Real comparative purchasing conclusion | Blocked as required: actual mode/endpoint/parameters/retry/timeout/concurrency/window missing; no provider winner; all arm decisions descriptive_only without thresholds | Both fresh evaluations/verdicts; evaluate/report exit3 |
| Human/browser smoke | Unperformed; automated offline/HTML safety checks pass, visual usability unassessed | Task7 limitation retained |
| Material workflow improvement | Not demonstrated: existing baseline and pack both0 bespoke B actions; no reduction | [workflow ledger](workflow-comparison.md) |

The positive/neutral/negative/unassessed classification is separate from
customer arm decisions and comparison eligibility:

- **Positive:** not established. It requires correctness plus zero row edits,
  zero B-specific code, and fewer bespoke conversion/analysis actions. The
  measured baseline ties the pack; human/browser smoke also remains open.
- **Neutral:** the measured preparation/replay comparison. Correct supported
  evidence can be regenerated, but the required preparation reduction is
  absent. A's one-time driver/exporter/oracle work cannot be charged again
  to B merely to make the pack appear more efficient.
- **Negative:** no specified incorrect-conclusion failure was observed in
  v2 or these real replays. Failed v1 validation remains explicitly
  negative evidence about that earlier frozen attempt. Unsupported settings,
  costs, missingness and leakage are not silently turned into favorable
  conclusions; this is bounded observation, not proof of universal safety.
- **Unassessed:** human/browser usability, customer/internal workflow
  duplication, business/adoption value, actual time savings, exact physical
  request efficiency/cost and task-paired latency, full PMID re-extraction,
  and answer/citation quality. Real provider purchasing comparisons remain
  ineligible on the available archive evidence.

A and B use the same supported archive/profile but different cohorts. Their
metrics are retained separately; the deduplicated coverage union is not a
pooled provider experiment. Archive exclusions (A60/B56), selection, quota
failures and absent historical conversion evidence limit generalization.
The counts are engineering coverage targets, not a power calculation, and
this demonstration cannot resolve tiny provider differences. Missing
collection-time settings, retry histories, cost receipts and linked latency
cannot be supplied from documentation defaults. No cost or settings were
invented, no live searches/judgments occurred, and no paid APIs were used.

The original A Task1 oracle is preserved unchanged; current oracle outputs
add only the later physical-attempt lower-bound field relative to that
historical sidecar, and every original retained field agrees. Current
first-execution versus clean output equality is exact. The unchanged
native denominator includes provider failures at this pinned revision;
full384-task cached summary agreement is not full PMID extraction replay.

The result completes the measured Task9 import/replay/assessment work with
these qualifications. It does not establish a generally successful customer
pilot or justify broadening the project beyond the thin supported boundary.
