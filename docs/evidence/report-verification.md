# Report publication verification

## Boundary and changed contract

The released `77b6082` report command verified frozen-file identity, case membership
and some summary relationships. It trusted other derived fields. Real CLI probes
confirmed acceptance of a missing requested pair, an eligible status retaining a
blocking gate, an unsupported `meets_criteria` decision, and a fabricated supported
zero cost. The first two changed exit 3 to exit 0. These were synthetic edits to
derived JSON, with unchanged frozen evidence; they are not faults in archived
provider responses or evidence of a general exploit severity.

`report` now reconstructs the entire evaluation from verified frozen inputs and
the frozen protocol. Scoring invokes the independent oracle; assessment starts
from these fresh diagnostics and reconstructs comparison gates, costs, latency,
settings, decisions, provenance and case/attempt records. The supplied JSON must
match the deterministic reconstructed values, including absence of extra claims.
JSON object key order/whitespace need not match. Counts, IDs and ranks are exact;
the native reconciliation tolerance remains absolute 1e-9. The trusted
reconstructed object is the object published and used for CLI exit selection.
The command never rereads the supplied path to choose its exit code.

This explicitly replaces the old **report without rescoring** contract and its
regression. A valid report now performs one fresh score/reference invocation;
repeat bytes remain stable in the same environment. The escaped pure
`render_html` renderer remains available for in-memory presentation but is not a
verification API. `write_report` still returns its HTML path; `publish_report`
returns the verified published evaluation for callers needing exit semantics.
`write_json_artifacts` now requires a `run` argument; omitted evaluation means
fresh generation, while supplied evaluation/verdict must independently reconcile.
Private `_publish` is a staging primitive for already verified values, not an
untrusted-input entry point.

The trust assumption is unchanged executable code and trustworthy frozen inputs.
Hashes, same-input identity strings and supplied passed flags are not
independent proof of derived claims. This does not protect against replacement
of both trusted evidence and code. Ordinary native checks reconcile retained
native sidecars; fresh pinned NEEDLE replay is a separate acceptance command.
Environment-sensitive deterministic fields must be reproduced in the recorded
Python environment. No unsigned receipt or invented authenticity claim is used.

## Evidence and scope

The new mutation catalog in `tests/report_mutations.py` is development regression
material, not a fresh holdout. It edits only derived claims: requested pairs,
status/gates, decisions/criteria, coherent hit/miss counts and cases, ranks,
results, settings, source inventory, reference flags, costs, latency, diagnostic
lists, attempts/retry selection, query/source fragments, native metrics,
limitations and extra claims. Tests execute real freeze/evaluate/report into
fresh and existing destinations, requiring exit 2, unchanged old complete output
and unchanged frozen bytes. A disclosed timing fault injection replaces the
supplied file after actual publication to test exit selection from the same
verified snapshot. It does not replace scoring or evidence validation.

Healthy blocked and unrequested controls, eligible controls and valid arm
threshold failures remain distinct from invalid inputs. Publication safety,
HTML escaping/locality, byte stability, lock contention and interrupted writes
are separate deterministic checks. Historical A/B comparisons stay blocked;
missing costs and exact physical counts remain unavailable. Human/browser
observations and operational work savings are not established by these checks.

Execution logs, code identity, machine verification cost and final review results
are recorded separately in the investigation evidence; historical v1/v2 records
are not overwritten.

## Run-window compatibility

A complete eligible canonical control confirmed that raw dictionary equality
blocked equivalent `Z` / `+00:00` and other known-offset encodings. The two
settings comparison sites now compare represented instants, preserving all
accepted fractional digits. Raw settings, protocol bytes and provenance hashes
are unchanged. RFC3339's `-00:00` unknown-local-offset convention remains distinct
from known UTC; missing, genuinely different and out-of-window intervals still
block. This follows the [RFC3339 offset distinction](https://www.rfc-editor.org/rfc/rfc3339.html#section-4.3)
and changes no historical A/B meaning because their actual windows are missing.
No general schema or temporal-policy redesign was performed.

## Publication path correction from final review

A real-process review found an inherited defect in lexical output aliases such
as `output/../output`: moving `output` to its backup made staging, rollback and
lock paths depend on the now-absent directory. An ordinary rename failure could
therefore leave only a recoverable backup. A new failing CLI regression and a
failing rollback regression reproduced this before the fix. Publication now
resolves the destination before moving any directory, after rejecting a final
symlink in the original path. Existing lock and rollback semantics are retained;
regressions also reject a final symlink pointing at a valid complete report.
The earlier clean candidate pass is retained as intermediate evidence, followed
by a fresh committed-candidate replay after this correction.

Malformed JSON, duplicate keys, explicit nonfinite literals and overflowing
nested numbers all produce `INVALID_REPORT_INPUT`/exit 2 before publication.
The overflow regression preserves its initial plain-diagnostic failure; the
failure was diagnostic classification, with no false publication.
The [CWE-345 description](https://cwe.mitre.org/data/definitions/345.html) is
conceptual context for insufficient verification, not a vulnerability rating
or a requirement for cryptographic signing.
