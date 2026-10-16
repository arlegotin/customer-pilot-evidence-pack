# Customer Pilot Evidence Pack

A proposed local tool that turns frozen evaluation evidence into a reproducible pilot report, preserving intended assignments, observed requests, failures, missing outcomes, and comparison conditions.

This repository currently contains the specification and implementation plan. Product code and real evaluation packets have not been added.

- [PoC specification](docs/superpowers/specs/2026-10-16-customer-pilot-evidence-pack-design.md)
- [Implementation plan](docs/superpowers/plans/2026-10-16-customer-pilot-evidence-pack.md)

The first implementation gate is to acquire a complete real NEEDLE packet and reproduce it with unchanged reporting and an independent baseline. Reuse an adequate existing workflow; stop provider-verdict claims if task-level evidence cannot be obtained.

The planned runtime is Python 3.11+, JSONL, SQLite, and static HTML, with no paid API, model judge, hosted dashboard, or customer-data upload. Planned outputs are `verdict.json` and `report.html`. The commands and acceptance checks in the documents describe future implementation, not commands available in this checkout.
