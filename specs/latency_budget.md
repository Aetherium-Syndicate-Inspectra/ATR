# ATR Latency Budget Specification
Document ID: ATR-LATENCY-2026
Status: LOCKED CONTRACT
Applies To: Tachyon Edition (Rust Data Plane + Python Control Plane)

---

# 1. Purpose

This document defines the deterministic latency budget
for ATR under 15M msg/sec target throughput.

At 15M messages/sec:

    Time per packet = 1 / 15,000,000
                    ≈ 66 nanoseconds

Every nanosecond must be accounted for.

This document defines:

- Per-stage latency limits
- Hard ceilings
- Acceptable variance (jitter)
- Micro-batching constraints
- Multi-core scaling behavior

---

# 2. Latency Tiers

ATR operates in 3 latency domains:

Tier A: Control Plane (Python)
Tier B: Bridge / Batch Submit (gRPC / FFI)
Tier C: Data Plane (Rust)

Only Tier C participates in 15M target.

---

# 3. End-to-End Targets

## Mode 1: Internal Bus (No Network)

Target:
    ≤ 5 microseconds (P99)

Breakdown:

| Stage                         | Budget |
|------------------------------|--------|
| Python batch preparation     | 2 µs   |
| gRPC submit call             | 2 µs   |
| Rust governance + dispatch   | 1 µs   |

---

## Mode 2: Network (io_uring)

Target:
    ≤ 10 microseconds (P99)

---

## Mode 3: RDMA Enabled

Target:
    ≤ 2 microseconds (P99)
    ≤ 1 microsecond (P50)

---

# 4. Data Plane Budget (Per Packet)

At 15M msg/sec:

66 ns total available.

Data Plane allocation:

| Component              | Budget |
|------------------------|--------|
| Queue pop              | 10 ns  |
| Governance fast-path   | 25 ns  |
| Batch aggregation      | 10 ns  |
| Serialization (zero-copy) | 10 ns |
| Dispatch enqueue       | 11 ns  |
| TOTAL                  | 66 ns  |

If any stage exceeds budget → throughput collapses.

---

# 5. Micro-Batching Strategy

Batch size target:

256 – 4096 packets

Constraints:

- Batch fill must not exceed 5 µs
- Empty batch wait must not exceed 10 µs
- No busy-wait beyond 1 core

Effective per-packet cost:

    per_packet_cost = batch_overhead / batch_size

As batch_size → large,
overhead → amortized.

---

# 6. Governance Budget Constraint

Governance must execute in:

≤ 25 ns per packet

Allowed operations:

- Atomic load
- Bitmap bit check
- Integer compare
- Token decrement

Forbidden:

- HashMap lookup
- String compare
- Mutex
- Allocation

---

# 7. Cache Line Constraint

Packet size:

64 bytes

Guarantee:

1 packet = 1 cache line fetch

L1 hit latency:
~4 cycles

L3 hit latency:
~40 cycles

Main memory:
~100+ cycles (fatal for 15M target)

Therefore:

No pointer chasing in fast path.
No cross-NUMA memory access.

---

# 8. Cross-Core Scaling Model

Throughput scaling:

R_total = R_core × N_cores × Efficiency

Where:

Efficiency target ≥ 0.85

Example:

Per core capacity:
15M / 4 cores = 3.75M per core

If 8 cores:

3.75M × 8 × 0.9 ≈ 27M msg/sec

---

# 9. Jitter Constraints

At HFT-class systems:

Jitter must remain below:

≤ 50 microseconds (network mode)
≤ 5 microseconds (internal mode)

Sources of jitter:

- Page faults
- Lock contention
- Cross-socket memory
- Branch misprediction
- Rule swap spikes

Mitigation:

- Pre-allocate memory
- Pin threads
- Disable CPU frequency scaling
- Use isolcpus (Linux)

---

# 10. RCU Swap Impact Budget

Rule update swap must:

≤ 200 ns

Must not:

- Stall workers
- Trigger stop-the-world
- Cause cache invalidation storms

---

# 11. gRPC Budget (Control Plane)

Per call overhead:

5 – 20 µs

Therefore:

Minimum batch size recommended:

≥ 512 packets

Otherwise gRPC dominates latency.

---

# 12. NUMA Budget

On dual-socket system:

Cross-node memory latency:
~120 ns

This alone exceeds per-packet budget.

Therefore:

- Per NUMA node sharding mandatory
- Worker pinned per node
- Rule shard per node

---

# 13. Failure Budget

Under overload:

System may:

- Drop packets
- Throttle
- Reduce batch size

System must not:

- Block
- Allocate
- Deadlock
- Spin uncontrollably

---

# 14. Profiling Requirement

Before claiming 15M:

Measure:

- ns per governance check
- ns per queue pop
- ns per serialization
- L1/L2 miss rate
- CPU cycles per packet

Use:

- perf
- flamegraph
- rdtsc-based microbench

---

# 15. Hard Red Lines

If any of the following appear in hot path:

- Mutex
- RwLock
- HashMap
- Vec::push (dynamic growth)
- String
- serde_json
- Panic

Latency target is void.

---

# 16. Physics Reminder

15M msg/sec = 66 ns per message.

66 ns = ~200 CPU cycles (on 3GHz CPU).

Every branch matters.
Every cache miss matters.
Every allocation kills throughput.

This is not web engineering.
This is exchange-engine class engineering.

---

# END OF SPEC
