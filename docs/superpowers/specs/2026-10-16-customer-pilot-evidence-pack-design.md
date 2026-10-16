# Customer Pilot Evidence Pack — PoC specification

Date: 2026-10-16

Status: Proposed design; implementation is outside this documentation task.

Audience: Keenable technical GTM, product, and a customer reviewing a pilot.

## 1. Purpose and evidence boundary

Turn a frozen evaluation packet into an auditable local evidence report. Preserve intended work, observed requests, failures, unknown outcomes, settings, and the conditions under which a comparison is supported. Immediate value is reproducibility and less bespoke preparation; better pilot conversion and revenue effects remain hypotheses.

An individually correct evaluation can still mix workloads, modes, evidence budgets, retries, and incomplete judgments or costs. This tool adds decision accounting around existing measurements. It does not introduce a novel estimator or presume a favorable provider result. It retains the seed proposal's failure-inclusive accounting and strong baselines without making novelty the objective.

The supplied brief is the requirements input. The following are design choices made for this proposal, rather than additional user commitments:

- Start with NEEDLE Scholar known-item retrieval only; support one frozen archive schema/profile, plus canonical JSONL.
- Use Python 3.11+ and its standard library for the delivered tool and tests.
- Treat unknown purchasing thresholds as unset; issue evidence and eligibility findings rather than inventing a winner.
- Use the first completed response under a frozen retry policy as the logical delivery, not the best response across retries.
- Use 2,000 grouped bootstrap replicates, seed 0, and a 95% percentile interval when the prerequisites below hold.
- Freeze 20 non-equivalent corruption cases and eight healthy controls before evaluating the protected packets.

## 2. Scope, non-goals, and stop conditions

Deliver one NEEDLE raw-run adapter, one documented canonical importer, immutable assignment and physical-attempt accounting, deterministic known-item scoring, an independent reference implementation, comparison gates, `verdict.json`, and escaped static `report.html`.

Required files include `pilotpack/{schema,ingest,ledger,score,report,cli}.py`, `pilotpack/__init__.py`, `pilotpack/__main__.py`, `reference/oracle.py`, `tests/`, `fixtures/`, `protocol.json`, and `sources.json`. Small additional files may separate comparison logic and upstream replay from scoring.

Global constraints:

- Python 3.11+; production runtime and tests use the standard library only.
- Evaluation and reporting are local and offline after acquisition.
- No paid APIs, model-generated judgments, hosted application, customer-data upload, routing, new ranking algorithm, or new agent framework.
- Missing cost remains missing; retrieval metrics never become claims about agent answer quality.
- Raw inputs, protocol, and normalized ledgers are immutable within a frozen run.
- Synthetic corruption artifacts remain separate from original evidence.
- Work stays on the current branch unless the user later requests otherwise.

This tool does not execute a general benchmark. A future runner can emit the canonical format. A bounded keyless acquisition fallback, if needed, is a separate recorded experiment using existing tools.

**Gate before product implementation:** reproduce one actual packet using unchanged NEEDLE reporting and a small independent Python/SQL baseline. If an existing workflow already produces the same complete, reproducible packet through configuration alone, stop duplication and deliver a documented reuse recipe or thin adapter only. If real task-level evidence and the bounded keyless fallback are unavailable, stop provider-verdict claims. A schema/report demonstration may still be labeled synthetic and cannot satisfy real-data acceptance.

## 3. Research status and acquisition contract

The repository was empty at planning time. No real packet, immutable upstream revision, raw-data hash, or baseline result has been acquired in this change.

