# TRANSITION_ROADMAP.md

## ATR Core – From Prototype to Tachyon Metal

---

# 🎯 Objective

ยกระดับ ATR จาก:

> Hybrid Governance + JetStream-backed Event Core

ไปสู่:

> Deterministic Split-Brain Architecture
> Python Control Plane + Rust Tachyon Data Plane
> Target: 15M msg/sec (Metal-bound)

โดยไม่ละเมิด:

* Determinism
* Immutable truth
* Canonical byte-level invariants
* Governance enforcement guarantees

---

# 🧭 Phase Overview

| Phase | Name                 | Goal                               | Risk      |
| ----- | -------------------- | ---------------------------------- | --------- |
| 0     | Stabilization        | Lock invariants                    | Low       |
| 1     | Iron Core            | Rust queue + packet                | Medium    |
| 2     | Governance Injection | Move enforcement to Rust           | Medium    |
| 3     | Batch Engine         | Micro-batching + vectorization     | High      |
| 4     | Persistence Refactor | Decouple JetStream                 | Medium    |
| 5     | io_uring Transport   | High-performance generic transport | High      |
| 6     | RDMA Enablement      | Kernel bypass                      | Very High |
| 7     | Metal Validation     | Failure injection + physics test   | Extreme   |

---

# 🧱 Phase 0 – Invariant Lockdown

### Goal

ก่อนเร่งความเร็ว ต้องทำให้ระบบ deterministic จริง

### Required

* Freeze canonicalization definition (byte-level spec)
* Lock signature verification contract
* Lock E3 truth semantics
* Finalize failure model spec
* Enforce metrics contract CI

### Acceptance Criteria

* Determinism proof for same input → same log
* Snapshot rebuild always converges
* No bypass path in immune pipeline

---

# 🔩 Phase 1 – The Iron Core (Rust Queue + Packet)

### Goal

สร้าง Data Plane แท้จริง

### Implementation

1. Define `TachyonPacket` (64B aligned struct)
2. Use `crossbeam::ArrayQueue`
3. Create PyO3 binding:

```rust
submit_packet(topic_id: u32, data: &[u8])
```

4. Benchmark:

   * Python → Rust push throughput
   * No JSON allowed in hot path

### Acceptance Criteria

* ≥ 1M msg/sec sustained (local benchmark)
* Zero dynamic allocation in hot path
* No lock contention under 4 producers

---

# 🧠 Phase 2 – Governance Injection (RCU Model)

### Goal

Move enforcement from Python to Rust

### Implementation

* Rust Rule Engine
* `Arc<AtomicPtr<Ruleset>>`
* RCU snapshot swap protocol
* Token bucket in Rust

Python only:

```
POST /governance/rules
```

Rust enforces per packet.

### Acceptance Criteria

* No Python callback in hot path
* Ruleset swap < 10µs
* Governance check cost < 200ns per packet

---

# 📦 Phase 3 – Batch Engine (Pulse Aggregator)

### Goal

Exploit cache locality + reduce syscall overhead

### Implementation

* Drain queue into Vec<TachyonPacket>
* Adaptive batch size
* SIMD serialization (rkyv / flat binary)
* No JSON anywhere in batch

Pseudo:

```
while queue.pop() → batch.push()
if batch >= N → process
else park_timeout(10µs)
```

### Acceptance Criteria

* ≥ 5M msg/sec local
* P99 latency stable under load
* No starvation between shards

---

# 🗃 Phase 4 – Persistence Refactor

### Goal

Decouple JetStream from hot path

### Design

Option A: Async persistence worker
Option B: Write-ahead memory buffer + async disk flush

Truth remains:

```
Immutable Log = authoritative
```

But hot path must not block on broker.

### Acceptance Criteria

* No blocking I/O in processing loop
* Crash recovery replay deterministic
* No data loss under controlled failure

---

# ⚙️ Phase 5 – io_uring Transport

### Goal

High-performance generic Linux transport

### Implementation

* Replace epoll with io_uring
* Pre-registered buffers
* Batch send
* Batch recv

### Acceptance Criteria

* Syscall count reduced by 100x
* P99 < 20µs network loopback
* CPU usage predictable

---

# 🚀 Phase 6 – RDMA Enablement

### Goal

Kernel bypass

### Requirements

* Memory registration (pinned)
* Completion queue polling
* Dedicated CPU core
* Lossless network fabric (RoCE v2)

### Flow

```
Rust writes → Registered Memory → NIC DMA → Wire
```

No CPU copy after submission.

### Acceptance Criteria

* Internal latency < 1µs
* Hop latency 2–5µs
* Stable 10M+ msg/sec

---

# 🧪 Phase 7 – Metal Validation

### Goal

Prove physics

### Required Tests

* Failure injection
* Ruleset swap under 10M load
* Backpressure storm
* Memory exhaustion scenario
* Shard imbalance

### Metrics to Validate

* P99, P99.9 latency
* Drop rate
* Queue depth stability
* Arena fragmentation
* Backpressure transitions

### Acceptance Criteria

* No nondeterministic behavior
* No invariant violation
* No silent data corruption
* No unbounded memory growth

---

# 🔥 Risk Register

| Risk                            | Impact                 | Mitigation          |
| ------------------------------- | ---------------------- | ------------------- |
| Python accidentally in hot path | Performance collapse   | CI guard            |
| Dynamic allocation creep        | Cache miss explosion   | Arena allocator     |
| Label cardinality explosion     | Observability collapse | Metrics contract CI |
| Governance drift                | Inconsistent truth     | RCU swap protocol   |
| Lock contention                 | Throughput collapse    | Lock-free queue     |
| False sharing                   | Cache thrash           | 64B alignment       |

---

# 📐 Performance Envelope Targets

| Stage   | Throughput | Latency        |
| ------- | ---------- | -------------- |
| Phase 1 | 1M         | < 20µs         |
| Phase 3 | 5M         | < 5µs          |
| Phase 6 | 15M        | < 1µs internal |

---

# 🛑 What We Will NOT Do

* Optimize Python loop for 15M
* Claim exactly-once without proof
* Use JSON in metal path
* Mix governance logic in Python hot path
* Introduce nondeterministic scheduling
* Trade determinism for vanity benchmark

---

# 🧠 Final Architecture Target

```
Python (Control Plane)
        ↓
Shared Memory (Zero-copy boundary)
        ↓
Rust Tachyon Ring (Lock-free)
        ↓
Batch Aggregator
        ↓
Governance Enforcement (Compiled)
        ↓
Transport (io_uring / RDMA)
        ↓
Immutable Log (Async)
```

---

# 📌 Strategic Statement

ATR is not evolving into a faster web server.

ATR is evolving into:

> Deterministic AI Data Plane Infrastructure
> built within physical limits of CPU cache, memory bandwidth, and network fabric.

---
