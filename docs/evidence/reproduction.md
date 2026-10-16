# Clean offline reproduction

The replay exports committed inputs from `9474fdd` (the protected B release)
with `git archive --format=tar`. Only the SHA-256-checked pinned NEEDLE source
archive and seven retained dependency wheels are added. The export starts
without `.cache`, `runs`, `build`, `reference/runs`, SQLite files, environments
or old execution outputs. Raw A/B originals, source metadata and frozen
baseline sidecars are committed inputs, not a copied prior database or
verdict. The export inventory is [input-export.json](reproduction/input-export.json).

The three retained text files below contain the exact executed preparation,
network guard and replay scripts. They are documentation of this experiment,
external to the frozen product/reference/test code. The preparation script
performs a local Git export, verifies every retained wheel/archive byte count
and hash, and extracts a fresh unchanged native checkout. The guarded replay
then creates a new native environment and runs only explicit Python children.
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
scratch=$(mktemp -d)
mkdir "$scratch/guard"
cp docs/evidence/reproduction/sitecustomize.py.txt "$scratch/guard/sitecustomize.py"
cp docs/evidence/reproduction/prepare-clean.py.txt "$scratch/prepare-clean.py"
cp docs/evidence/reproduction/replay.py.txt "$scratch/replay.py"
mkdir -p .superpowers/sdd/2026-10-16-customer-pilot-evidence-pack
python "$scratch/prepare-clean.py"
clean=$(cat .superpowers/sdd/2026-10-16-customer-pilot-evidence-pack/task9-clean-path.txt)
PYTHONPATH="$scratch/guard" python "$scratch/replay.py" "$PWD" "$clean"
```

`prepare-clean.py` uses current committed `HEAD`; the recorded acceptance
execution used `9474fdd`. Later evidence-only commits retain the same product,
profile, suite, protocol, configuration, raw evidence and baseline inputs.
The full expanded commands, stdout, stderr and actual exit statuses are in
[command-log.json](reproduction/command-log.json). The harness records
`os.uname()` directly so the strict subprocess guard need not allow a system
`uname` executable. All files used by the two tiny procedures are listed in
the scripts; no hidden database or generated source packet is required.

The fresh native setup runs exactly:

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
.cache/native-venv/bin/python reference/needle_replay.py --packet fixtures/real/packet-a --checkout .cache/needle-pinned --out build/task9-reference/a/native-replayed.json
.cache/native-venv/bin/python reference/needle_replay.py --packet fixtures/real/packet-b --checkout .cache/needle-pinned --out build/task9-reference/b/native-replayed.json
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
