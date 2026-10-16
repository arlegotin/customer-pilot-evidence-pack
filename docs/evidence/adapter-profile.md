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

The supported matching identifiers are `needle-scholar-73c7f810` and the
existing synthetic-fixture alias `literal-v1`. Both select these pinned
Scholar URL/title/snippet extraction and normalization rules, including the
frozen snippet budget and optional conversion map; `literal-v1` does not
declare a separate matching algorithm. Other identifiers are rejected before
scoring by both packet validation and the independent oracle. A future
identifier requires an implemented matcher and independent reference support.
The standalone oracle also accepts the original direct-JSONL exports, which
can omit a protocol and profile claim. Those use its implicit pinned literal
rules; every explicitly supplied profile is still checked. A packet declaring
a protocol hash cannot omit that protocol and fall back to this legacy input.

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

## Product canonical v1 schema contract

`pilotpack.schema` provides a frozen `Packet` dataclass, `ValidationError`
(with a list of structured diagnostics), `load_json(Path)`,
`load_jsonl(Path)`, and `validate_packet(Path)`. Decoding rejects duplicate
keys, nonfinite numbers (including overflowing exponent notation), non-object
records and blank JSONL rows. Semantic validation separately accepts disclosed
unknown evidence; it never replaces nulls with defaults. Unknown core fields
are rejected; annotations such as the reference driver's `native_profile`
belong in `extensions` in product packets.

A product run contains `packet.json`, `protocol.json`, `sources.json`, and
`tasks.jsonl`, `assignments.jsonl`, `outcomes.jsonl`, `attempts.jsonl`, plus the
inventoried source files. `sources.json` uses the existing envelope
`{"schema_version":1,"sources":[...]}`. Source objects use `source_id`,
`role`, `source_uri`, `revision`, `acquired_at`, `local_path`, `bytes`,
`sha256`, `license`, `parents`, `command`; optional `limitations` documents
missing immutable revision. References use `<source-id>#line=N` (1-based) or
`<source-id>#$...`. Inventory paths and hashed paths must stay under the run
root, including after symlink resolution.

The full manifest requires the section 5 identity/evidence fields and a
`hashes` object mapping run-relative file names to lowercase SHA-256 strings;
this covers canonical JSONL, protocol, sources and each source artifact.
`protocol_sha256` must match the protocol entry. `reconciliation_note` is
required for reconstructed assignments. New-run manifests additionally
require `assignment_manifest_frozen_at` and `assignment_manifest_sha256`;
freezing after an evidenced dispatch is `MANIFEST_AFTER_DISPATCH`.
`content_id` and `normalized_table_digest` are optional until freeze/ledger
creation; they are integrity checks owned by subsequent ingest/ledger stages.

Protocol v1 preserves the checked-in acquisition policy's exact top-level
fields, including `status`, `actual_retry_policy`, `comparison_blockers`, and
the reserved `packets` metadata. Each arm and each manifest actual-settings
entry declares all settings fields from section 5. Actual mode, endpoint,
query parameters, retry policy, timeout, concurrency and window may be null;
`snippet_chars` may also be null. Known result count and k remain positive
integers, with `k <= requested_num_results`. `snippet_chars=0` is valid and
means no cap. Unknown actual settings require manifest limitations and yield
`UNKNOWN_ACTUAL_SETTINGS` blocks rather than schema errors. Unknown or partial
physical history yields `UNKNOWN_ATTEMPT_HISTORY` limitations.

`decision_criteria` maps protocol arm IDs to null or objects whose optional
keys are exactly `min_delivered_hit_rate`, `max_provider_failure_rate`, and
`max_unknown_rate`. Every present non-null threshold is a finite numeric
rate in [0,1], excluding booleans. Unknown arms/criterion names are invalid;
empty objects and null thresholds preserve descriptive reporting. Bootstrap
configuration is explicit (`seed`, `replicates`, `confidence`); requested
comparisons use objects with `arm_a` and `arm_b`. Non-null run/comparison
windows use `started_at` and `ended_at` timezone-aware RFC3339 strings.

