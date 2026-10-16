# Clean offline reproduction

## Current release recipe

The original experiment below used a 190-test source revision. The current
release has 202 tests. The runnable procedure now records the actual suite
count and writes new logs only under ignored `build/reproduction`; it never
replaces historical transcripts. Original preparation and replay scripts are
retained as `prepare-clean-historical.py.txt` and `replay-historical.py.txt`
beside the current scripts.

Start from a fresh checkout with Python 3.11 and the retained native tar/wheels.
The optional `pilotpack-v0.1.0-offline-baselines.tar.gz` release asset supplies
those exact files. Extract it into the checkout before replay:

```sh
tar -xzf /path/to/pilotpack-v0.1.0-offline-baselines.tar.gz -C .
```

The procedure below rebuilds both packets with networking disabled. Inspect new
results in `build/reproduction/results.json`. Recorded results below describe
earlier runs, not the new execution.

## Historical experiment and runnable procedure

The replay exports committed inputs from `9474fdd` (the protected B release)
with `git archive --format=tar`. Only the SHA-256-checked pinned NEEDLE source
archive and seven retained dependency wheels are added. The export starts
without `.cache`, `runs`, `build`, `reference/runs`, SQLite files, environments
or old execution outputs. Raw A/B originals, source metadata and frozen
baseline sidecars are committed inputs, not a copied prior database or
verdict. The export inventory is [input-export.json](reproduction/input-export.json).

The retained historical text files contain the preparation and corrected replay
handoff procedure used in this experiment; the network guard is unchanged.
They are external to the frozen product/reference/test code. The original
acceptance transcript is preserved; the later fresh-workspace correction and
covering execution are identified below. The preparation script
performs a local Git export, verifies every retained wheel/archive byte count
and hash, and extracts a fresh unchanged native checkout. The guarded replay
then creates a new native environment in the clean export and runs only
explicit Python children. Both the launching-workspace and clean-output
passes reuse that freshly built clean interpreter and pinned checkout. The
launching workspace needs only committed files and the retained hashed source
tar/wheels; it needs no installed native environment or expanded checkout.
An inherited `sitecustomize` audit hook rejects DNS, connect/send operations,
non-Python process execution, and explicit `-I`/`-E`/`-S` child options that bypass site
initialization; the child wrapper restores the guard even when a caller
replaces its environment. Loopback connection, DNS, external executable, and
nested-child DNS probes all fail before networking. The guard leaves local
socket-pair creation available for asyncio. The actual probe output is
[network-probes-console.txt](reproduction/network-probes-console.txt).

Use the recorded Python 3.11.5 interpreter (the `python` command here), from
this checkout, with the retained artifacts at the exact paths in
`reference/retention-manifest.json` and the `needle-source` provenance entry.
Git alone does not contain those native dependencies. No package download is
part of replay. For a fresh workspace use the following commands once; the
freeze and independent exporter intentionally refuse existing run paths.

```sh
python --version
replay_work=$(mktemp -d)
mkdir "$replay_work/guard"
cp docs/evidence/reproduction/sitecustomize.py.txt "$replay_work/guard/sitecustomize.py"
cp docs/evidence/reproduction/prepare-clean.py.txt "$replay_work/prepare-clean.py"
cp docs/evidence/reproduction/replay.py.txt "$replay_work/replay.py"
clean=$(python "$replay_work/prepare-clean.py")
PYTHONPATH="$replay_work/guard" python "$replay_work/replay.py" "$PWD" "$clean"
```

`prepare-clean.py` uses current committed `HEAD`; the recorded acceptance
execution used `9474fdd`. Later final-review fixes add canonical-input validation
and 12 regressions; their separate [verification](final-verification.json)
reproduced all six real evaluation/verdict/HTML artifacts byte-for-byte. The
current recipe targets the checked-out committed revision. Protocol,
configuration, real raw evidence and historical baseline inputs stay frozen.
The original expanded commands, stdout, stderr and actual exit statuses are in
[command-log.json](reproduction/command-log.json). Its successful workspace pass
used the original workspace's already installed native environment/checkout.
The corrected handoff is separately exercised from an entirely fresh launching
root; its [command log](reproduction/fix-i1/command-log.json) records reuse of
the freshly built clean dependencies for both passes. Both transcripts remain
retained without rewriting the original acceptance evidence. The harness records
`os.uname()` directly so the strict subprocess guard need not allow a system
`uname` executable. All files used by the two tiny procedures are listed in
the scripts; no hidden database or generated source packet is required.

The fresh native setup runs exactly, with the clean export as its working
directory:

```sh
python -m venv .cache/native-venv
.cache/native-venv/bin/python -m pip install --no-index --no-cache-dir --find-links .cache/wheels --require-hashes -r reference/native-requirements.txt
```

The isolated baseline requires only the pinned `run_papers` import closure.
Python/native package versions appear in [results.json](reproduction/results.json),
and [offline-install-console.txt](reproduction/offline-install-console.txt)
records the retained-wheel-only install. This is the replay environment,
not the unavailable original collection environment.

