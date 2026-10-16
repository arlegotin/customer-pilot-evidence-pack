# Customer Pilot Evidence Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a local, reproducible evidence packet that preserves intended assignments, physical-request evidence, missing outcomes, native metrics, and comparison limits.

**Architecture:** Freeze original bytes and policy, normalize one NEEDLE Scholar profile or canonical JSONL into an immutable SQLite ledger, and compute deterministic metrics checked by independent Python and unchanged upstream replay. Apply scoped comparison gates and optional per-arm criteria, then emit a deterministic JSON verdict and escaped static HTML.

**Tech Stack:** Python 3.11+, `json`, `sqlite3`, `hashlib`, `decimal`, `random`, `html`, `argparse`, `unittest`; no production/test dependencies. Unchanged upstream baseline uses its own pinned offline environment.

**Spec:** [Customer Pilot Evidence Pack design](../specs/2026-10-16-customer-pilot-evidence-pack-design.md). Read it before executing any task.

## Global Constraints

- Python 3.11+; production runtime and tests use the standard library only.
- Evaluation and reporting are local and offline after acquisition.
- No paid APIs, model-generated judgments, hosted application, customer-data upload, routing, new ranking algorithm, or new agent framework.
- Missing cost remains missing; retrieval metrics never become claims about agent answer quality.
- Raw inputs, protocol, and normalized ledgers are immutable within a frozen run.
- Synthetic corruption artifacts remain separate from original evidence.
- Work stays on the current branch unless the user later requests otherwise.

This is a plan, not an implementation authorization. The repository had no product files when this plan was written. Do not create a worktree or switch branches: the user explicitly requested the current branch. Do not push or publish. Native execution using `superpowers:executing-plans` is a suitable later choice because the tasks share contracts and the four-day budget favors a single implementer. Preserve a different execution method if the user chooses one.

## Review Focus

1. Equal query text with different task identities must not merge assignments; pin in Task 2 and Task 4.
2. Terminal archive rows with unobserved retries must not become exact physical counts or complete cost; pin in Task 4 and Task 6.
3. Partial results, unknown judgments, and runner non-dispatch must not become ordinary misses; pin in Task 5 and Task 6.
4. Valid but untrusted query/snippet/URL text must render safely in a fully offline report; pin in Task 7.
5. Reordered records, interrupted writes, and reused output directories must preserve identities and leave no misleading partial result; pin in Task 3, Task 4, and Task 7.

## File structure and shared interfaces

| File/directory | Responsibility |
| --- | --- |
| `pilotpack/schema.py` | Strict JSON records, protocol, validation errors, shared `Packet` type. |
| `pilotpack/ingest.py` | One archive adapter, canonical adapter, provenance, canonical serialization, frozen-run verification. |
| `pilotpack/ledger.py` | Transactional tables, insert-only protection, normalized-record digest and queries. |
| `pilotpack/score.py` | Native-compatible identifier matching, logical retry selection, metrics and reference reconciliation. |
| `pilotpack/compare.py` | Scoped comparison gates, grouped bootstrap, cost availability, per-arm criteria. |
| `pilotpack/report.py` | Deterministic JSON artifacts, escaped HTML, identity checks and publication. |
| `pilotpack/cli.py`, `__main__.py`, `__init__.py` | `freeze`, `evaluate`, `report` entry points and exit codes. |
| `reference/oracle.py` | Independent direct-JSONL scorer/accounting; no product imports. |
| `reference/prepare_packet.py`, `reference/needle_replay.py` | Small existing-workflow baseline export and offline replay driver for unchanged pinned NEEDLE. |
| `fixtures/real/{packet-a,packet-b}/` | Unchanged acquired source bytes with manifest; protected B held until Task 9. |
| `fixtures/canonical/`, `fixtures/config/`, `fixtures/expected/` | Small human-auditable inputs, adapter config, frozen expected records. |
| `fixtures/corruptions/manifest.json`, `fixtures/controls/manifest.json` | Frozen cases, mutation definitions and expected findings. |
| `protocol.json`, `sources.json` | Actual versioned evaluation policy and real provenance, populated only from evidence. |
| `tests/test_*.py`, `tests/support.py` | Contract tests and small fixture builders, not a second framework. |
| `docs/evidence/` | Acquisition decision, actual adapter profile, manual reconciliation, native baseline, workflow comparison and validation results. |
| `runs/`, `build/`, `reference/runs/`, `reference/upstream/` | Generated runs/output and pinned baseline environment; ignored or stored as explicitly hashed acquisition artifacts. |

