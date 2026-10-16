# Workflow protocol v3: prospective operational assessment

**Status: blocked; operational value UNASSESSED.** No authorized reviewers,
operating requirements, participant observations, or human timing records are
available. This is a protocol and log checker, not a completed study. The
historical preparation experiment remains **NEUTRAL**: the reusable
`reference/prepare_packet.py`, `reference/oracle.py`, and
`reference/needle_replay.py` baseline and the pack each needed zero recurring
B-specific conversion/analysis actions and zero manual source-row edits.
See [workflow-comparison.md](workflow-comparison.md) and
[poc-assessment.md](poc-assessment.md). These counts establish no time saving.

## Question and comparator

Determine whether authorized users can complete the specified assessment work
with independently correct, traceable results, within their actual accuracy
and turnaround requirements, with a practically useful improvement in total
operator effort. Correctness, safety of blocked conclusions, and efficiency
are separate outcomes. A faster wrong answer is not a successful assessment.

The baseline uses the existing reusable reference/native scripts and the
operator's normal tools, with manual inspection, calculations, and controls
allowed. The pack uses the same unchanged evidence and the same assessment
questions. Both receive equivalent documentation, source access, training,
hardware, and permitted assistance. Record actual tool versions and permitted
normal tools in the final plan. Count baseline verification and manual work
just as pack verification and correction; do not rebuild reusable baseline
scripts for each packet or remove useful baseline tools to create a benefit.

## Prerequisites and freeze

Before viewing any operational outcomes, an authorized owner must source and
freeze the following, retaining each source and its SHA-256 receipt:

| Requirement | Current value | Needed before an operational conclusion |
| --- | --- | --- |
| Accuracy | `null` | Required assessment correctness, error severity, acceptance rule |
| Turnaround | `null` | Required delivery window and treatment of unfinished work |
| Practical improvement | `null` | Smallest useful effort improvement and its rationale |
| Authorized users | `null` | Authorized population, recruitment and consent/access arrangements |
| Task rubric | `null` | Exact assessment questions, expected evidence and independent scoring rubric |
| Counterbalancing | `null` | Order/learning/fatigue controls and allocation procedure |
| Sample design | `null` | Justified participant/task design and uncertainty analysis |
| Independent grading | `null` | Authorized graders, blinding where feasible, adjudication and disagreement procedure |
| Holdout | `null` | Uninspected task/evidence inventory, access boundary and release procedure |
| Final plan | `null` | Frozen analysis, timing method, exclusions, stopping and deviation rules |

No percentage, participant count, time target, or convenient sample size is
chosen here. Requirements may remain unresolved and null. Do not substitute
LLM personas, script runtime, guessed human durations, or developer familiarity
for observations from authorized users. No participant study is authorized or
performed by this change.

The final plan and assignment manifest are frozen before inspecting holdout
outputs or grading operational results. Preserve the committed/versioned
manifest, raw bytes, hashes, UTC freeze time, and independent freeze receipt.
Tool timestamps detect inconsistent chronology; they do not prove that someone
did not inspect a task beforehand. Any unplanned change creates a documented
deviation and a new prospective freeze; it does not repair the old result.

A, B, validation v1 and validation v2 are **development-consumed** evidence,
including derivatives and renamed copies. They can debug tooling or rehearse
procedures; they cannot be relabeled fresh holdout evidence. A future holdout
and its sample design require their own sourced approval. Engineering task
counts and the existing validation suite do not establish statistical power.

## Tasks, allocation and grading

Assign the full assessment workload, not only tasks that produced a favorable
verdict. The rubric must cover eligible comparisons and blocked decisions,
including genuinely zero cost, missing cost, and malformed synthetic evidence.
For example, a zero-cost task must distinguish an observed numeric zero from
an unavailable cost; a missing-cost task must retain unknown totals; a blocked
or malformed task must identify the evidence/validation issue without choosing
an unsupported winner. Correct refusal can be a correct completed task.
Synthetic fault tasks are labeled synthetic and independently specified; they
do not stand in for fresh real operational evidence. The authorized rubric
determines the actual questions, mix, weights and required coverage.

