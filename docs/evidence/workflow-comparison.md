# Existing workflow and PoC value

**Measured workflow outcome: neutral.** B imports correctly through the
frozen product with configuration/provenance changes only, but the generic
baseline established on A already processes B with path/configuration
arguments alone. Both require zero B-specific conversion/analysis code and
zero manual source-row edits. The pack does not demonstrate fewer bespoke
preparation actions. No hours, revenue, adoption or internal duplication
claim follows from these proxies.

The Task 1 duplication gate justified only the narrow accounting/replay
boundary: native archived reports contain results/errors/ranks but do not
supply immutable intended assignments, reconciled missingness, physical
history availability or comparison gates. The stored-response native driver,
bounded independent exporter and oracle written for A are reused for B.
This is a reuse outcome; no further evaluator/adapter scope is warranted by
the workflow result. Keenable/customer internal workflows were unavailable
for inspection, so internal duplication remains unknown.

The B baseline was executed **before** product import: release unchanged
files, run the independent exporter/oracle and unchanged native driver,
then compare their selected ranks/metrics. It did not import product code
or use product-normalized output as its input. The original B config already
specified archive/cohort/paths/arms/projection and explicit unknown settings;
it needed no baseline configuration edit. The subsequent product config
edit adds the native/oracle/check sidecar source IDs using the existing
adapter shape. Source registry edits change five release paths/roles and
add three hashed derived-source records. They do not repair a row.

| Activity for B | Existing independent/native baseline | Pack |
| --- | --- | --- |
| New downloads | 0; five original B downloads already retained | 0; same retained originals |
| Raw preparation | Verify reserved length/hash and copy five unchanged files | Same shared release step |
| New dependency setup | 0 in initial workspace; retained native venv | 0 product dependencies; same native environment for required reference check |
| Configuration edits | 0 after acquisition reservation | 1 config edit adding three baseline refs |
| Provenance edits | Record release paths/roles and derived artifacts | Same source registry is consumed by freeze |
| Required preparation/report commands | Export, oracle, native replay: 3 | Freeze, evaluate, report: 3 |
| B-specific bespoke conversion/analysis actions | 0 | 0 |
| Manual source-row edits | 0 | 0 |
| B-specific product/reference/schema/profile code | 0 | 0 |

Exact initial B baseline commands (all exit 0) were:

```sh
python reference/prepare_packet.py --input fixtures/real/packet-b --config fixtures/config/packet-b.json --out reference/runs/task9-packet-b
python reference/oracle.py --run reference/runs/task9-packet-b > docs/evidence/packet-b-oracle.json
.cache/native-venv/bin/python reference/needle_replay.py --packet fixtures/real/packet-b --checkout .cache/needle-pinned --out docs/evidence/packet-b-native.json
```

Exact initial product commands were:

```sh
python -m pilotpack freeze --adapter needle-scholar --input fixtures/real/packet-b --config fixtures/config/packet-b.json --protocol protocol.json --sources sources.json --out runs/task9-packet-b
python -m pilotpack evaluate --run runs/task9-packet-b --out build/task9-packet-b
python -m pilotpack report --run runs/task9-packet-b --evaluation build/task9-packet-b/evaluation.json --out build/task9-packet-b
```

Freeze exits 0; evaluate/report exit 3 for blocked requested comparisons.
The exact five original B acquisition expressions, URLs, UTC timestamps and
hashes remain in [sources.json](../../sources.json). They are five separate
`urlopen(immutable_url).read()` downloads, plus file writes/hashing while
opaque. The common source pin/metadata, wheel download/install and checkout
setup commands remain in [acquisition.md](acquisition.md) and
[native-baseline.md](native-baseline.md); no new download was introduced for B.

All additional acceptance work is listed separately so neither workflow
gets artificial credit: one raw-gold identity/coverage inventory extraction;
one independent selected-rank/metric reconciliation (984 exact B ranks);
one clean replay procedure with an inherited offline guard; one fresh native
venv creation plus one retained-wheel-only hashed installation; both packet
reference/product rebuilds; and full-suite verification. The exact replay
commands/outputs are in [reproduction.md](reproduction.md) and its command
log. Those verification/documentation procedures are new experimental work,
shared correctness evidence for both workflows, not a measured B preparation
reduction. No manual row editing or B-specific adapter logic occurs in them.

A's initial setup required four bespoke actions in the recorded grouping:
select/freeze supported cohort after tuple and missing-evidence inspection;
write the stored-response native driver; write the bounded independent
exporter; write the literal oracle and manually reconcile 20 examples.
Download/setup were separately grouped as source/dataset/action metadata pin,
selected A plus opaque B acquisition, and source/environment/wheel setup.
Those one-time actions do not become repeated B work when reusable scripts
already handle B. Their original exact acquisition expressions and methods
remain retained; the comparison does not fabricate a counterfactual baseline.

[coverage.json](coverage.json) records A 324 tasks/81 groups and B 328/82,
with 3 repeated query identities and 3 repeated groups: **649 distinct queries
and 160 groups** after deduplicating native `(paper_key,bucket,query_text)`
identity across packets/providers. Archive-hour task IDs do not inflate this
count. Cohorts are evaluated separately, never pooled to manufacture a pair.

Correctness and workflow conclusions remain separate: v2 detects 20/20
faults, all 12 critical, and has 0/8 unexpected healthy findings; failed v1
remains disclosed. Both packet baselines and the clean replay are checked.
Actual settings/retry/window are unknown, and real provider pairs remain
blocked. No physical history, exact cost, paired latency, full PMID extraction
or answer-quality claim is supported. Engineering counts are not a power
calculation; small provider differences and archive selection remain uncertain.
Browser/human smoke is unperformed and therefore unassessed. Full acceptance
and the positive/neutral/negative/unassessed distinctions appear in
[poc-assessment.md](poc-assessment.md).
