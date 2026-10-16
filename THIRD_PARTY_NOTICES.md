# Third-party material

## NEEDLE source and evaluation records

[NEEDLE](https://github.com/keenableai/needle), by Keenable.ai, is MIT-licensed.
Native replay uses source revision
[`73c7f810c57ad675609832bff0195efe5d5275cb`](https://github.com/keenableai/needle/tree/73c7f810c57ad675609832bff0195efe5d5275cb).
The unchanged notice is in [reference/NEEDLE-LICENSE](reference/NEEDLE-LICENSE).

The Scholar matching behavior in `pilotpack/score.py`, `reference/oracle.py`
and the native replay/export drivers follows that source. The independent
oracle is separately implemented and imports no product scoring code. MIT
notices remain applicable to upstream-derived portions alongside this project's
software license.

Original gold, benchmark summaries and selected per-engine results in
`fixtures/real/packet-a` and `fixtures/real/packet-b` came from
[`keenable-ai/needle-results`](https://huggingface.co/datasets/keenable-ai/needle-results/tree/fc40441e7d6d521dc2dbec7e46e76ed9ba1fe6f4)
at revision `fc40441e7d6d521dc2dbec7e46e76ed9ba1fe6f4`. The recorded
[dataset card](fixtures/real/metadata/dataset-card.md) declares MIT. Revisions,
acquisition times, byte lengths, hashes and transformation parents are in
[sources.json](sources.json). Derived source records and baseline sidecars retain
these upstream terms. The project licenses make no additional grant over
papers, snippets or underlying third-party content beyond rights actually
supplied by their owners. GitHub metadata and inventory receipts in
`fixtures/real/metadata` are retained as provenance. No endorsement is implied.

## Native baseline dependencies

The product uses the Python standard library. Unchanged NEEDLE replay uses seven
pinned distributions in [reference/native-requirements.txt](reference/native-requirements.txt):
AnyIO, certifi, h11, HTTP Core, HTTPX, idna and typing_extensions. They retain
their own license files and bundled-component notices inside the original
wheels. Certifi includes Mozilla certificate material under MPL-2.0; those
terms remain separate from this project's licenses.

Wheels and the unchanged NEEDLE source archive are omitted from Git and included
as separately hashed files in the optional offline-baselines release asset.
No installed environments, provider credentials, models or live customer data
are distributed. Filenames, hashes and sizes are in
[reference/retention-manifest.json](reference/retention-manifest.json).

## Writing assistance

README editing used the requested
[write-like-me](https://github.com/arlegotin/write-like-me) skill. Its source
and reference material are not bundled. Development and reporting used AI
assistance under the project owner's direction.