The intentionally narrow v1 observed-cost witness is a source JSON object
referenced at `#$`, with `request` equal to the physical `attempt_id`, and
`amount`/`currency` equal to the cost record. Merely naming an existing source
or an assignment does not prove a request's cost; missing/incorrect evidence
is `INVALID_COST_PROVENANCE`. The amount is a nonnegative fixed-point decimal
string; observed `"0"` is valid with this evidence. Missing cost retains null
amount/currency/source_ref. A missing request measurement requires explicit
attempt limitations. This acquired archive has no cost witness and therefore
continues to report missing cost. Other cost-source shapes require an explicit
adapter transformation and retained parents, rather than accepting an
unverifiable observed amount.

Task identities are source IDs, never query text. Missing outcome records
survive validation with an assignment-scoped `MISSING_OUTCOME` block; the
subsequent accounting stage must synthesize explicit unknown outcomes before
publication. Validation does not manufacture attempts or decide retry
selection, cohort compatibility, native metric support or comparative gates.
`fixtures/canonical/schema-small` is a separate hand-authored synthetic
control with two equal-text tasks, four assignments, one physical request,
known no-cap settings, unknown archive settings/history, and an evidenced
zero cost. The earlier `ten-assignments` reference fixture remains unchanged.

## Product ingestion and frozen provenance

`pilotpack.ingest` implements the observed archive profile independently of
`reference.prepare_packet`. `freeze` accepts the explicit selection config,
protocol and source registry paths. A plain packet selection config carries
no implicit repository root or policy lookup. Direct `import_needle_scholar`
callers supply the reserved runtime context
`config['_context'] = {'protocol': loaded_protocol, 'sources': loaded_registry,
'source_root': provenance_root}`. This context is supplied by `freeze` from
its explicit arguments. Runtime roots never enter content identity.
`import_canonical` instead validates the input directory's contained protocol,
source inventory and canonical records; `freeze` requires them to agree with
its explicit protocol/source inputs. Source task, assignment and source IDs
are preserved. Direct adapters return normalized records; publication performs
strict canonical schema, retained-fragment and ledger verification.

The production archive join uses all raw gold rows and the full documented
query/group/bucket tuple. Duplicate IDs/tuples, orphan terminal rows and
result-count mismatches abort. Versioned co-archival evidence and the packet's
protocol-pinned source hashes are required for reconstructed assignments.
An absent terminal row for an evidenced intended assignment becomes an
explicit `unobserved` / `unknown` outcome, with no physical attempt inference.
Frozen `raw/reconciliation.json` identifies that inference and its original
assignment evidence. Intended counts are checked against assignment rows.
For new canonical runs, the original pre-dispatch assignment-manifest bytes
are retained and checked against `assignment_manifest_sha256`; schema
validation also checks that the frozen timestamp precedes dispatch.

A freeze copies the selected A source artifacts, A inventory, and required
baseline parents only. Protected B artifacts are absent from A's retained
source set. B's checked-in config was prepared from the reserved source IDs,
run inventory and precommitted selector; its provider outcomes remain unread.
All 384 A tasks remain in unchanged raw gold; every excluded PMID task and
original source line is recorded in `raw/exclusions.json`. The original
all-engine `ultimate` remains in the retained slim summary and creates no
real-provider assignment.

The frozen source inventory includes `baseline-native`, `baseline-oracle`,
`baseline-check`, and their pinned `needle-source` parent. Downstream readers
locate these through source IDs and run-relative paths in `sources.json`,
not repository-relative files. The sidecars are original hashed baseline
bytes, with their acquisition commands and parent IDs retained. The product
runtime remains standard-library-only; it does not import the independent
reference exporter or native scorer.