For each packet A/B, the harness uses the same frozen adapter/configuration
and policy to freeze, evaluate and render. `freeze` exits 0. `evaluate` and
`report` both exit **3**, emitting qualified artifacts for the requested
Bing/Keenable pair with unknown actual settings/retry/window. That is the
expected comparison state, not a passing provider comparison. All three
arm decisions remain `descriptive_only`. It separately runs:

```sh
python reference/oracle.py --run runs/task9-packet-a
python reference/oracle.py --run runs/task9-packet-b
python reference/prepare_packet.py --input fixtures/real/packet-a --config fixtures/config/packet-a.json --out reference/runs/task9-reproduction-a
python reference/prepare_packet.py --input fixtures/real/packet-b --config fixtures/config/packet-b.json --out reference/runs/task9-reproduction-b
"$clean/.cache/native-venv/bin/python" reference/needle_replay.py --packet fixtures/real/packet-a --checkout "$clean/.cache/needle-pinned" --out build/task9-reference/a/native-replayed.json
"$clean/.cache/native-venv/bin/python" reference/needle_replay.py --packet fixtures/real/packet-b --checkout "$clean/.cache/needle-pinned" --out build/task9-reference/b/native-replayed.json
python -m unittest discover -s tests -v
```

Reference outputs stay in `build/task9-reference`, outside the product's
strict three-file publication directory. The exported independent baselines
and product standalone oracles agree byte-for-byte. Both fresh native replay
outputs agree byte-for-byte with their retained baseline sidecars. Every
selected native/oracle rank is checked exactly (A 972; B 984), as are
num_scored/search_errors; recall/MRR agreement uses absolute `1e-9`. Product
checks independently report passed for live oracle, frozen oracle, native
replay and frozen reconciliation sidecar.

The original Task 1 A oracle predates the later independent-oracle
`physical_attempt_count_lower_bound` field. Every retained original field
matches the current oracle exactly; current A additionally reports the
source-supported lower bound 324 for each arm. Its original bytes remain
unchanged. The current first-execution and clean oracle outputs do agree
byte-for-byte. This historical schema distinction does not waive any metric,
rank or fresh-replay equality.

Stable-result comparison checks each canonical JSONL file and every other
frozen run file except SQLite bytes, normalized records read from the ledger,
the normalized table digest, content/protocol identity, and complete
`evaluation.json`, `verdict.json` and `report.html` bytes. It also checks
fresh independent-oracle/native outputs. Execution logs and SQLite storage
layout are the only exclusions. The environment, per-file hashes, exact
rank counts, metric differences and stable equality results are retained
in [results.json](reproduction/results.json). No source-row repair, policy
change or network dependency is accepted.

The clean full suite passed **190 tests with no failures, errors or skips**. Both
packet stable-result comparisons passed. The full clean test output is [clean-suite-console.txt](reproduction/clean-suite-console.txt).
Browser/human visual smoke remains unavailable as disclosed in Task 7;
automated HTML/locality checks do not establish visual review. Full PMID
re-extraction, collection-time settings/physical histories, exact costs and
paired latency remain unsupported. A/B metrics remain separate cohorts.

## Fresh-workspace handoff correction (review I1)

The original acceptance execution remains valid, but its documented replay
procedure originally selected `root/.cache/native-venv` and
`root/.cache/needle-pinned` during the workspace baseline pass while creating
those dependencies only in the clean export. A fresh root with exactly the
stated retained artifacts therefore failed before native replay. The
[focused failing invocation](reproduction/fix-i1/red-console.txt) records the
missing interpreter/checkout without using prior runs or environments.

The one-line procedure correction committed at `2ba3888` uses the clean
export's freshly installed interpreter and verified checkout for both passes.
A second launching root was exported from that commit with only the hashed
source tar/seven wheels added. Before execution it contained no runs, build,
reference runs, native environment or expanded checkout
([fresh-root inventory](reproduction/fix-i1/corrected-root.json)). Because this
validation root was a Git export rather than a clone, `GIT_DIR` referenced
existing local repository metadata solely for the recipe's local
`git archive`/`rev-parse`; no branch, worktree or checkout changed.

The exact documented shell recipe above then ran there offline. Corrected
[results](reproduction/fix-i1/results.json),
[full command/output log](reproduction/fix-i1/command-log.json),
[network probes](reproduction/fix-i1/network-probes-console.txt),
[install transcript](reproduction/fix-i1/offline-install-console.txt), and
[clean suite](reproduction/fix-i1/clean-suite-console.txt) are retained separately
from the original execution. The launching root still has no native
environment/checkout afterward; no hidden root dependency was initialized.
Both packets' stable records/digests/evaluation/verdict/report bytes reproduce
exactly, supported ranks/counts/metrics agree, and the required harness suite
passes 190 tests with zero skips. The corrected result hashes also match the
original acceptance result hashes; all 37 expected command statuses and the
absence of launching-root native state are recorded in
[covering-check.json](reproduction/fix-i1/covering-check.json). No product/reference/test/protocol changes
were required.