Use `JsonObject = dict[str, Any]` in product type hints. `Packet` is a frozen dataclass with `root: Path`, `manifest: JsonObject`, `protocol: JsonObject`, and tuple-of-object fields `sources`, `tasks`, `assignments`, `outcomes`, `attempts`, `diagnostics`. JSON records follow spec section 5; freezing the dataclass does not replace SQL/content-integrity checks. No mutable global state.

Evaluation JSON has `schema_version`, `run_id`, `content_id`, `protocol_hash`, `arms`, `cases`, `native_metrics`, `reference_checks`, `pairs`, `decisions`, `diagnostics`, `limitations`. `arms[arm_id]` includes `N`, `H`, `M`, `F`, `U`, `unknown_reasons`, `delivered_hit_at_k`, `missingness_range`, `attempts`, `cost`, and `latency`. `pairs` is a list of objects with `arm_a`, `arm_b`, `comparison_status`, `gates`, `delivered_difference`, `missingness_difference_range`, `bootstrap`. `decisions[arm_id]` contains that arm's criteria, `decision_status`, and reasons. Keep these names consistent across tasks. The verdict is a documented subset without full case text.

Diagnostics contain `code`, `severity` (`error`, `block`, `limitation`), `scope`, `source_refs`, and `message`. `ValidationError` carries a list of diagnostics. Invalid files abort import; supported missingness survives with limitations. Do not treat every diagnostic as a blocking fault.

Task dependency order: **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9**. Freeze acceptance assets before protected evaluation. Task 1 can terminate or shrink the project; do not work around its gate with synthetic provider evidence.

---

### Task 1: Acquire evidence and falsify the need for a new layer

**Files:** Create `docs/evidence/{acquisition,adapter-profile,reconciliation,native-baseline,workflow-comparison}.md`, `sources.json`, `protocol.json`, real/config/expected fixtures, `reference/{prepare_packet,needle_replay,oracle}.py`, `tests/test_reference_baseline.py`, `.gitignore`.

**Interfaces:**
- Consumes: the spec, public archive, actual pinned NEEDLE scorer; no existing product API.
- Produces: real packet A plus reserved B inventory; an acquisition/reuse decision; actual field-map annex; offline native replay artifacts.
- Produces: `reference.oracle.evaluate_run(root: Path) -> dict[str, Any]` and CLI `python reference/oracle.py --run RUN`, JSON on stdout, diagnostic stderr, exit 0/2. It reads canonical files directly, independently scores literal identifiers and counts assignments/attempts; it imports no `pilotpack` code.
- Produces: `python reference/needle_replay.py --packet SOURCE --checkout CHECKOUT --out OUTPUT` and `python reference/prepare_packet.py --input SOURCE --config CONFIG --out RUN`. These are bounded drivers for the actual acquired shape, not a general importer framework.

- [ ] **Step 1: Freeze candidate source bytes and reserve B.** Follow spec section 3: select by completeness, pin revisions, hash actual bytes and record acquisition commands/times/license. Do not put guessed hashes or placeholder values in `sources.json`. Keep downloaded dependency caches and generated outputs out of ordinary Git history; record how the exact artifacts are retained for offline replay.
- [ ] **Step 2: Write the actual adapter profile and reconcile 20 examples.** Record exact source fields, join rules, gold/run correspondence, selection, retry evidence, native eligible set and conversion-map requirements. Put independently inspected task IDs, ranks, counts and expected outcomes in `fixtures/expected/packet-a.json`. Note unavailable fields explicitly.
- [ ] **Step 3: Reproduce unchanged NEEDLE reporting offline.** Create the minimal replay driver against the pinned upstream checkout and isolated environment. Inject stored responses into existing scoring entry points rather than invoking live search. Preserve native code/license and any required identifier maps. Record supported metrics and exact commands/results in `native-baseline.md`; unsupported replay is a gate finding, not a replacement formula.
- [ ] **Step 4: Write independent baseline tests.** Hand-author canonical records for a ten-assignment arm with four hits, two misses, one terminal provider failure and three known-dispatched unknown judgments. Assert against the independent oracle, with no product helpers:

```python
result = evaluate_run(FIXTURES / "canonical" / "ten-assignments")
arm = result["arms"]["a"]
self.assertEqual([arm[x] for x in ("N", "H", "M", "F", "U")], [10, 4, 2, 1, 3])
self.assertEqual(arm["delivered_hit_at_k"], 0.4)
self.assertEqual(arm["missingness_range"], [0.4, 0.7])
```

