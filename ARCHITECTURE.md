# ATR Core Architecture (Class D)

## 1) Overview

ATR (Aetherium Transmission & Retrieval) is a **Class D Deep Core Server** operating as a Ground Truth Authority.

ATR Core is not:
- an application runtime,
- a business-workflow orchestrator,
- an agent reasoning engine.

ATR Core is:
- a contract enforcement kernel,
- an immutable truth recorder,
- a canonical event publisher.

---

## 2) Architectural Model

### 2.1 3-Axis Architecture

#### Axis 1 — Transport (AetherBusExtreme)
- NATS JetStream backbone in containerized mode.
- Deterministic envelope transit between gates and internal workers.
- Tachyon phase target: zero-copy pathways and kernel-bypass-ready transport.

#### Axis 2 — Immune System
Mandatory envelope checks on ingress:
1. Schema validation
2. Deterministic canonicalization (byte-level)
3. Signature verification (Ed25519)
4. Inspira ruleset enforcement

Validation failures are routed to quarantine (`audit.violation`) and never admitted to main flow.

#### Axis 3 — State Authority (E3 Hybrid)
Truth model is fixed:

**Truth = Immutable Log + Materialized Snapshot**

- Immutable Log: append-only, replayable source of truth.
- Materialized Snapshot: idempotent derived state for low-latency read/query.
- Recovery: reconstruct snapshot deterministically from log + ordered replay.

---

## 3) External Gate Model (Fixed Surface)

Only four external gates are allowed:
1. Ingress (submit envelope)
2. Stream (subscribe canonical events)
3. Query (state + ledger)
4. Admin (health + governance)

Any additional endpoint requires explicit architecture review.

---

## 4) Determinism and Ordering Principles

- Canonical bytes, not pretty JSON, define hash/signature identity.
- No hidden nondeterminism from map iteration, timing side effects, or randomized behavior.
- Ordering authority must come from stream/broker sequence, not wall-clock assumptions.
- State transitions must remain idempotent under at-least-once delivery.

---

## 5) Data Flow

`Ingress → Immune Validation → Stream → Log → Worker → Snapshot`

Rejected envelopes:

`Ingress → Immune Validation (failed) → Quarantine/Audit Stream`

---

## 6) Deployment Modes

### 6.1 Containerized Phase
- Docker/Kubernetes deployment
- SSD/NVMe-backed persistence
- Primary goal: operational correctness + stable p99 tail latency

### 6.2 Tachyon Phase
- Unikernel + kernel-bypass networking (RDMA/DPDK/XDP by profile)
- NVMe optimized write path
- Target throughput and latency defined by benchmark contract

---

## 7) Benchmark Contract Alignment

Performance and correctness claims are governed by `specs/benchmark_contract.yaml`.

- Tail latency percentiles (p50/p95/p99/p99.9/max) are required.
- Effectively-once semantics is default claim.
- Exactly-once requires explicit failure-injection proof.
