# Usage

Run from the checkout with Python 3.11+. Product commands need no installation,
third-party runtime packages, paid APIs or model judge. Acquire source evidence
first; evaluation and reporting make no network calls.

## Inputs and outputs

`freeze` imports a NEEDLE Scholar packet or canonical JSONL directory, retains
the source bytes and policy, and builds an immutable SQLite ledger. `evaluate`
verifies evidence, scores it, checks the independent oracle and assesses
requested comparisons. `report` reads the evaluation once, reconstructs every
claim from the verified frozen run and policy (including fresh scoring and an
independent oracle check), rejects any difference, then renders HTML. Edited
evaluation files are not trusted, even if their identity and reference flags
match. See [the verification boundary](evidence/report-verification.md).

The output directory contains `evaluation.json` (all cases and attempts),
`verdict.json` (summary and comparison gates), and, after `report`, `report.html`.
HTML opens locally without scripts, assets or a server. Optional thresholds
produce independent arm decisions; there is no automatic winner.

Use `python -m pilotpack --help` and each subcommand's `--help` for flags.
[The adapter profile](evidence/adapter-profile.md) documents canonical records,
provenance, conversion maps and actual-vs-declared settings.

## Canonical example

This is a synthetic schema control, not customer or provider evidence:

```sh
python -m pilotpack freeze --adapter canonical \
  --input fixtures/canonical/schema-small --config fixtures/config/canonical.json \
  --protocol fixtures/canonical/schema-small/protocol.json \
  --sources fixtures/canonical/schema-small/sources.json --out runs/canonical
python -m pilotpack evaluate --run runs/canonical --out build/canonical
python -m pilotpack report --run runs/canonical \
  --evaluation build/canonical/evaluation.json --out build/canonical
```

For real packet B, use the README's NEEDLE commands with `packet-b` input and
configuration, `runs/demo-b`, and `build/demo-b`. Its requested comparison is
also blocked. Originals and explicit exclusions are retained. Supported real
cohorts are arXiv-only: A has 324 tasks/81 groups, B has 328/82. Full historical
PMID extraction is unsupported.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Artifacts generated; comparisons eligible, or none requested |
| 2 | Invalid evidence, integrity/reference failure or publication failure |
| 3 | Qualified artifacts generated with a requested comparison blocked |

A threshold failure is valid and does not change the exit code. Diagnostics go
to stderr. Missing costs stay missing; exact request counts require complete
evidenced histories. Sorted marginal latency samples cannot supply task-paired
latency. Missingness ranges aren't confidence intervals; the demonstration
cannot resolve tiny provider differences.

## Repeating commands and interrupted publication

`freeze` refuses an existing destination. Evaluation/reporting can reuse an
output directory only for identical run/content/protocol identities. Identical
commands under the same recorded Python environment produce identical JSON/HTML bytes. Re-evaluation removes old HTML
until `report` runs again. Input and output directories must not overlap.

Publication stages a complete directory before replacing the previous output.
Handled errors preserve that output or leave no final output. The destination
can briefly be absent during replacement. A hard kill can leave a sibling
`.NAME.previous-*` complete backup and `.NAME.publishing` lock; inspect the
backup before restoring it and removing a stale lock. Do not edit frozen runs.

## Checks and full reproduction

```sh
python -m unittest discover -s tests -v
python reference/oracle.py --run runs/demo-a
```

Extract the offline-baselines release asset before real-packet commands or the
full suite: provenance requires its original NEEDLE source tar even when no
native code is executed. The synthetic example above needs no external assets.
The native-replay test additionally needs its isolated environment and explicitly
skips without one. The v0.1.0 release verified 202 tests; the [current candidate check](evidence/integrity-2026-10-16.md) verified 233, both with zero skips.
For native setup and guarded clean replay, follow
[offline reproduction](evidence/reproduction.md). The bundle supplies the exact
source archive and seven wheels; replay makes no provider or judgment requests.
Failed validation and separately reserved v2 remain in
[validation](evidence/validation.md).

## Prospective reviewer assessment

[Workflow protocol v3](evidence/workflow-protocol-v3.md) defines the prerequisites
and log format for a future authorized reviewer study. The separate
`tools/workflow_study.py` CLI validates assignment/event/independent-grade logs
and reports descriptive totals. Its synthetic tests are software checks, not
observed operator timings. No reviewers or operating requirements are available;
operational value is unassessed.