Also assert literal DOI/arXiv aliases, first-hit rank, valid empty response, and unknown evidence. Native denominator expectations come from Step 3, not this illustrative delivered example.
- [ ] **Step 5: Run the independent test red.** `python -m unittest discover -s tests -p test_reference_baseline.py -v` must fail because the oracle implementation is absent, not because the source fixture is malformed.
- [ ] **Step 6: Implement the small independent baseline.** Implement `evaluate_run` plus the bounded export driver using direct Python/SQL. Use separate literal identifier logic and independent aggregation; do not import future production normalization/scoring. Run it against the frozen packet and capture discrepancies with native metrics rather than reconciling by hand edits.
- [ ] **Step 7: Run the baseline checks green.** Re-run the test command and `python reference/oracle.py --run reference/runs/packet-a`. Verify exact example counts and supported metrics within `1e-9` against the unchanged replay. Save machine-readable baseline output and its hash.
- [ ] **Step 8: Decide the acquisition/duplication gate.** Record whether the existing export/report already meets the complete accounting/replay requirement through configuration alone. If yes, stop new platform work and document reuse or a thin missing adapter. If real evidence fails, attempt only the spec's recorded 20-task keyless fallback; if it fails, stop provider-verdict claims. Document unattained two-packet/coverage targets. Continue Tasks 2–9 only when justified by the gate.
- [ ] **Step 9: Commit the evidence milestone.** Stage the named reference code, tests, documentation, policy and manageable source fixtures explicitly. Verify `git diff --cached --check`, then commit `docs: freeze evidence baseline and record acquisition gate`. Use `feat:` instead if the commit contains substantial executable reference tooling. Never label this a successful provider comparison before the later checks.

### Task 2: Define and validate canonical records and protocol

**Files:** Create `pilotpack/{__init__,schema}.py`, `tests/test_schema.py`, `tests/support.py`, and hand-sized `fixtures/canonical/` records. Update the actual `protocol.json` schema contract documentation in `docs/evidence/adapter-profile.md`.

**Interfaces:**
- Consumes: canonical version 1 and actual source facts from Task 1.
- Produces: `schema.Packet`, `schema.ValidationError`, `schema.load_json(path: Path) -> JsonObject`, `schema.load_jsonl(path: Path) -> tuple[JsonObject, ...]`, `schema.validate_packet(root: Path) -> Packet`.
- Produces: stable diagnostic codes from spec section 10 and validated per-arm `decision_criteria`. JSON decoding and semantic validation are separate so null/unknown evidence is not confused with malformed input.

- [ ] **Step 1: Write schema contract tests.** Cover duplicate JSON keys/NaN (`INVALID_JSON`), blank JSONL lines, unknown fields outside `extensions`, missing task/source IDs, orphan assignments, invalid rank order, negative latency/cost, timezone-free timestamps, reversed durations, k outside `[1, requested_num_results]`, unknown criterion arm IDs, and thresholds outside [0, 1]. Assert diagnostics include file and line/path. Pin identity behavior:

```python
packet = validate_packet(make_packet(self.tmp, scenario="same-text-distinct-tasks"))
self.assertEqual(len(packet.tasks), 2)
self.assertEqual(len(packet.assignments), 4)
self.assertEqual(packet.protocol["decision_criteria"], {})
```

Add a valid `snippet_chars=0` case distinct from null, a true observed-zero cost with provenance, and incomplete archive fields with explicit limitations.
- [ ] **Step 2: Run red.** `python -m unittest discover -s tests -p test_schema.py -v`; verify failure is the missing schema API.
- [ ] **Step 3: Implement the schema API.** Use `json` duplicate-key hooks and `parse_constant`, frozen `Packet`, explicit field sets, decimal-string validation and timezone-aware `datetime` parsing. Require source references and distinguish structural errors from allowed evidence gaps. Reject unsupported versions; no schema auto-migration in this PoC.
- [ ] **Step 4: Run green.** Re-run schema tests and the independent baseline tests. Expected: all pass; no product import added to the oracle.
- [ ] **Step 5: Commit.** `git add pilotpack/__init__.py pilotpack/schema.py tests/test_schema.py tests/support.py fixtures/canonical docs/evidence/adapter-profile.md`, check staged whitespace, then `git commit -m "feat: validate canonical evidence and protocol contracts"`.

### Task 3: Build the immutable ledger and verify accounting

**Files:** Create `pilotpack/ledger.py`, `tests/test_ledger.py`; extend `tests/support.py` with canonical-only fixture construction.