The [NEEDLE README](https://github.com/keenableai/needle) documents a public full-artifact archive and the exclusion of failed searches/judgments from relevant scored means with errors reported separately. This is not evidence that a particular archive contains a complete assignment or retry history. The [archive tree](https://huggingface.co/datasets/keenable-ai/needle-results/tree/main/runs) is accessible; its listing alone does not establish completeness.

The inspected [Scholar scorer](https://raw.githubusercontent.com/keenableai/needle/main/src/needle/scholar/score.py) uses paper identifiers and can perform identifier conversion. The inspected [shared recall code](https://raw.githubusercontent.com/keenableai/needle/main/src/needle/shared/recall.py) supplies summaries and a synthetic `ultimate` engine. These mutable pages were inspected for planning, not frozen as the evaluation baseline. A README description is insufficient to choose the denominator of a particular revision: inspect and replay the pinned implementation, preserve its exact behavior, and report any discrepancy explicitly.

The inspected [search client](https://raw.githubusercontent.com/keenableai/needle/main/src/needle/shared/search/base.py) can retry and publishes sorted latency samples. Consequently, a terminal result row is not proof of one physical request, and sample positions cannot establish query pairing. The [CI workflow](https://raw.githubusercontent.com/keenableai/needle/main/.github/workflows/bench.yaml) identifies candidate gold and report artifacts; the implementation must verify the matching run and revision.

Day 1 acquisition must:

1. Select packet A for development and reserve packet B as a protected second import. Inspect B's inventory/format metadata only until the protocol and corruption suite are frozen. Select by completeness and compatible format, never provider score.
2. Acquire matching gold, selected task/assignment evidence, every selected real engine's task-level outputs, original summaries, run settings, run window, scorer code revision, and any identifier-conversion evidence used by the scorer. Download selected artifacts, not the whole archive.
3. Pin full source/dataset revisions, immutable URLs where available, acquisition times in UTC, byte lengths, SHA-256 hashes, licenses, and exact commands. Prove that gold belongs to the run; a current rolling gold file is insufficient.
4. Reconcile 20 named examples spanning available buckets, hits, misses, and error/unknown cases. If an error class is absent, record its absence rather than inventing real evidence.
5. Document the actual JSON paths, task join keys, duplicate-query behavior, selection rules, native scorer entry points, denominator, retry evidence, and unsupported fields in `docs/evidence/adapter-profile.md` before coding the adapter. This is a gate deliverable, not permission to infer source fields.
6. Run unchanged pinned NEEDLE scoring/reporting over frozen results without new searches or judgments, using an offline replay driver if required. Freeze the driver, upstream checkout/license, environment lock, and output. Upstream dependencies belong to a separate baseline environment; retain local dependency artifacts needed for its offline replay.
7. Run the independent baseline and record differences. Missing evidence may mark a native metric unsupported; it must not be reconstructed by guessing.

Target two compatible real packets totaling at least **200 distinct queries and 50 distinct source groups**. Count queries once across providers and deduplicate repeated identities across packets. These are engineering coverage targets, not power calculations. Packet B need not have A's cohort; each packet must support its own intended comparisons. Cross-packet provider comparisons require the same gates as within-packet comparisons.

Fallback: if archive acquisition fails, use at most 20 already available public identifier tasks and at most one keyless request per task, with no automatic retry and no paid key. Freeze the assignment manifest and retry/timeout settings before sending; record each physical attempt and dispatch failure. Discover and verify the existing keyless interface first. Do not generate gold through an LLM or claim a one-provider fallback supports a provider comparison. If this cannot be done, record the stop condition.

## 4. Architecture and artifacts

```text
frozen source + protocol + provenance
  -> strict schema validation and explicit reconciliation
  -> canonical task, assignment, outcome, physical-attempt records
  -> SQLite ledger (transactional, append-only)
  -> deterministic score + independent oracle + native replay check
  -> comparison gates, missingness, grouped uncertainty, case records
  -> verdict.json + report.html
```

The immutable run directory is the unit of replay:

```text
RUN/
  raw/                       original downloaded bytes, unchanged
  sources.json               provenance entries for every raw/baseline artifact
  protocol.json              frozen policy and per-arm comparison settings
  packet.json                schema version, adapter profile, manifests/hashes
  tasks.jsonl                query and gold identities
  assignments.jsonl          intended logical tasks per arm
  outcomes.jsonl             terminal logical observations / reconciliation
  attempts.jsonl             evidenced physical requests only
  identifier-map.json        optional frozen conversion map, provenance required
  ledger.sqlite              normalized records and import diagnostics
```

Derived output goes to a separate `OUT/` directory containing `verdict.json`, `report.html`, and `evaluation.json` (case records and unrounded intermediate metrics). Never rewrite a frozen run to repair it; issue a new run identity with its parent and transformation history. SQLite bytes need not match across platforms; normalized records, metrics, diagnostics, and verdict must.

## 5. Versioned data contracts

Canonical schema version is integer `1`. JSONL is UTF-8, one JSON object per nonblank line; reject blank lines, duplicate JSON keys, NaN/Infinity, unknown core fields, and invalid types. Optional extension data lives under `extensions`. Error messages include relative file, line/JSON path, and stable diagnostic code. Reject a whole import transaction on structural corruption; do not skip rows or silently deduplicate.

`packet.json` declares `run_id`, `schema_version`, `adapter_profile`, `origin` (`archive` or `new_run`), `assignment_basis` (`predeclared`, `reconstructed`, or `unreconstructable`), `intended_count` per arm when known, source-evidenced `actual_settings` per arm, `attempt_history` (`complete`, `partial`, or `unknown`) per arm, and hashes for canonical/raw files and the protocol. Claimed exact counts must be supported by complete request evidence. Reconstructed assignments require explicit evidence and a reconciliation note; their existence is not evidence of dispatch.

| Record | Required core fields and rules |
| --- | --- |
| Task | `task_id`, `source_group_id`, `cohort_id`, `query_text`, `gold_ids` (namespace to sorted identifiers), `bucket`, `source_ref`. Identity comes from source IDs or a documented content digest including group, bucket, and query. Equal query text alone is not a join key. |
| Assignment | `assignment_id`, `task_id`, `arm_id`, `settings_id`, `source_ref`. Exactly one per intended `(task_id, arm_id)` in the cohort. Assignment identity never changes with retries. |
| Outcome | `assignment_id`, `observation_kind` (`attempt_backed`, `archive_logical`, `unobserved`, `not_dispatched`), `terminal_status` (`completed`, `provider_error`, `unknown`, `runner_failure`), `selected_attempt_id` or null, `results` (ranked list), `reported_hit_rank` or null, `source_ref`, `limitations`. One per assignment, synthesized missing records explicitly labeled. |
| Attempt | `attempt_id`, `assignment_id`, `attempt_index` (1-based), `started_at`, `ended_at`, `status` (`completed`, `provider_error`, `unresolved`), `results`, `error`, `latency_ms`, `cost`, `source_ref`. Only real evidenced requests enter this ledger. |
| Result | `rank` (contiguous, 1-based), `url`, `title`, `snippet`, `returned_ids`. Preserve response order and repeated results. Do not rerank or apply deduplication absent from the frozen native scorer. |
| Cost | `amount` (nonnegative decimal string or null), `currency` or null, `kind` (`observed`, `estimated`, `missing`), `source_ref` or null, `scope` (`attempt` only in v1). Known zero requires evidence. Estimated cost never supplies an observed total. |

Nullable attempt timestamps, latency, and cost must have a limitation explaining missing evidence. Present timestamps are UTC RFC 3339 with a zone; `ended_at >= started_at`; latency is finite and nonnegative. Do not infer request latency from wall-clock bounds or assign aggregate samples to tasks. Complete new-run attempts require both timestamps. No attempt is created for an assignment never dispatched.

Arm settings include provider, exact mode/endpoint, query/operator parameters, requested result count, scoring `k`, snippet-character cap, retry policy, timeout, concurrency, run window, and scorer/matching profile. `snippet_chars=0` means no cap and is distinct from an unknown budget. Require `1 <= k <= requested_num_results`; returned result count is separately recorded as the actual list length. Unknown fields use null plus a limitation, never default values masquerading as observations.

`sources.json` lists source IDs, artifact roles, source URI, immutable revision or documented absence, acquisition timestamp, relative local path, bytes, SHA-256, license, and transformation parents/commands. Every `source_ref` resolves to source ID plus line/object path; generated reconciliation rows identify the inference and its evidence. Resolve all paths under the run root and reject traversal, escaping symlinks, and duplicate IDs.

`protocol.json` fixes schema/profile versions, arm settings, cohort membership/selection, assignment basis, `k`, retry selection, matching and optional conversion-map hash, comparison window, bootstrap seed/replicates/interval, corruption manifest hash, and optional decision thresholds. Defaults proposed here are explicit protocol values, not hidden code defaults. Freeze it before protected evaluation; revisions create a new protocol identity. New-run assignments must be demonstrably frozen before the earliest dispatch. A hash only attests to the supplied bytes; it does not independently prove collection-time truth.

Compute `content_id` as SHA-256 of the sorted relative-path/byte-hash map for raw inputs, canonical JSONL, conversion map when present, sources and protocol. Exclude `packet.json`, SQLite and derived outputs to avoid self-referential hashes. `packet.json` carries this identity and the canonical normalized-table digest; verify the latter when opening SQLite. Stable serialization uses sorted object keys, compact separators, UTF-8, finite numbers, a final newline, and records sorted by their identity. Preserve original JSONL order in raw bytes and result order within records.

## 6. Assignment, attempt, and scoring semantics

The ledger uses separate tables for tasks, assignments, outcomes, attempts, results, sources, and diagnostics. Foreign keys, unique keys, and insert-only triggers protect accounting. Import is all-or-nothing. Derived scores are computed separately and do not update source rows. Reopening a run verifies its recorded content digest, so direct database modification is detected as well as rejected through normal writes.

An archived terminal row can support an `archive_logical` observation while physical attempts remain unknown. Report observed physical rows, a supported lower bound if dispatch is evidenced, and `physical_attempt_count_exact=null` when history is incomplete. Never equate terminal rows with exact requests. Exact accounting means every source record is retained or explicitly rejected/classified, every known intended assignment is represented, and missing history is disclosed; it does not mean fabricating unavailable history.

For new runs, choose the lowest-index completed response under the frozen retry policy, including an empty result list or a response whose score is unknown. Earlier failed attempts remain in the attempt ledger. All terminal provider errors under that policy yield non-delivery. Interrupted retry sequences, ambiguous terminal rows, and contradictory outcome/attempt records are diagnosed; no best-of-retries selection. Archives retain their native logical selection only when its policy can be established; otherwise comparison eligibility is blocked.

For each arm at a fixed `k`, partition intended assignments:

| Symbol | Meaning | Contribution |
| --- | --- | --- |
| H | Completed delivery with a confirmed gold identifier in the first k results | Known hit |
| M | Completed delivery with sufficient evidence to establish no match in the first k results, including a valid empty response | Known miss |
| F | Evidenced terminal provider failure/non-delivery | Known non-hit |
| U | Outcome not evaluable, including unavailable evidence, unresolved dispatch, unknown judgment, or an explicit runner non-dispatch | Unknown |

When N is known, `N = H + M + F + U`, `delivered_hit_at_k = H/N`, and `missingness_range = [H/N, (H+U)/N]`. Report U subcounts for `completed_unknown`, `missing_record`, `unresolved_dispatch`, and `runner_not_dispatched`. A known provider error is F, not U. A completed request with no usable judgment is U, not M. An identifier-free but otherwise complete Scholar result is M under the pinned matcher, with its evidence-limit caveat; an absent/corrupt result record is U or a structural fault, not an empty response.

Example: N=10, H=4, M=2, F=1, U=3 produces 0.4 and [0.4, 0.7]. If one unknown is an undispatched task, retain those numbers but block the provider comparison. For N=0, metric/range are null with `EMPTY_COHORT`; never divide by zero. If N cannot be reconstructed, intended-denominator metrics are null with `UNKNOWN_ASSIGNMENT_BASIS`; observed rows may be shown descriptively.

Preserve native names, values, support status, denominators, and native error counts in a separate `native_metrics` object. Reproduce exactly the pinned implementation's supported conditional recall/hit and MRR behavior; do not apply the delivered denominator to native metrics. Where the native profile genuinely excludes failures, conditional hit is H divided by native scored assignments; native MRR uses that same eligible set. Do not assert this formula for a revision until its replay establishes it. A zero-scored native convention may be zero while the pack's undefined delivered metric remains null.

The production matcher uses the pinned Scholar extraction/normalization rules over the same URL/snippet evidence and budget. Rank of the first matched gold identifier determines hit and reciprocal rank. Frozen conversion maps may be used; no live identifier lookup during evaluation. Keep reported native scores alongside recomputed values and diagnose disagreement rather than trusting cached `matched` or `hit_rank` flags. Exclude synthetic `ultimate` from real-provider assignments, cost, pairing, and verdicts; retain its native ceiling separately.

The independent oracle reads frozen canonical JSONL directly, imports no `pilotpack` modules or native scorer, and independently computes normalized-ID rank matches, assignment partitions, denominators, and supported MRR. Verify production extraction with pinned native replay and independent literal URL/snippet identifier cases, not only shared pre-extracted IDs. Freeze expected extraction examples before running protected packets. Agree exactly on counts/IDs and within absolute `1e-9` on applicable numeric metrics. Disagreement is a blocking finding, not an average to smooth away.

## 7. Comparison gates and uncertainty

Comparison units are explicitly named arms, not provider names alone. A pro/auto/realtime difference may be the intended treatment: the protocol declares each arm's exact mode. Do not require differently named providers to expose identically named modes; do reject actual settings that differ from their declarations.

| Gate | Required behavior |
| --- | --- |
| Integrity and reconciliation | Hash/schema/reference mismatches, duplicate identities, orphan rows, or irreconcilable assignments block affected comparisons. |
| Intended cohort | Both arms have the same frozen task IDs, query/gold versions, groups, and selection policy. No silent intersection or row dropping. Different packets/cohorts get separate summaries. |
| Comparison conditions | Common k, requested count, snippet cap, frozen matching profile and map, temporal window, and declared evidence policy; exact per-arm mode, parameters, retry, timeout and concurrency must match protocol. Unknown comparison-critical settings block comparison. |
| Dispatch | Any known runner non-dispatch or unexplained missing outcome blocks a provider comparison, while preserving the ledger and descriptive bounds. |
| Metric support | Gold, scorer evidence, assignment denominator and native/oracle agreement must be established. Unsupported metrics remain null with reasons. |
| Physical history | Missing exact retry history blocks exact attempt totals, total cost, and request-efficiency claims. It need not block retrieval if logical selection/retry policy and the other conditions are supported. Unknown retry policy blocks retrieval comparison too. |
| Latency | Only task/attempt-linked observations support paired latency. Sorted arrays and summaries are marginal only, labeled with their native eligibility set. |
| Cost | Total observed request cost requires complete physical history, all attempts covered by observed cost of one currency and consistent scope. Otherwise total is null; show known subtotal and coverage. Never claim total agent cost. |

Provider failures are an outcome, not a reason to exclude an assignment or automatically block a fair comparison. Completed unknown judgments can leave a comparison qualified by missingness bounds if dispatch and cohort evidence are intact. Store gates with stable code, scope (run/arm/pair/metric), severity, source references, and explanation. An intentionally incomplete archive receives expected limitations, not fabricated schema errors.

For eligible paired arms with equal N, report the observed delivered difference and the missingness identification range:

`[H_A/N - (H_B+U_B)/N, (H_A+U_A)/N - H_B/N]`.

This is a range from unknown outcomes, not a confidence interval. If either arm has U>0, show it and suppress the v1 paired bootstrap with a reason. If U=0 in both arms and group IDs exist, resample source groups uniformly with replacement, keeping every query variant and both arms together. Recompute the query-weighted delivered difference for each sample; do not average group rates. Use 2,000 replicates with seed 0, sorted stable group IDs, and nearest-rank 2.5th/97.5th percentiles (`ceil(p*B)-1`, clamped). Record Python version, group/query counts, seed, replicate count, and estimand. Fewer than two groups makes the interval unavailable. Counts below the 50-group engineering target carry an explicit small-group qualification, not a fictitious precision guarantee. No p-value or automatic winner is required.

## 8. Verdict and HTML behavior

`verdict.json` version 1 contains run/protocol/content identities; source inventory; accounting and reconstruction status; per-arm H/M/F/U and subcounts; native and delivered metrics; attempt/cost/latency availability; pair gates and intervals; reference checks; diagnostics; limitations; and `decisions` keyed by arm ID. `evaluation.json` contains inspectable per-assignment outcomes, selected response/rank, all evidenced attempts, and source locations.

Use independent fields for evidence eligibility and decision:

- Each pair has `comparison_status`: `eligible` or `blocked`, with scoped reasons.
- Each arm has `decision_status`: `descriptive_only`, `not_evaluable`, `meets_criteria`, `fails_criteria`, or `indeterminate`. There is no run-wide decision status or automatic winner.
- `protocol.decision_criteria` maps arm IDs to optional thresholds; absent/empty criteria mean descriptive reporting for that arm. Unknown arm IDs are invalid. An arm with unsupported accounting/scoring or an arm-level blocking gate is `not_evaluable` regardless of thresholds.
- Optional `min_delivered_hit_rate` is evaluated conservatively: lower bound at/above threshold meets; upper bound below threshold fails; overlap is indeterminate. Optional `max_provider_failure_rate` and `max_unknown_rate` use exact F/N and U/N. Combine an arm's criteria: any known failure fails; otherwise any unknown is indeterminate; all met means meets. Cost thresholds are outside v1.
- A pair-only cohort/settings block prevents a comparative conclusion even if an arm independently meets its absolute criteria. Display that block alongside the arm decisions; never collapse these into a favorable combined verdict. A valid result with no thresholds is `descriptive_only` and is not a purchasing recommendation.

The PoC's **workflow assessment** (`positive`, `neutral`, `negative`, `unassessed`) is a separate validation artifact, not the customer decision field. Positive means acceptance plus the preparation reduction below; neutral means correct but little workflow benefit; negative means incorrect conclusions from missingness, incompatible conditions, leakage, or unsupported costs. Acquisition/validation not performed is unassessed.

Static HTML opens locally with no server, external requests, scripts, fonts, or assets. Escape every imported text/attribute; permit clickable result URLs only for `http`/`https`, otherwise render text. Avoid embedding untrusted JSON in executable contexts. Display provenance and qualifications before comparisons, then native vs delivered metrics, comparison settings/gates, attempt/cost availability, and inspectable case records including failures and unknowns. Make all evidence accessible without JavaScript.

Every report states: retrieval is not answer quality or citation support; a miss does not prove index absence; missingness bounds are not confidence intervals; the demonstration is too small to resolve tiny provider differences. Case text does not assign a causal explanation absent evidence.

## 9. CLI and replay contract

Planned commands (these do not exist in the documentation-only change):

```bash
python -m pilotpack freeze --adapter needle-scholar --input fixtures/real/packet-a --config fixtures/config/packet-a.json --protocol protocol.json --sources sources.json --out runs/packet-a
python -m pilotpack freeze --adapter canonical --input fixtures/canonical/healthy --config fixtures/config/canonical.json --protocol protocol.json --sources sources.json --out runs/canonical
python -m pilotpack evaluate --run runs/packet-a --out build/packet-a
python -m pilotpack report --run runs/packet-a --evaluation build/packet-a/evaluation.json --out build/packet-a
python reference/oracle.py --run runs/packet-a
python -m unittest discover -s tests -v
```

`freeze` validates, reconciles, copies source bytes, creates canonical files and a transactional SQLite ledger, and refuses an existing destination. `evaluate` verifies the frozen run and produces evaluation plus verdict atomically. It invokes the independent oracle through its standalone interface and records the native replay check against frozen baseline artifacts. `report` verifies evaluation/run/protocol identity before rendering and does not rescore. Never leave successful-looking partial output after failure.

Exit codes: 0 for successful artifact generation with all requested comparisons eligible (or no pair requested); 2 for invalid input/integrity/reference/structural failure; 3 for an emitted qualified report/verdict with a requested comparison blocked. A customer threshold failure is a valid result and does not change the exit code. Expected archive limitations can return 0 when they do not affect a requested comparison. Diagnostics use stderr; machine-readable verdicts remain files. Repeated evaluation into the same output directory is allowed only for the identical run/protocol and replaces derived files atomically.

## 10. Frozen validation protocol

Use hand-sized canonical cases to prove semantics, then packet A, then frozen protected copies and packet B. Freeze protocol, expected results, mutation recipes, and hashes before protected evaluation. Tests of product behavior use `unittest`; the unchanged NEEDLE baseline may require its isolated pinned environment.

Freeze this set of 20 non-equivalent corruptions. A detection means the specified fault is rejected or given the specified blocking/unsupported state with a stable code; an unrelated parse error does not count. For downstream semantic mutations, rehash the mutated copy consistently so the test reaches the intended gate. Keep one explicit raw-byte/hash mutation to test provenance. Every case has a parent packet hash and expected finding.

| ID | Mutation | Required finding | Critical |
| --- | --- | --- | --- |
| C01 | Alter raw bytes without updating provenance | `HASH_MISMATCH` | Yes |
| C02 | Duplicate assignment identity/logical task | `DUPLICATE_ASSIGNMENT` | Yes |
| C03 | Add orphan outcome/attempt | `ORPHAN_RECORD` | Yes |
| C04 | Remove one outcome from an intended cohort | Explicit U plus `MISSING_OUTCOME`, pair blocked | Yes |
| C05 | Substitute another gold/cohort version for one arm | `COHORT_MISMATCH` | Yes |
| C06 | Change one arm's actual k/result count from protocol | `SETTINGS_MISMATCH` | Yes |
| C07 | Change actual snippet budget from protocol | `SETTINGS_MISMATCH` | Yes |
| C08 | Change actual provider mode/endpoint from protocol | `SETTINGS_MISMATCH` | Yes |
| C09 | Mark an intended task not dispatched | U, no attempt, `RUNNER_FAILURE`, pair blocked | Yes |
| C10 | Supply a forged cached hit/rank inconsistent with evidence | `REFERENCE_MISMATCH` | Yes |
| C11 | Substitute a better retry for the policy-selected response | `RETRY_SELECTION_MISMATCH` | Yes |
| C12 | Set missing cost to observed zero without provenance | `INVALID_COST_PROVENANCE` | Yes |
| C13 | Supply latency only as sorted marginal samples but request pairing | `UNPAIRED_LATENCY`, paired latency null | No |
| C14 | Omit physical retry history but claim an exact attempt count | `UNKNOWN_ATTEMPT_HISTORY`, exact total null | No |
| C15 | Mix observed cost currencies/scopes while requesting a total | `INCOMPLETE_COST`, total null | No |
| C16 | Move a run outside the protocol's comparison window | `TIME_WINDOW_MISMATCH` | No |
| C17 | Remove a required identifier conversion map | `MISSING_MATCH_EVIDENCE`, affected metric unsupported | No |
| C18 | Introduce duplicate JSON keys or nonfinite numbers | `INVALID_JSON` | No |
| C19 | Point a source path outside RUN, including an escaping symlink | `UNSAFE_SOURCE_PATH` | No |
| C20 | Give a new-run manifest a time after its first dispatch | `MANIFEST_AFTER_DISPATCH` | No |

Eight healthy controls: complete hit/miss/error accounting; completed unknown judgment with intact dispatch; documented unknown archive attempt history; missing cost; a genuine observed zero cost with provenance; reordered JSON objects/independent record lines; repeated query text with distinct identities; legitimate declared per-arm modes with a native `ultimate` ceiling. Each control defines expected limitations explicitly. Healthy means no unexpected faults or comparison blocks; expected unsupported cost/attempt fields are not false alarms. Unknown outcomes must never be silently converted to irrelevant results.

Additional direct tests cover native conditional-vs-delivered denominators, k boundaries, empty cohorts, wholly missing assignment basis, duplicate result ranks, identifier aliases and snippet clipping, missing group IDs, grouped resampling, mixed timezones/negative durations, HTML injection/unsafe links, repeat import, content modification through SQLite, output identity mismatch, and interrupted output writes. Security tests verify safe local rendering without introducing a hosted security subsystem.

Acceptance requires:

- Exact known assignment/attempt accounting and explicit unavailable history; no silent source-row loss.
- Native supported-metric and independent-oracle agreement within absolute `1e-9`; exact counts and identities.
- All 12 critical faults detected; at least 18/20 total frozen corruptions detected; all eight healthy controls have no unexpected findings. An undetected noncritical case is disclosed, never removed from the denominator.
- Real-data end-to-end import/report and clean offline reproduction with identical canonical records, metrics, verdict, and report bytes in the recorded Python environment. Volatile execution timestamps belong in separate logs, not deterministic outputs.
- Two real compatible packets, with the 200-query/50-group target either attained or explicitly marked unmet. A fallback does not satisfy this target.
- Packet B imports using the frozen adapter and configuration changes only. New code or manual row repair for B fails this condition; disclose any protocol revision and restart protected evaluation rather than claiming success.

Record exact commands, bespoke transformations, manual row edits, and packet-specific code for the existing workflow and the pack in `docs/evidence/workflow-comparison.md`. Count required conversion/analysis actions separately from download/setup commands. Proposed material reduction: B needs **zero manual row edits, zero packet-specific code, and fewer bespoke conversion/analysis actions** than the independently recorded existing baseline for B. Configuration edits and commands are still listed. This operationalizes workflow value without claiming measured human-hours saved. A baseline already meeting these conditions triggers the reuse/neutral outcome.

## 11. Four-day delivery sequence

| Day | Deliverable and exit condition | Risk and bounded response |
| --- | --- | --- |
| 1 | Packet A frozen; B reserved; actual adapter profile written; 20 examples reconciled; unchanged NEEDLE and independent baseline reproduced; duplication/acquisition gate decided. | Incomplete archive: try the recorded 20-task keyless fallback. No complete evidence: stop provider-verdict claims. Existing adequate workflow: reuse it. |
| 2 | Canonical contract, one archive importer, immutable ledger, deterministic scoring and basic offline report work end to end. | Keep one Scholar profile; do not grow to every suite. |
| 3 | Protocol, expected outputs and 20-case suite frozen; protected evaluation, gates, and grouped comparison checked. | Identifier ambiguity stays unsupported; do not introduce a model judge. |
| 4 | Packet B through configuration only; clean-directory offline reproduction; limitations, workflow comparison, demo and PoC assessment. | Little incremental value: deliver a thin adapter/reuse recipe and report neutral. |

Largest technical risk is incomplete/inconsistent archived evidence. Largest business assumption is that preparation and review still involve meaningful bespoke work. Internal duplication is unknown. Bounded completion and an engineering accounting evaluation are high-confidence conditional on complete evidence; useful workflow improvement and Keenable value remain to be demonstrated.

## 12. Handoff decisions and unresolved facts

No product implementation is authorized by this document-writing task. The linked implementation plan will sequence tests, code, checks and commits for a later execution request.

Day 1 must resolve source facts rather than ask the builder to invent them: matching packet/gold revisions, actual archive field paths, native eligible set, reconstruction of intended assignments, retry observability, available identifier-conversion records, and existing workflow adequacy. Any missing fact has a gate or unsupported state above. Customer thresholds can remain unset indefinitely without blocking the evidence tool. The builder may choose internal SQL indexes, dataclass layout, and small helper boundaries while preserving these contracts.
