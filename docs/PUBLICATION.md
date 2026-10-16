# Publication scope

The current release is `v0.2.0`; the first release, `v0.1.0`, remains available.
Original software is AGPL-3.0-only; original
writing and result presentation are CC BY 4.0. [LICENSING.md](../LICENSING.md)
and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) define the boundaries.

## Published contents

The repository and source archives contain product/reference code, tests,
canonical controls, frozen protocols, reports of validation and reproduction,
source provenance, and unchanged selected NEEDLE gold/task-level results. The
real inputs were acquired from the public MIT-declared NEEDLE dataset; they
are not private customer exports. Source paths, acquisition timestamps,
historical local machine paths and failure records retain their original
meaning. The repository contains no provider credentials or installed
environments.

The offline-baselines asset contains the exact pinned NEEDLE source
tar and seven original dependency wheels at the relative paths expected by
`sources.json` and `reference/retention-manifest.json`. Its notices accompany
the bundle; original wheel license files remain inside each wheel. Extract it
into the checkout before real-packet imports: the original tar is required
provenance even without executing native code. The wheels are needed only for
native checks. Synthetic canonical inputs need no external assets. A source
archive can run product commands; the full replay procedure uses Git to make a
clean export and therefore starts from a clone.

The reports asset contains both packets' static HTML, evaluation/verdict JSON,
and the applicable notices. These are qualified descriptive reports. Both
requested provider comparisons are blocked; they are not purchasing advice.
Every downloadable asset has a SHA-256 digest in `SHA256SUMS`.

## Claims and recorded history

Supported inputs reconcile with independent/native checks across 649 unique
queries and 160 groups. Validation v2 detects 20/20 faults, including all 12
critical faults, and has zero unexpected findings across eight healthy controls.
Failed/invalid v1 remains published separately; no first-pass validation success
is claimed. The existing baseline also handled B through configuration, so
workflow value remains neutral. No hours or revenue savings were measured.

The historical clean experiment ran 190 tests. Final-review fixes added 12
ordinary regressions; v0.1.0 verified 202 tests. The v0.2.0 integrity changes
verify 233 tests with zero skips; [their evidence](evidence/integrity-2026-10-16.md)
retains the initial failures, three reviews and clean offline acceptance. Historical transcripts
remain unchanged. The current replay recipe records its actual discovered test
count and writes new logs under `build/reproduction`, separate from those
transcripts. [Final implementation verification](evidence/final-verification.json)
records unchanged A/B artifact hashes after those fixes.

Actual collection settings, full physical-attempt histories, exact cost totals,
paired latencies and full historical PMID extraction remain unavailable.
Browser/human visual usability is unassessed. Retrieval scoring does not validate
agent reasoning, answer quality or citation support.

## Conventions and attribution

Release preparation checked the latest `outcome-aware-context-allocation`,
`reasoning-allocation` and `adaptive-calculus` repositories in the owner's
account. Their code/writing split, author attribution and CFF citation pattern
are used here. README prose was edited with the requested
[write-like-me](https://github.com/arlegotin/write-like-me) skill. Cite
[CITATION.cff](../CITATION.cff) and record the exact commit used. No DOI, peer
review, affiliation with Keenable or independent replication is claimed.