**Interfaces:**
- Consumes: `schema.Packet`.
- Produces: `ledger.create_ledger(packet: Packet, db_path: Path) -> None`, `ledger.read_records(db_path: Path) -> dict[str, tuple[JsonObject, ...]]`, `ledger.normalized_digest(db_path: Path) -> str`, `ledger.verify_ledger(db_path: Path, expected_digest: str) -> None`.
- `read_records` keys are `sources`, `tasks`, `assignments`, `outcomes`, `attempts`, `diagnostics`; result arrays retain rank order. Outcomes can exist without physical attempts.

- [ ] **Step 1: Write ledger tests.** Check exact source-row preservation, foreign keys, duplicate logical keys, rollback when the last row is invalid, refused existing database, and SQL UPDATE/DELETE rejection. Import reordered equivalent records and assert the same normalized digest. Modify a database through a separate connection after deliberately dropping a protection trigger and assert `verify_ledger` detects the content change. Do not assert identical SQLite file bytes.
- [ ] **Step 2: Run red.** `python -m unittest discover -s tests -p test_ledger.py -v` must fail on the missing ledger implementation.
- [ ] **Step 3: Implement the ledger API.** Use SQLite transactions, foreign keys, uniqueness constraints and insert-only triggers for evidence tables. Create tables for ordered results instead of losing rank in an unordered join. Query source/canonical counts independently to prove no row was silently dropped. Compute the digest over stable normalized records, excluding volatile metadata.
- [ ] **Step 4: Run green.** Re-run ledger and schema tests. A failed import must leave no published database; repeated construction at an existing path must leave its original bytes untouched.
- [ ] **Step 5: Commit.** Stage ledger code/tests/helper changes explicitly; check staged whitespace; commit `feat: preserve immutable assignment and attempt ledgers`.

### Task 4: Normalize both import paths and freeze provenance

**Files:** Create `pilotpack/ingest.py`, `tests/test_ingest.py`, `fixtures/config/{packet-a,packet-b,canonical}.json`. Update source/adapter documentation only with observed facts. Do not read B's task outcomes yet.

**Interfaces:**
- Consumes: Task 1's actual profile; `schema.validate_packet`; Task 3 ledger functions.
- Produces: `ingest.import_canonical(input_dir: Path, config: JsonObject) -> Packet`, `ingest.import_needle_scholar(input_dir: Path, config: JsonObject) -> Packet`, `ingest.freeze(input_dir: Path, *, adapter: str, config_path: Path, protocol_path: Path, sources_path: Path, out: Path) -> Path`, `ingest.verify_run(run: Path) -> Packet`.
- `freeze` returns the completed run path. Adapters are named exactly `canonical` and `needle-scholar`. Canonical import does not reinterpret source identities.

- [ ] **Step 1: Write import/reconciliation tests.** Verify packet A's 20 checked examples and full task/arm counts. Test equal text with different IDs, duplicate/orphan rows, explicit synthesized U for an absent intended outcome, reconstruction with/without authoritative manifest evidence, and preservation of original `ultimate` without real-provider assignments. Test all archive-to-canonical unknown fields against the documented profile. Assert archive logical rows do not create physical attempt rows:

```python
run = freeze_archive(self.tmp, scenario="logical-results-only")
packet = verify_run(run)
self.assertEqual(packet.attempts, ())
self.assertEqual(packet.manifest["attempt_history"]["a"], "unknown")
```

Test raw hash mismatch, traversal/symlink escape, missing conversion evidence, pre-dispatch manifest timestamps, stable content ID under canonical record reordering, source-byte preservation, interrupted staging and refusal of an existing destination.
- [ ] **Step 2: Run red.** `python -m unittest discover -s tests -p test_ingest.py -v`; failures must expose the absent adapter/freezer, not a network dependency.
- [ ] **Step 3: Implement adapters and freeze/verification.** Support the one observed profile only. Match tasks using the documented keys; require gold/version evidence. Generate explicit reconciliation rows, preserve nulls and limitations, and never manufacture settings/physical requests. Build in a sibling staging directory; validate all bytes/records before publishing. Implement the spec's noncyclic `content_id`, relative-path checks, normalized-table digest and source hashes. `verify_run` recomputes hashes plus ledger digest without writing to the run.
- [ ] **Step 4: Run green.** Re-run importer, schema and ledger tests. Freeze A, verify it in a fresh process, and compare canonical records to the independent baseline export. Original source hashes must match the Task 1 acquisition manifest.
- [ ] **Step 5: Commit.** Stage importer/tests/config/profile documentation; verify staged diff; commit `feat: freeze canonical and NEEDLE Scholar packets with provenance`.