Use matched task difficulty and equivalent evidence access across workflows.
Freeze task identities, assignment order and counterbalancing before outcomes.
Avoid exposing an operator to the answer for a later task through a repeated
case. Record familiarity, training, assistance, tool failures and deviations.
Do not silently replace failed, unfinished, or inconvenient assignments.

Every assignment receives an independent grade against the frozen rubric,
with separate boolean correctness and traceability judgments, a retained
evidence reference, grader identity, and rationale. Traceability requires a
reviewable chain from task/source evidence through calculations and decisions;
it is not a self-reported confidence score. The grader must differ from the
operator; the final plan must establish substantive independence and resolve
disagreements. A submitted wrong or untraceable answer is an error. An
unsuccessful or unattempted assignment stays in the denominator and cannot
receive a correct grade. Absence of a grade is missing evidence, never success.

## Timing and denominators

Record observed operator intervals for **preparation, execution, verification,
correction and unsuccessful attempts**. Include reading source material,
configuring tools, interpreting blocked results, diagnosing errors and rework.
Preserve all attempts, including abandoned ones; logging only the final
successful attempt invalidates the comparison. Explicitly record zero-duration
phases with an explanation instead of treating missing records as zero.
Intervals may be collected from an authorized observation method in the plan;
this repository does not claim to measure them automatically.

Separate one-time setup/training from repeated assessment assignments and
report both. Do not amortize setup using an invented reuse horizon. Machine
intervals are reported separately as summed recorded machine minutes; they
are neither human effort nor automatically wall-clock turnaround. Operators
may work during machine activity. An operator cannot charge overlapping human
intervals to two assignments. Retain observation gaps and interruption rules
in the frozen plan, rather than silently dropping time.

For each workflow and each setup/repeat period report: all assigned tasks,
submitted tasks, independently correct-and-traceable tasks, errors (every
assigned task that is not independently correct and traceable), completion
rate = submitted / assigned, correct-and-traceable rate = correct-and-traceable
/ assigned, error rate = errors / assigned, total operator minutes with phase
breakdown, and machine minutes separately. A failed or unattempted task has
zero completion credit even when it consumed substantial effort. Zero assigned
tasks have null rates. The tooling reports descriptive aggregates only; the
frozen sample design must address paired allocation, operator/task variation,
uncertainty, missingness and requirement evaluation before any interpretation.

## Small log contract

`python tools/workflow_study.py --assignments assignments.json --events events.jsonl --grades grades.jsonl`
reads files without modifying them and emits JSON on stdout. Preserve raw
event and grade logs, source artifacts and freeze receipts outside strict
product reports, for example in a separately controlled study evidence
directory. Do not insert telemetry into `pilotpack` verdict/report schemas.

The assignment JSON has exactly these fields (values below are a **blocked
template**, not observations):

```json
{
  "schema_version": 1,
  "study_id": "unstarted",
  "frozen_at": null,
  "requirements": {
    "accuracy": null, "turnaround": null, "practical_improvement": null,
    "authorized_users": null, "task_rubric": null, "counterbalancing": null,
    "sample_design": null, "independent_grading": null, "holdout": null,
    "final_plan": null
  },
  "development_consumed": ["A", "B", "v1", "v2"],
  "assignments": []
}
```

A populated requirement is `{"source":"retained source reference","sha256":"64 lowercase hexadecimal characters"}`.
The checker validates receipt shape, not source authenticity or substantive
adequacy. No requirement is inferred from a nonempty string. The authorized
reviewer must inspect those retained sources before deciding readiness.

