# ATR Core Server (Class D)

ATR (Aetherium Transmission & Retrieval) is a **Class D Deep Core Server**.
It serves as a **Ground Truth Authority** for deterministic event admission, immutable truth recording, and canonical stream publication.

ATR Core is not an application runtime and must remain business-logic agnostic.

## Core Principles

- Determinism-first behavior
- Immutable truth model
- Mandatory validation and signature enforcement
- Predictable failure behavior under stress

## Architecture Model

ATR follows a **3-Axis Architecture**:

1. **Transport** — AetherBusExtreme / JetStream backbone
2. **Immune System** — schema + canonicalization + signature + ruleset enforcement
3. **State Authority** — E3 Hybrid (`Immutable Log + Materialized Snapshot`)

See full architecture details in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Technical and Governance References

- Technical specification: [`SPEC.md`](SPEC.md)
- Contributor policy: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Invariants policy (normative): [`AGENTS.md`](AGENTS.md)
- Benchmark contract: [`specs/benchmark_contract.yaml`](specs/benchmark_contract.yaml)
- Three-tier performance model: [`docs/AETHERBUS_TACHYON_SPEC_TH.md`](docs/AETHERBUS_TACHYON_SPEC_TH.md)
- Formula estimator tool: [`tools/perf_estimator.py`](tools/perf_estimator.py)

## Repository Layout

```text
cmd/           Binary entrypoints
core/          Class D core logic boundaries
internal/      Internal deterministic utilities
api/           External gate interfaces
specs/         Contracts and protocol specifications
configs/       Deployment/runtime profiles
deployments/   Deployment manifests and packaging
tests/         Unit/integration/replay/failure suites
scripts/       Benchmark and verification entrypoints
```

## Status

This repository is structured for production-grade governance with Class D constraints.
Implementation should evolve without violating deterministic and security invariants.
