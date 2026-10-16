# Customer Pilot Evidence Pack

A search pilot should tell you what happened to every query, including the requests that failed. This local tool turns a frozen [NEEDLE](https://github.com/keenableai/needle) run or canonical JSONL export into an inspectable report. It keeps hits, misses, provider errors, unknown judgments and retries separate, then checks whether a comparison is supported by the evidence.

You get `report.html`, a summary in `verdict.json`, and every assignment in `evaluation.json`. It runs locally with Python 3.11+ and the standard library. No paid APIs, model judge, server or data upload.

## What the PoC found

Two real packets cover **649 distinct queries and 160 source groups**. Supported scores agree with independent checks, and the reports reproduce offline. The suite passes 202 tests. Frozen validation v2 catches all 20 introduced faults, including 12 critical faults, with no unexpected findings in eight healthy controls. The failed first validation remains [recorded](docs/evidence/validation.md).

**Preparation savings are unproven.** The existing baseline also handled the second packet through configuration. Both real provider comparisons are blocked because actual comparison conditions are missing. Exact request totals and costs remain unknown. These reports support no provider purchasing recommendation. See the [assessment](docs/evidence/poc-assessment.md).

## Try it

Download the retained evidence files once; evaluation and reporting run offline.

```sh
git clone https://github.com/arlegotin/customer-pilot-evidence-pack.git
cd customer-pilot-evidence-pack
curl -fL -o /tmp/pilotpack-baselines.tar.gz \
  https://github.com/arlegotin/customer-pilot-evidence-pack/releases/download/v0.1.0/pilotpack-v0.1.0-offline-baselines.tar.gz
tar -xzf /tmp/pilotpack-baselines.tar.gz -C .
python -m pilotpack freeze --adapter needle-scholar \
  --input fixtures/real/packet-a --config fixtures/config/packet-a.json \
  --protocol protocol.json --sources sources.json --out runs/demo-a
python -m pilotpack evaluate --run runs/demo-a --out build/demo-a
python -m pilotpack report --run runs/demo-a \
  --evaluation build/demo-a/evaluation.json --out build/demo-a
```

Open `build/demo-a/report.html`. For this packet, `evaluate` and `report` intentionally exit **3**: the files were written, but the requested comparison is blocked. `freeze` needs a new destination. No Python package installation or API keys are required.

[Usage and JSONL inputs](docs/usage.md) · [Validation](docs/evidence/validation.md) · [Offline reproduction](docs/evidence/reproduction.md) · [Latest release](https://github.com/arlegotin/customer-pilot-evidence-pack/releases/latest)

Retrieval hits don't establish answer quality or citation support. A miss doesn't prove a paper is absent from an index. Missingness bounds aren't confidence intervals.

## License and citation

Original code is **AGPL-3.0-only**; original writing and result presentation are **CC BY 4.0**. [Licensing](LICENSING.md) defines the split; [third-party notices](THIRD_PARTY_NOTICES.md) preserve NEEDLE's MIT terms. Please cite [CITATION.cff](CITATION.cff) and record the commit you used. Development and reporting used AI assistance under the owner's direction.