### Task 5: Score logical delivery and reconcile both baselines

**Files:** Create `pilotpack/score.py`, `tests/test_score.py`, `fixtures/expected/identifier-cases.json`. Complete the standalone oracle's physical-history and native-supported metric outputs independently if the acquired profile requires them.

**Interfaces:**
- Consumes: `ingest.verify_run(run)`, ledger records, the Task 1 pinned native profile and oracle CLI.
- Produces: `score.match_rank(gold_ids: dict[str, list[str]], results: list[JsonObject], *, k: int, snippet_chars: int, identifier_map: JsonObject | None) -> int | None`, `score.select_delivery(assignment: JsonObject, outcome: JsonObject, attempts: tuple[JsonObject, ...], protocol: JsonObject) -> JsonObject`, `score.score_run(run: Path) -> JsonObject`, `score.check_reference(run: Path, evaluation: JsonObject) -> list[JsonObject]`.
- `score_run` fills evaluation identities, `arms`, `cases`, `native_metrics`, empty `pairs`/`decisions`, diagnostics and limitations. `check_reference` invokes `reference/oracle.py` in a separate process, compares counts exactly/numerics at absolute `1e-9`, and checks the frozen native replay outputs. It returns reference diagnostics and never alters raw data.

- [ ] **Step 1: Write metric/retry tests.** Pin the ten-assignment counts/range from Task 1, empty cohort nulls, wholly unknown N nulls, native scored denominator and MRR from the pinned profile, unknown judgments as U, provider errors as F, runner non-dispatch as U, and true empty response as M. Test identifier aliases/versions, URL/snippet extraction, snippet cap/zero/no cap, first match at k versus k+1, repeated results and missing map evidence. Pin retry behavior:

```python
delivery = select_delivery(assignment, outcome, attempts_error_then_empty_then_hit, protocol)
self.assertEqual(delivery["selected_attempt_id"], "attempt-2")
self.assertEqual(delivery["classification"], "M")
```

Also test all-errors terminal F, interrupted retries U/block, forged cached ranks, contradictory selected attempt, and native `ultimate` only in the separate ceiling section. Force a `1e-8` reference discrepancy and assert `REFERENCE_MISMATCH`; accept a supported `1e-10` difference.
- [ ] **Step 2: Run red.** `python -m unittest discover -s tests -p test_score.py -v`; verify absent scoring functions cause the failures.
- [ ] **Step 3: Implement deterministic scoring and reference checking.** Use the exact frozen Scholar extraction evidence/profile, explicit H/M/F/U partition and first-completed retry selection. Retain native score/denominator separately; never replace native metrics with delivered metrics. Preserve source evidence for each score and collect observed physical rows, lower bounds and exact-count availability independently. Run the oracle without product imports and compare extraction against the literal examples/native replay as well as canonical IDs.
- [ ] **Step 4: Run green.** Re-run scoring tests, full existing unit suite and both packet A baselines. All applicable metrics must agree within `1e-9`; assert exact source/assignment/attempt counts. A disagreement stops later verdict claims.
- [ ] **Step 5: Commit.** Stage scoring/tests/identifier fixtures and any independently implemented oracle additions; check staged whitespace; commit `feat: score delivered retrieval with explicit missingness and retries`.

### Task 6: Gate comparisons, estimate grouped uncertainty and judge per-arm criteria

**Files:** Create `pilotpack/compare.py`, `tests/test_compare.py`, `tests/test_cost.py`; update protocol documentation for actual arm settings and optional thresholds.

**Interfaces:**
- Consumes: `Packet` and evaluation from Task 5.
- Produces: `compare.assess(packet: Packet, evaluation: JsonObject) -> JsonObject` (returns an annotated copy with `pairs`, `decisions`, cost/latency availability and scoped diagnostics).
- Produces: `compare.grouped_bootstrap(rows: list[JsonObject], *, replicates: int, seed: int) -> JsonObject`; each row has `task_id`, `source_group_id`, and binary `a_hit`, `b_hit`. Return `interval`, `replicates`, `seed`, `n_groups`, `n_queries`, `estimand`, `method`, plus unavailable reason when needed.
- Produces: `compare.observed_cost(attempts: tuple[JsonObject, ...], *, history_complete: bool) -> JsonObject`, `compare.build_verdict(evaluation: JsonObject) -> JsonObject`.

