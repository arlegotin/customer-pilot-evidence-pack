# Acquisition and gate

Decision: **continue only the narrow accounting/replay PoC over the declared
arXiv projection; block provider-comparison conclusions**. Acquisition is
real and sufficient for that projection. It does not reproduce the complete
published 384-task extraction or satisfy the two-packet acceptance target.
Existing native configuration alone does not supply immutable intended
assignments, missing-outcome reconciliation, physical-history availability,
or comparison gates. A thin bounded export and oracle are now demonstrated;
product Tasks 2–9 remain conditional on preserving these limits. This is not
a successful provider comparison.

The newest two complete Scholar entries in native run inventory were
`2026-10-14T1506Z` (A) and `2026-10-15T1453Z` (B), each containing gold,
slim report, and per-engine artifacts. The fixed selected engines are bing,
keenable, perplexity. Selection used inventory structure/size, not scores.
A has 384 unique query IDs, 96 paper groups, 384 unique join tuples and
384 terminal rows in each selected arm. Every row joins exactly to run-local
gold. The supported cohort has 324 tasks and 81 groups; all 60 exclusions
are listed, with source lines and reasons, in
`fixtures/expected/packet-a-exclusions.json`. Originals are unchanged.

B was downloaded as opaque bytes, SHA-256 hashed, and never JSON-decoded or
viewed. Its exact five artifacts and hashes are reserved in
`fixtures/real/packet-b/reserved.json`, `sources.json`, and `protocol.json`.
The full B filename/size/blob inventory is separately retained. B is not
scored, reconciled, or claimed compatible by execution yet. The corruption
suite is not frozen; protected evaluation must wait.

## Pinned identities and linkage

- Dataset: `fc40441e7d6d521dc2dbec7e46e76ed9ba1fe6f4`.
- NEEDLE: `73c7f810c57ad675609832bff0195efe5d5275cb`.
- GitHub Bench run: `38565433652`; head SHA is the pinned source. Its Scholar
  job ran `2026-10-14T12:39:33Z`–`2026-10-14T15:07:31Z`; publish ran
  `15:06:21Z`–`15:07:28Z`, matching A's minute ID. These are job bounds,
  not actual task dispatch times. Metadata is frozen unchanged.
- Run-local `scholar.jsonl` and report tuple correspondence establish gold
  membership. Pinned `publish_bench.py` copies the exact gold bytes into
  the same run directory. This is strong operational linkage through job
  metadata/timing and publisher code, not a cryptographic run-attestation
  field: the archive embeds neither head SHA nor action-run ID.
- Source code and dataset both declare MIT; unchanged NEEDLE license and
  dataset card are retained. Dependency wheels retain their license metadata.

All source byte lengths, actual SHA-256s, immutable URLs, UTC acquisition
times, and per-artifact commands are in `sources.json`; none are invented.
Metadata/source archive timestamps use original download mtime, explicitly
identified separately from direct per-download UTC clock samples.

## Commands and retention

Initial sandboxed curl failed DNS; the authorized read-only network
acquisition succeeded with sandbox escalation. Incorrect exploratory
`runs.json` (root rather than `data/runs.json`) and guessed run minute
`1253Z` returned HTTP 404; neither supplied evidence.

The successful source/metadata request sequence was:

```sh
curl -fsSL https://api.github.com/repos/keenableai/needle/commits/main -o /tmp/needle-commit.json
curl -fsSL https://huggingface.co/api/datasets/keenable-ai/needle-results -o .cache/acquisition/dataset-info.json
curl -fsSL 'https://huggingface.co/api/datasets/keenable-ai/needle-results/tree/main/runs?limit=1000' -o .cache/acquisition/runs.json
curl -fsSL https://raw.githubusercontent.com/keenableai/needle/gh-pages/data/runs.json -o .cache/acquisition/site-runs.json
```

The run listing's first 1,000 entries were old; the native index, not a score,
located recent complete Scholar entries. The pinned tree API was requested
for those exact run directories with `recursive=true&limit=1000`. Each
selected artifact was downloaded via `urllib.request.urlopen(immutable_url)`
and `Path.write_bytes(data)`, with actual per-file expressions in sources.
Only five artifacts per packet were downloaded. The full 18 GB archive was
not cloned. A preliminary current-main source archive was exploratory; the
matched historical source archive is the replay input.

```sh
# The source archive URL is pinned to the historical job head.
tar -xzf .cache/needle/matched.tar.gz -C .cache/needle-pinned --strip-components=1
python -m venv .cache/native-venv
.cache/native-venv/bin/python -m pip download 'httpx==0.28.1' -d .cache/wheels
.cache/native-venv/bin/python -m pip install --no-index --find-links .cache/wheels httpx==0.28.1
```

Ordinary Git contains manageable unchanged A raw bytes (~6.6 MiB), source
metadata, licenses, code, expected examples and small derived baseline JSON.
`.cache/` retains the source tar, unchanged expanded checkout, dependency
wheels, and opaque B bytes; `reference/retention-manifest.json` and sources
hash them. Generated canonical runs are ignored. Before deleting this
workspace, copy those exact cached paths to durable storage; Git alone does
not contain the offline dependency/B artifacts. No remote upload occurred.

## Missing evidence and stop conditions

No historical conversion cache was found in either candidate's inventory.
PMID full extraction is therefore unsupported; fresh identifier lookups
would change the evidence. No physical attempt history, task-linked latency,
observed cost, request timestamps or complete actual request settings were
archived. Modes/endpoint/retry/timeout overrides cannot be proven by defaults.
Actual comparison-critical settings are null and explicitly block comparisons.
Raw terminal failures are provider-error observations, not proof of search
quality or an independently fair provider comparison.

The archive acquisition fallback condition did not occur for the supported
arXiv projection, so **zero keyless search requests** were sent. The existing
keyless interface was inspected in pinned KeenableClient (`POST
/v1/search/public`, no API key); it is not silently used to repair missing
archive metadata. A later task cannot claim a two-provider comparison from
that one-provider fallback. Two-packet acceptance remains unmet until B is
opened after the protocol and corruption suite freeze. A alone exceeds the
200-query/50-group engineering counts, but does not satisfy the two-packet
requirement. No measured workflow reduction or purchasing verdict exists.
