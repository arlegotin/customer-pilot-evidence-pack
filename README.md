# Customer Pilot Evidence Pack

A local Python 3.11+ tool for freezing retrieval evidence and producing inspectable JSON and static HTML. The runtime uses the standard library; run commands from this checkout without installing a package. Evaluation and reporting make no network requests and use no paid APIs or model judges.

```bash
python -m pilotpack freeze --adapter needle-scholar --input fixtures/real/packet-a --config fixtures/config/packet-a.json --protocol protocol.json --sources sources.json --out runs/packet-a
python -m pilotpack evaluate --run runs/packet-a --out build/packet-a
python -m pilotpack report --run runs/packet-a --evaluation build/packet-a/evaluation.json --out build/packet-a
python reference/oracle.py --run runs/packet-a
python -m unittest discover -s tests -v
```

Open `build/packet-a/report.html` locally. It needs no server, JavaScript, fonts, external assets, or browser dependency. `evaluation.json` retains every assignment, selected response, evidenced physical attempt, rank, failure, unknown outcome and source location. `verdict.json` contains the summary, independent arm decisions and requested pair gates. Reporting verifies the frozen run and evaluation identities without scoring again.

For a small **synthetic schema control**, use the same commands with this freeze step and replace the subsequent run/output paths with `runs/canonical` and `build/canonical`:

```bash
python -m pilotpack freeze --adapter canonical --input fixtures/canonical/schema-small --config fixtures/config/canonical.json --protocol fixtures/canonical/schema-small/protocol.json --sources fixtures/canonical/schema-small/sources.json --out runs/canonical
```

`freeze` refuses an existing destination and preserves source bytes, protocol and normalized ledger. Repeating `evaluate` or `report` at an output path requires the same run, content and protocol identities. Publication stages a complete directory, then replaces the previous derived directory; re-evaluation invalidates any previous HTML until `report` runs again. Input evidence and output directories must not overlap. Errors preserve the previous complete output or leave no final output. During replacement the final directory can briefly be absent. A hard process kill can leave a sibling `.NAME.previous-*` complete backup and `.NAME.publishing` lock; inspect the backup before restoring it and removing the stale lock. No mixed evaluation/verdict is exposed.

Exit codes apply to both evaluation and reporting:

- `0`: artifacts generated; requested comparisons eligible, or no pair requested.
- `2`: invalid input, frozen-integrity failure, reference disagreement or publication failure; no new valid-looking output.
- `3`: qualified artifacts emitted with at least one requested comparison blocked.

Optional customer thresholds affect each arm's `decision_status`, never the exit code. There is no automatic winner or run-wide customer decision. Diagnostics go to stderr. Repeated identical replay produces identical JSON and HTML bytes; execution times are excluded from artifacts.

The acquired A evidence supports a reconstructed arXiv cohort of 324 tasks, 81 source groups and 972 assignments across Bing, Keenable and Perplexity. It contains no observed physical-attempt rows. The original collection has quota failures and excludes unsupported non-arXiv gold from this cohort with a retained exclusion manifest. Exact historical request counts, retry history, actual comparison settings and cost receipts are unavailable. Declared settings are shown separately from actual evidence; documentation defaults do not fill missing settings. Archived marginal latency arrays cannot establish task-paired latency. Missing cost remains unavailable. The frozen acquisition baseline requests no provider pair; requesting a pair under these unknown conditions emits a blocked comparison. Descriptive retrieval counts do not support a provider purchasing recommendation.

Every report preserves these limits: retrieval is not answer quality or citation support; a miss does not prove index absence; missingness bounds are not confidence intervals; the demonstration is too small to resolve tiny provider differences.

See the [specification](docs/superpowers/specs/2026-10-16-customer-pilot-evidence-pack-design.md), [acquisition evidence](docs/evidence/acquisition.md), [adapter profile](docs/evidence/adapter-profile.md), [unchanged native baseline](docs/evidence/native-baseline.md), and [manual reconciliation](docs/evidence/reconciliation.md). The pinned native baseline has a separate offline environment recipe; normal product commands need no third-party runtime packages.