`raw/normalization-input.json` binds the logical selection config and every
authoritative derived manifest field, including origin/basis, actual settings,
intended counts, limits and cohort/profile selection. Its bytes are inventoried
as a derived source and included in the prescribed raw/canonical/source/policy
content map. `verify_run` requires exact agreement with `packet.json`, so valid
manifest-only edits are detected even though `packet.json` is excluded from
`content_id`. Hashes and content/digest fields are excluded from this snapshot
to avoid cycles. Generated source timestamps use an explicitly labeled fixed
serialization marker, with no claim about collection time.

Canonical object keys are sorted and compact; records sort by identity and
result order is preserved. JSON is UTF-8 with escaped non-ASCII characters,
finite values and a final LF. Incoming JSONL separates physical records on LF
(and accepts CRLF), preserving literal Unicode separators inside JSON strings.
The content identity hashes the sorted relative-path/byte-SHA256 map of raw
inputs, canonical JSONL, optional identifier map, sources and protocol; SQLite,
`packet.json`, and derived output are excluded. Protocol bytes retain their
explicit supplied identity. Canonical record reordering leaves content and
normalized SQL identities unchanged.

Before publication, every ordinary source reference is resolved to a retained
physical line or an existing JSON object/array path. Escaping symlinks and
traversal are rejected before canonical core decoding. All source bytes and
hashes, canonical records, reconciliation rows, SQL records and normalized
digest are verified in a sibling staging directory. An exclusive empty
reservation followed by directory rename publishes the completed run on the
supported local POSIX filesystem; an existing destination is refused. Failed
staging is removed. `verify_run` uses read-only SQLite access and writes no
run bytes or metadata.

Baseline linkage is explicit: the selection config's `baseline_source_ids`
object maps `native`, `oracle`, and `check` to source IDs. The same map is
frozen at `packet.json.extensions.baseline_source_ids`; a consumer resolves
those IDs in the run's source inventory. Source parents are copied recursively.
A's map is `native=baseline-native`, `oracle=baseline-oracle`,
`check=baseline-check`. There are no packet-A filename defaults in the adapter.
B's reserved config has an empty baseline map until independently generated,
provenanced B sidecars are available. The generic mapping can select them
without product code changes. `extensions.native_profile` names the replayed
denominator profile; `extensions.exclusions_source_id` identifies the retained
excluded-task manifest; `extensions.selection` records cohort ID and selector.

## Review corrections: pre-dispatch intent and conversion-map evidence

A retained pre-dispatch assignment manifest is parsed as strict UTF-8 JSONL,
and its complete assignment objects must match the canonical assignment set.
This includes assignment/task/arm/settings IDs, source evidence and extensions.
Row order, JSON object key order and formatting may differ; missing, extra,
duplicate or changed rows fail `MANIFEST_CONTENT_MISMATCH`. A genuine SHA256
of unrelated bytes is insufficient. Both initial canonical import and frozen
reopen perform this reconciliation as well as byte-hash and timestamp checks.

A supplied conversion map is retained byte-for-byte at `RUN/identifier-map.json`
and at its inventoried raw source path. Its canonical path participates in the
content map. `packet.json.extensions.conversion_map` records
`{"status":"available","source_id":"<inventoried-source-id>"}`;
canonical bytes, source bytes/length/SHA256 and
`protocol.conversion_map_sha256` must agree. The source preserves acquisition
and transformation parents. At initial canonical import, a unique source whose
local path is `identifier-map.json` supplies this link automatically; a map
retained at another source path needs the explicit link. For the archive path,
optional `config.conversion_map` supplies the same explicit link, selecting its
source and parent closure from the provided registry. No map source/path is
inferred from repository state.

