# Frozen accounting validation

Protocol `protected-validation-v1` freezes C01–C20 (12 critical; minimum 18/20 total) and H01–H08 (zero unexpected findings). Exact diagnostic codes, stage, H/M/F/U counts, selected response and availability/pair states are in the committed manifests. No cases or expected states may change after protected execution. Undetected noncritical cases stay in the denominator. Product fixes require focused regression tests and a versioned rerun preserving the initial results.

The hand-authored six-assignment parent is synthetic, with a hit, miss and provider error in each arm. Its settings and receipts are synthetic evidence, never claims about provider defaults. Every recipe copies it, updates downstream provenance where appropriate, then independently freezes through the real importer/ledger/oracle/comparison pipeline. Only C01 intentionally retains stale hashes. C18 is structurally invalid JSON by definition. Parent tree hashes bind every original filename/byte. Originals are verified before and after each case. C17 declares unavailable historical conversion evidence and requires unsupported affected matching; loss of integrity for a claimed-present frozen map is a separate rejection condition.

Controls explicitly allow missing cost; H03 allows unavailable physical history without a retrieval block. H02 keeps a completed unknown judgment distinct from a miss. H08 includes a hand-derived native `ultimate` ceiling without a selectable `ultimate` arm. Required codes alone never count as detection when state or owning-stage assertions fail.

The root protocol uses a new identity and declares the real bing/keenable requested pair before freeze. Acquired A/B source metadata is preserved; actual real settings remain unknown and must block comparison. Historical runs retain their historical protocols. B source bytes remain unopened until Task 9.

Before freeze, the healthy parent imported, scored and compared as eligible with exact baseline H/M/F/U. A throwaway C01 copy with only `HASH_MISMATCH` diagnostic emission deliberately disabled failed the runner assertion specifically with `missing intended finding HASH_MISMATCH` (one failure, no incidental exception). Command: `PYTHONPATH="$PWD" python /tmp/validation_red_probe.py`. This demonstrates the harness demands the intended finding. No protected full suite was executed before the freeze commit.

Protected commands (results will be appended without replacing this declaration):

```
PILOTPACK_VALIDATION_RESULTS=docs/evidence/validation-initial python -m unittest discover -s tests -p test_corruptions.py -v
PILOTPACK_VALIDATION_RESULTS=docs/evidence/validation-initial python -m unittest discover -s tests -p test_controls.py -v
```

## Initial v1 result: failed and invalid for acceptance

Freeze commit: `69ee79e`. Initial protected commands above produced **10/20 detections, 5/12 critical, 8/8 healthy with zero unexpected controls**. Exact per-case codes/errors and console output are retained in `validation-initial/`. Undetected: C04–C10, C13, C15, C16. This run does not satisfy acceptance.

Three frozen harness defects invalidate a protected success claim: C05 expected unchanged b hit/miss counts despite substituted gold; C09 supplied null results although canonical outcomes require a ranked list, causing unrelated structural failure; C15 supplied valid zero receipts to b while expecting its total null. These are retained as failures, with no retroactive adjustment. Separately, ordinary focused regressions exposed missing stable spec diagnostics for missing outcomes, runner non-dispatch, forged cached rank, settings/window mismatch, unavailable total cost and marginal-only latency. Six focused regression tests failed before the product fixes and passed after; exact outputs are retained. Existing diagnostic aliases remain available.

The coordinator reserved **a separate v2 evaluation** with a newly authored parent, fresh task/group IDs and an additional literal known hit per arm. Only the three disclosed harness corrections and necessary literal new-parent projections are permitted. C01–C20, 12 critical and eight healthy denominators stay fixed. V1 definitions remain available in Git at `69ee79e`, and initial evidence is never overwritten. V2 is a newly reserved evaluation, not an uninterrupted first-pass protected claim. B remains unopened.