Each assignment has exactly `id`, `task_id`, `fixture_id`, `task_class`,
`workflow`, `operator`, `period`, and `evidence_status`. IDs are nonempty
strings. `task_class` is `eligible`, `blocked`, `zero_cost`, `missing_cost`, or
`malformed`; `workflow` is `baseline` or `pack`; `period` is `setup` or
`repeat`; `evidence_status` is `development` or `holdout`. Keep fixture
identity consistent across derivatives. The development inventory may add
identities but must retain A/B/v1/v2. A development identity declared holdout
is contradictory. The checker cannot discover undisclosed familiarity.

Each raw JSONL event has a unique `id`, `assignment_id`, `kind`, and a nonempty
`note`. An `operator` event also has `phase`, `start`, `end`; a `machine`
event has `start`, `end`; a `close` event has `at`, `outcome`. Phases are
`preparation`, `execution`, `verification`, `correction`, and
`unsuccessful_attempts`. Outcomes are `submitted`, `unsuccessful`, and
`not_attempted`. Every assignment has all five operator phases (repeat
intervals allowed), explicit machine coverage (a zero interval when none),
and exactly one close. All timestamps use timezone-aware ISO 8601, including
zero-duration declarations. Timing starts at or after freeze, ends before
close, and cannot be negative. `not_attempted` has only zero intervals.

Each grade JSONL row has exactly `assignment_id`, `grader`, `at`, `correct`,
`traceable`, `evidence`, and `rationale`. Booleans must be JSON booleans. All
assignments require exactly one grade at or after close, even unsuccessful or
unattempted work. `evidence` identifies the retained independently graded
submission or explicit noncompletion record. The independent grader may not
be any operator in the study. Raw events, grades and manifests are hashed in
CLI output so later reports can identify the exact analyzed bytes.

Unknown fields, malformed JSON/duplicate keys, duplicate IDs, orphan records,
missing phase/machine/close/grade evidence, contradictory outcomes, overlapping
operator intervals and invalid timestamps fail closed: `validation: invalid`,
no metrics, exit 2. Complete logs with null prerequisites or development data
produce descriptive metrics with `readiness: blocked`, exit 3. Complete
holdout logs with populated prerequisite receipts produce
`readiness: requires_source_review`, exit 0. In every case
`operational_value` remains `UNASSESSED`; neither receipt presence nor a
descriptive difference certifies requirements, authorization, causal benefit,
or final operational success. No pooled efficiency score, winner, significance
claim, percentage improvement or automatic success threshold is produced.

## Implementation plan and verification record

**Goal:** implement the contract above without product changes, network access,
participant activity or third-party dependencies. **Architecture:** one
standard-library CLI validates a declared assignment manifest and independent
raw logs, then calculates bounded descriptive totals only after validation.
**Files:** this protocol, `tools/workflow_study.py`, and
`tests/test_workflow_study.py`. The user's assigned file scope overrides the
usual plan directory. The parent agent owns commits and whole-repository
integration.

1. Write this protocol before implementation. Preserve the operational block
   and unresolved values; do not supply convenient experimental requirements.
2. Write executable behavior tests covering all-assignment denominators,
   setup/repeat separation, effort/latency separation, independent grading,
   zero/missing evidence, consumed holdout identity, and malformed/contradictory
   logs. Run and retain the expected missing-tool failures before writing code.
3. Implement the smallest CLI satisfying those tests, then run the tests and
   the repository suite. Preserve actual red/green command outputs under
   `build/investigation/workflow/`; synthetic test durations are software
   fixtures and must never be presented as observed operator timing.
4. Review schema/report consistency and changed-file scope. Document actual
   checks and limits; hand files to the parent for integration and review.

The main review risks are denominator loss from missing submissions, omitted
unsuccessful effort, conflation of machine and human time, self-grading or
invented independence, and development evidence masquerading as holdout.
The tests exercise these failure modes. Real authorization, source adequacy,
timing completeness, representative sampling and grading quality remain
outside the tool's ability to establish.