- [ ] **Step 1: Write comparison/decision/cost tests.** Cover every gate in spec section 7, including unmatched cohorts (no intersection), actual vs declared modes, k/count/snippet/settings/time-window mismatch, unknown retry policy, runner non-dispatch, absent outcome and reference mismatch. Legitimate different per-arm modes and documented physical-history gaps remain valid for supported retrieval. For N=10, A=(H4,U3), B=(H5,U1), assert missingness difference `[-0.2, 0.2]` within `1e-9` and suppressed bootstrap. For complete paired grouped data, assert deterministic replay, all variants move with the group, and the query-weighted estimand matches independently enumerated small resamples; include unequal group sizes and one-group/missing-group cases. Require exactly 2,000 replicates, seed 0 and the specified nearest-rank endpoints.

Assert no thresholds means `descriptive_only`; configure separate A/B criteria yielding different decisions; test hit threshold above/below/inside the missingness range and exact max F/U criteria. An arm block yields `not_evaluable`; a pair-only block never becomes a winner or erases independent arm status. Test `Decimal("0.10") + Decimal("0.20")` totals, known-zero provenance, mixed currencies, estimated/missing rows and incomplete history; unknown total is null, not 0. Sorted latency samples must yield no task-paired latency.
- [ ] **Step 2: Run red.** `python -m unittest discover -s tests -p test_compare.py -v` and `python -m unittest discover -s tests -p test_cost.py -v`; inspect the missing-implementation failures.
- [ ] **Step 3: Implement the comparison API.** Apply scoped gates without dropping assignments. Compute missingness identification endpoints directly; bootstrap only eligible U=0 paired cohorts with group IDs. Resample sorted groups uniformly, retain variants and both arms, recompute query-weighted differences. Use decimal strings for costs and explicit coverage/availability. Keep decisions keyed by arm ID, criteria empty by default, and omit a global winner/status.
- [ ] **Step 4: Run green.** Re-run both focused test commands and the full unit suite. Inspect a packet A annotated result to confirm gates and limitations cite source evidence and no marginal latency array is paired.
- [ ] **Step 5: Commit.** Stage comparison code/tests/protocol documentation; check staged diff; commit `feat: qualify comparisons and expose grouped uncertainty`.

### Task 7: Publish deterministic offline JSON/HTML through the CLI

**Files:** Create `pilotpack/{report,cli,__main__}.py`, `tests/test_report.py`, `tests/test_cli.py`. Update `README.md` with actual install-free usage and acquisition limitations.

**Interfaces:**
- Consumes: ingestion, scoring, reference, comparison and verdict functions from Tasks 2–6.
- Produces: `report.render_html(evaluation: JsonObject, verdict: JsonObject) -> str`, `report.write_json_artifacts(out: Path, *, evaluation: JsonObject, verdict: JsonObject) -> None`, `report.write_report(run: Path, evaluation_path: Path, out: Path) -> Path`.
- Produces: `cli.main(argv: list[str] | None = None) -> int`, `cli.evaluate_run(run: Path, out: Path) -> int`; `__main__.py` exits with `main()`'s result.
- `evaluate_run` verifies run → scores → checks reference → assesses → builds verdict → publishes evaluation/verdict. Structural/reference errors return 2; a valid emitted blocked comparison returns 3; eligible/no requested pair returns 0. `report` consumes those outputs without rescoring. No threshold criterion changes the exit code.

- [ ] **Step 1: Write output and CLI tests.** Call real subprocess commands using `sys.executable`, temporary directories and network access disabled. Assert all three commands' flags from spec section 9, help, exits 0/2/3, blocked verdict emitted, and missing/corrupt input produces no new valid-looking output. Verify repeated identical replay yields identical canonical/JSON/HTML bytes; different run/protocol identities in a reused output path are rejected. Simulate interruption before publication and verify the previous complete output survives or no final output exists.

