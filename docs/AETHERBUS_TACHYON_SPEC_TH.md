# Three-Tier Performance Model (Formal Spec)

**Document ID:** ATR-PERF-3T-2026-REV1  
**Applies to:** ATR Python Control Plane + ATB-ET Rust Data Plane  
**Status:** Publishable Technical Specification

## 1) Purpose

This document defines a formal three-tier performance model for the ATR hybrid runtime (Python + Rust), establishes realistic throughput/latency tiers, and calculates a strict theoretical upper bound using both direct timing equations and Amdahl's Law.

## 2) Architectural Tiers

### Tier 1 — Control Plane (Python Runtime)

**Responsibilities**
- Ingress orchestration and envelope handoff.
- Validation orchestration flow (schema, canonicalization, signature, ruleset, quarantine).
- Business policy routing and state authority invocation.

**Performance constraints**
- GIL + asyncio scheduling overhead.
- Python object allocation and per-message dispatch overhead.

**Representative range (single-thread path)**
- Throughput: ~20k–80k msg/s (complex validation/routing path), up to ~100k–300k msg/s for simple routing.
- Latency: ~50–500 us (realistic logic path), lower for synthetic empty-hop microbenchmarks.

### Tier 2 — Bridge (PyO3 / FFI Boundary)

**Responsibilities**
- Cross-language call boundary and marshaling.
- Buffer transfer / borrow semantics.

**Cost model**
- `T_ffi = T_call + T_marshaling + T_copy`

**Representative range**
- ~0.2–1 us for small raw calls.
- ~5–50 us when copying medium payload buffers.

### Tier 3 — Data Plane (Rust / Tachyon Core)

**Responsibilities**
- Hot-path routing, vectorized compute, lock-free queues/fanout.
- Transport-adjacent throughput path in sidecar domain.

**Representative range**
- Throughput ceiling: ~10M–20M msg/s (in-memory, hardware/path dependent).
- Spec reference point: ~15M msg/s class target.
- Latency: typically sub-microsecond for in-memory micro-ops.

## 3) Hybrid Timing Model (Per Message and Batched)

### 3.1 Per-message path

For one sequential message:

`T_total = T_py + T_ffi + T_rust`

Throughput:

`R_max = 1 / T_total`

### 3.2 Batched path

For batch size `N`:

`T_batch = T_py + T_ffi(batch) + N * T_rust (+ T_persist)`

Effective per-message time:

`T_eff = T_batch / N`

Throughput:

`R(N) = N / T_batch`

Asymptotic upper limit:

`lim(N -> inf) R(N) = 1 / T_rust`

Interpretation: batching amortizes Python and FFI overhead, approaching the Rust ceiling only when Python is removed from per-message critical path.

## 4) Scenario Calculations

### Scenario A — Naive per-message orchestration

Assume:
- `T_py = 5 us`
- `T_ffi = 0.5 us`
- `T_rust = 0.1 us`

Then:
- `T_total = 5.6 us`
- `R_max = 1 / 5.6e-6 = 178,571 msg/s`

**Result:** ~170k–180k msg/s class, Python-bound.

### Scenario B — Batched bridge (`N = 1000`)

Assume:
- `T_py = 5 us`
- `T_ffi(batch) = 50 us`
- `T_rust = 0.1 us`

Then:
- `T_batch = 5 + 50 + 100 = 155 us`
- `T_eff = 155 / 1000 = 0.155 us`
- `R(1000) = 1000 / 155e-6 = 6,451,612 msg/s`

**Result:** ~6.45M msg/s class, strong improvement from batching.

### Scenario C — Rust owns the loop

If Python is only control/config (not per-message), then hot path approaches:
- `R ~ 1 / T_rust`
- practical target envelope: ~15M msg/s class when transport + memory path permit.

**Result:** 15M is a Tier-3 transport/data-plane ceiling, not a universal end-to-end ATR Core guarantee.

## 5) Amdahl's Law (Strict Form)

Let:
- `P` = fraction of workload moved to Rust
- `S` = speedup of Rust over Python for that moved fraction

Then:

`Speedup = 1 / ((1 - P) + (P / S))`

Example:
- `P = 0.95`
- `S = 100`

`Speedup = 1 / (0.05 + 0.0095) = 16.81x`

Implication: even a very high Rust fraction is still capped by the remaining Python serial portion.

## 6) Practical Upper Bound for Hybrid ATR

With aggressive batching, low-copy envelopes, and minimal persistence penalty in the hot path:
- realistic hybrid upper envelope: ~8M–10M msg/s.

To reach ~15M class consistently:
- Rust must own socket poll/dispatch/fanout/persistence-adjacent path.
- Python must remain out of per-message inner loop.

## 7) Governance and Truth-Model Notes

This performance model does **not** change ATR core invariants:
- No bypass of schema/canonical/signature/ruleset/quarantine.
- Canonicalization remains byte-defined.
- E3 truth model remains immutable log + rebuildable snapshot.
- Delivery semantics remain effectively-once (idempotent apply keyed by event identity).

Performance claims must be stated by scope:
- **Tier-3 ceiling** (transport/data-plane microbench), vs
- **End-to-end Class D persisted path** (full validation + durability guarantees).
