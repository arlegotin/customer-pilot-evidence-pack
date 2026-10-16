# Unchanged native offline baseline

This Task1 baseline snapshot is supplemented by [Task9 reproduction](reproduction.md)
for both packets. The retained-wheel fresh install there adds `--no-cache-dir`
and verifies all current native/oracle ranks and stable outputs offline. The
original Task1 artifact hashes remain historical; the root source registry has
since added released B and its derived baselines.

Interpreter: Anaconda `python` 3.11.5, in an isolated venv. Only the
`run_papers` import closure is installed (`httpx` plus dependencies), not
unrelated generation/tokenizer dependencies. Exact package/wheel hashes are
in `reference/native-requirements.txt`; retained artifact inventory is in
`reference/retention-manifest.json`. This is a minimal replay environment,
not the original collection environment, whose dependency lock is absent.

The driver checks every pinned upstream Python source hash, imports unchanged
`needle.scholar.score.run_papers`, and injects archived responses through
stored-response clients. It drops cached IDs/matched/rank fields before
native extraction. Network socket connection and DNS entry points are denied;
ID conversion is not invoked for the selected arXiv cohort. Neither live
searches nor judgments occur. Native source and license are unmodified.

```sh
.cache/native-venv/bin/python reference/needle_replay.py --packet fixtures/real/packet-a --checkout .cache/needle-pinned --out docs/evidence/packet-a-native.json
python reference/prepare_packet.py --input fixtures/real/packet-a --config fixtures/config/packet-a.json --out reference/runs/packet-a
python reference/oracle.py --run reference/runs/packet-a > docs/evidence/packet-a-oracle.json
```

These commands exit 0. `packet-a-native.json` records zero rank/metric
discrepancies versus archived rows on 324 selected tasks per arm.
`reference-check.json` records zero oracle/native discrepancies at absolute
`1e-9`; counts and all 972 assignment ranks agree exactly.

| Arm | Native num_scored | Hits | Search errors | Native recall@10 | Native MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| bing | 324 | 157 | 0 | 0.4845679012345679 | 0.4593743876151283 |
| keenable | 324 | 293 | 0 | 0.904320987654321 | 0.8723765432098767 |
| perplexity | 324 | 0 | 324 | 0.0 | 0.0 |

These are descriptive archive observations on an explicitly selected cohort;
actual comparison conditions are unknown. No provider ranking is supported.
The independent oracle's reciprocal-rank summation order gives keenable
`0.8723765432098765`; difference is about `2.22e-16`, below tolerance.
All three have U=0 in this projection. No physical attempts are manufactured;
observed physical rows=0, exact physical totals=null for every arm.

The pinned `recall_summary` defaults its scored list to every per-query row,
and `run_papers` does not pass an error-filtered list. The all-error native
arm still has `num_scored=324`, search_errors=324 and zero recall/MRR. Thus
**this revision's denominator includes search failures**. The README's
"mean skips" prose does not apply to this actual implementation. Do not
replace its behavior with H/(N-F). Native group summaries also include all
rows. A zero-native-scored convention is 0.0 in upstream, but the pack's
undefined delivered rate remains null.

Full original 384-task cached summary recomputation through unchanged
`recall_summary` also matches the downloaded original summaries. This only
verifies native reporting over stored ranks; **full 384-task re-extraction
is unsupported** without historical PMC conversion evidence. The full
published values remain in original raw files and under
`full_archive_cached_summary` in replay JSON. They must not be described as
reproduced extraction metrics. The raw all-engine `ultimate` summary is
retained; selected-engine replay ceiling is separate. The subset cannot
reproduce original all-engine miss-classification or latency populations.

Clean offline verification used a second venv and no package index:

```sh
python -m venv .cache/native-clean
.cache/native-clean/bin/python -m pip install --no-index --no-cache-dir --find-links .cache/wheels --require-hashes -r reference/native-requirements.txt
.cache/native-clean/bin/python reference/needle_replay.py --packet fixtures/real/packet-a --checkout .cache/needle-pinned --out /tmp/task1-clean-native.json
cmp docs/evidence/packet-a-native.json /tmp/task1-clean-native.json
```

The recipe above includes the deferred `--no-cache-dir` correction. The
original Task1 install omitted it; Task9 actually exercised the corrected
flag in a fresh guarded environment using the same retained wheels.

Task1 installation/replay/cmp all exited 0; derived replay bytes are identical.
Pip emitted a harmless unavailable user-cache warning and disabled that
cache; all installs came from retained wheels. Output hashes are frozen in
`baseline-hashes.json`. Timestamps and acquisition logs are separate from
deterministic metric JSON.