For HTML, assert `<script>`/quotes/`</script>`/Unicode in query/title/snippet/source text are escaped; `javascript:` and `data:` URLs are not anchors; `http`/`https` links use escaped attributes. Assert all cases and attempts, native vs delivered metrics, unavailable cost, comparison settings/gates, and the four required caveats are visible. Parse HTML with `html.parser` to assert there are no script or external asset references; no browser dependency.
- [ ] **Step 2: Run red.** `python -m unittest discover -s tests -p test_report.py -v` and `python -m unittest discover -s tests -p test_cli.py -v`; failures should be missing report/CLI behavior.
- [ ] **Step 3: Implement local output and orchestration.** Use argparse, stable JSON serialization, html escaping and a scheme allowlist. Include provenance and limitations before comparisons, then inspectable case details without scripts. Verify input/output identities and publish staged derived output without replacing evidence. Execution timestamps go to logs outside deterministic artifacts. Reference reconciliation errors remain blocking even if JSON can be rendered.
- [ ] **Step 4: Run green and demonstrate A.** Run focused tests and `python -m unittest discover -s tests -v`, then the exact `freeze`, `evaluate`, `report`, and oracle commands in spec section 9 for A. Open local HTML for a human smoke review; record commands and supported/blocked conclusions. No paid API or network traffic is permitted during these commands.
- [ ] **Step 5: Commit.** Stage CLI/report/tests/README; check staged diff; commit `feat: generate inspectable offline pilot evidence reports`.

### Task 8: Freeze and run protected corruption/healthy validation

**Files:** Create `fixtures/corruptions/manifest.json`, `fixtures/controls/manifest.json`, `tests/test_corruptions.py`, `tests/test_controls.py`, `docs/evidence/validation.md`. Update `protocol.json` with the frozen manifest hash before protected execution.

**Interfaces:**
- Consumes: spec C01–C20/eight controls and the frozen tool/API.
- Produces: `tests/support.py` helpers `apply_mutation(parent: Path, mutation_id: str, out: Path) -> Path` and `collect_findings(run_or_input: Path) -> set[str]`, with manifests defining required stages/statuses as well as codes. Helpers do not implement scoring or mutate original packets.
- Produces: a frozen denominator, baseline/control expectations, protected results and explicit acceptance decisions.

- [ ] **Step 1: Write the exact cases and healthy expectations.** Implement 20 distinct mutation recipes mapped one-to-one to spec C01–C20, mark the 12 critical IDs, include parent hashes, intended changed fields and expected code/metric/eligibility effects. Write the eight healthy controls and their expected limitations. Do not tune expected findings to protected results.
- [ ] **Step 2: Write runner assertions and verify red with an intentionally disabled diagnostic in a throwaway copy.** Tests must fail for the missing intended finding, not merely because any exception occurred. Rehash downstream mutated copies so only C01 is stopped at the raw hash gate; regenerate structurally valid canonical/ledger identities where needed. Verify the original parent hashes remain unchanged.
- [ ] **Step 3: Freeze the validation assets in Git.** Set the manifest hash in the protocol, verify expected/control definitions and commit `test: freeze evidence corruption and healthy-control protocol` before protected evaluation. B's predeclared packet entry remains unchanged.
- [ ] **Step 4: Run the frozen suite against protected copies.** `python -m unittest discover -s tests -p test_corruptions.py -v` and `python -m unittest discover -s tests -p test_controls.py -v`. Count detection only when the expected fault reaches its owning stage and yields the correct code/state. Record detected/total, critical detected/total and unexpected healthy findings separately. The acceptance harness asserts aggregate thresholds; an undetected noncritical case remains in its results and denominator rather than being relabeled a passing detection.
- [ ] **Step 5: Verify acceptance without changing the denominator.** Require 12/12 critical, at least 18/20 total and 0/8 controls with unexpected findings. Disclose every undetected case. A failed critical/healthy requirement fails acceptance; do not relabel or remove cases. Product fixes require ordinary red/green tests and a versioned rerun; protocol/expected changes invalidate the protected claim and require a newly reserved evaluation.
- [ ] **Step 6: Commit results.** Commit `docs: record protected accounting validation results` with the measured outcomes and limitations. Stage only original manifests, mutation recipes, tests and results; never overwrite or mislabel the acquired originals.

### Task 9: Import B through configuration and reproduce from a clean directory

**Files:** Update only `fixtures/config/packet-b.json` and provenance entries needed for B; create `docs/evidence/{reproduction,poc-assessment}.md`; complete `workflow-comparison.md` and README. Product code remains frozen for this acceptance attempt.

**Interfaces:**
- Consumes: the frozen tool, source packets, protocol, independent/native baselines and protected-suite results.
- Produces: B run/output, exact reproduction recipe, coverage inventory and separate positive/neutral/negative/unassessed PoC workflow assessment.