A required conversion map explicitly unavailable at initial import is a
supported evidence limitation. It requires
`extensions.conversion_map = {"status":"unavailable","source_id":null,
"reason":"<specific absence reason>"}` (or the same archive config object).
There must be no contradictory supplied map bytes or canonical-map source.
Import and reopen reproduce one `MISSING_MATCH_EVIDENCE` block diagnostic at
scope `conversion_map`; all original tasks/outcomes remain intact. Task 5 must
mark metrics that require that conversion unsupported, with no fabricated
misses or new identifier lookup. This absence state is part of the authoritative
manifest binding and frozen content identity.

A claimed/supplied map without policy pinning/provenance, mismatched hashes or
bytes, or removal of a previously available frozen map is an integrity failure
(`CONVERSION_MAP_INTEGRITY_MISMATCH`, or an earlier canonical/source hash fault).
It cannot be downgraded to initial missing evidence by rehashing the remaining
files. An unmarked missing protocol-pinned map also fails; explicit initial
unavailability distinguishes incomplete evidence from broken retained evidence.
The map JSON object is strictly decoded, but conversion interpretation and
coverage are assigned to scoring; ingestion adds no matching algorithm.

## Comparison and absolute decision policy

`pilotpack.compare.assess(packet, evaluation)` consumes the verified Packet and
Task 5's independently reconciled evaluation. It returns a copy, without another
oracle invocation or changes to the frozen run. Only
`protocol.requested_comparisons` generates pairs; an empty list requests none.
Each pair retains scoped gates and remains blocked when its actual request
settings, retry policy, cohort or temporal window cannot be established. Explicit
`protocol.comparison_blockers` remain binding. A's unknown actual settings and
retry history do not establish a fair provider comparison. Distinct exact modes
are allowed when each is evidenced and matches its own frozen arm declaration.
A known actual/declaration mismatch also blocks the affected arm's decision.

Unknown comparison conditions are recorded at
`metric:arm:<arm_id>:comparison_conditions` and gate requested pairs. They do not
erase independently supported absolute H/M/F/U accounting. Missing physical
history limits exact attempts, observed total cost and request efficiency;
supported logical delivery can remain evaluable when retry selection is known.
Unavailable conversion coverage blocks only affected assignment judgments;
a direct confirmed hit can retain delivered recall while its exact first rank
and native MRR remain unavailable. A canonical packet with no original native
metric has no original native-replay obligation; independent oracle agreement
is still required.

`protocol.decision_criteria` remains empty for the acquired baseline. To declare
criteria, freeze a new protocol identity with a map such as
`{"arm_a":{"min_delivered_hit_rate":0.6},"arm_b":{"max_provider_failure_rate":0.1,"max_unknown_rate":0.05}}`,
using actual arm IDs. These are examples, not recommended thresholds or
acquisition observations. Missing/null thresholds mean `descriptive_only`.
Hit-rate thresholds use the entire missingness range; F/N and U/N are exact.
Decisions stay keyed by arm, and pair eligibility is separate. There is no
automatic winner or run-wide customer decision.

Eligible complete pairs use exactly 2,000 source-group bootstrap replicates,
seed 0, and nearest-rank 2.5th/97.5th endpoints. Sorted group IDs make replay
stable; every query variant and both arms move together. Each resample computes
query-weighted rates, including F as non-hits. Any U suppresses this interval;
its missingness identification range remains separate. Fewer than two groups
makes bootstrap unavailable; fewer than 50 carries a small-group qualification.
The result records the Python version, estimand and counts.

Observed request cost uses decimal strings, evidence-backed zero, one currency,
attempt scope, complete physical history and coverage of every attempt. Missing,
estimated, mixed-currency or incomplete evidence yields `total=null`; known
subtotals and coverage remain visible. The helper relies on ingestion's strict
request-specific receipt validation. Original archive latency samples remain
marginal, with source references and their native eligibility metadata. Only
selected-response-linked measurements on every task in both eligible arms can
supply paired latency; arrays are never zipped onto tasks. `build_verdict`
retains identities, source inventory, accounting, per-arm availability, pair
findings, decisions and reference checks while leaving full case records in
`evaluation.json`.