- [ ] **Step 1: Release B and import without code changes.** Complete its source profile configuration using the existing documented shape; run the same freeze/evaluate/report commands with B paths. Do not patch source rows. If B needs new code/schema/profile logic, record that configuration-only acceptance failed; a subsequent extension is a new evaluation, not a silent success.
- [ ] **Step 2: Check both baselines and coverage.** Run the standalone oracle and pinned unchanged replay for each supported packet/metric. Verify exact counts, absolute `1e-9` metric agreement, and at least 200 distinct queries/50 distinct source groups total with identity deduplication across providers/packets. Keep each cohort separate; do not pool incompatible runs to meet comparison requirements.
- [ ] **Step 3: Reproduce offline from a clean temporary checkout/export.** Copy only committed code/docs plus the pinned hashed evidence/baseline dependency artifacts; exclude existing databases/output/caches. Record Python and upstream environment versions. Disable network access in the reproduction harness, rebuild both runs, re-evaluate, render reports and run `python -m unittest discover -s tests -v` plus `python reference/oracle.py --run RUN`. Verify native replay works using retained local artifacts, not a fresh download.
- [ ] **Step 4: Compare stable results.** Compare normalized canonical records and digest, metric/diagnostic/verdict JSON, and report bytes to the first execution in the same recorded environment. Exclude SQLite bytes and separate execution logs only. A manual row edit, network dependency, unknown provenance or changed normalized verdict fails clean reproduction.
- [ ] **Step 5: Assess workflow value and limitations.** Record B's existing baseline preparation independently and list every download/setup command, bespoke conversion/analysis action, configuration edit, manual row edit and packet-specific code change for both workflows. Positive requires all correctness acceptance plus zero row edits, zero B-specific code, and fewer bespoke conversion/analysis actions; neutral means correct but no material reduction; negative means the specified incorrect-conclusion failures; unperformed evaluation is unassessed. Do not convert these proxies to hours/revenue saved. Record archive gaps, incomplete costs, sample uncertainty and internal duplication unknowns.
- [ ] **Step 6: Commit the handoff.** Verify the final full suite, clean offline replay and `git diff --check`. Commit `docs: demonstrate second-packet replay and assess PoC value` with configuration/provenance/results/README changes. Inspect branch status/history and report actual outcomes, including unmet gates. Do not call the PoC successful on documentation or synthetic tests alone.

## Four-day timeboxes and acceptance map

Day 1 is Task 1 and its stop/reuse decision. Day 2 targets the narrow end-to-end path in Tasks 2–7, with basic rendering and no report polish. Day 3 freezes/runs Task 8 and verifies grouped comparisons on protected evidence. Day 4 is Task 9. Task numbers state dependency order. These are timeboxes, not measured effort estimates; source complexity can consume the budget. If time is tight, defer report polish and disclose unfinished acceptance work; do not expand beyond Scholar, weaken the frozen suite, or claim a skipped gate passed.

| Requirement | Owning tasks and evidence |
| --- | --- |
| Real gold/task outputs frozen, source lineage, 20 examples | 1, 4: manifests, profile, independent reconciliation |
| Reuse/kill gate and bounded keyless fallback | 1: explicit acquisition/duplication decision |
| Canonical JSONL plus one real NEEDLE adapter | 2, 4: contract tests and packet A import |
| Immutable assignments/physical requests, unknown archive history | 3–5: transaction/digest/retry tests, counts |
| Native metric preservation, deterministic identifiers, oracle agreement | 1, 5, 9: pinned replay/literal examples/exact counts and `1e-9` |
| Missingness/provider/runner distinctions | 5, 6: H/M/F/U tests, partition identity, gates |
| Comparable cohorts/settings, no false pairing, grouped uncertainty | 6: gate matrix and independent resampling checks |
| Cost provenance and no missing-as-zero | 2, 6: provenance and completeness tests |
| Offline escaped HTML plus verdict and CLI | 7: subprocess/output/HTML tests and local review |
| All critical, >=90% total corruption coverage, healthy controls clean | 8: frozen 12/12, >=18/20, 0/8 unexpected results |
| Second packet by config, 200 queries/50 groups, workflow comparison | 9: B commands, inventory and action ledger |
| Clean offline replay and qualified verdict | 9: independent clean directory, hashes/metrics/report agreement |

## Plan self-review and execution handoff

Before executing, verify that Task 1's source-fact annex is populated from real evidence. All later interfaces above use the same `Packet`, evaluation keys, diagnostic shape and decision scope. The five Review Focus items have named tests; source-dependent native field paths deliberately belong to the acquisition gate rather than fabricated instructions here. This plan contains no implementation or test-result claims.

The current request ends with the spec and plan committed. Review both documents before any implementation. A later execution request should preserve the current-branch instruction, use the chosen Superpowers execution skill, and stop or shrink the project when Task 1 warrants it.
