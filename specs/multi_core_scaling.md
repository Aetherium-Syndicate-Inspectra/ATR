# ATR Multi-Core Scaling Specification
Document ID: ATR-MULTICORE-2026
Status: LOCKED CONTRACT
Applies To: Tachyon Data Plane

---

# 1. Purpose

This document defines how ATR scales from:

Single-core 15M msg/sec
→ Multi-core 50M+
→ Multi-socket 100M+

Without:

- Lock contention
- Cache line bouncing
- NUMA penalties
- False sharing
- Global atomic bottlenecks

---

# 2. Core Scaling Principle

Scaling model:

R_total = R_core × N_cores × Efficiency

Where:

Efficiency must remain ≥ 0.85

If efficiency < 0.7 → design failure.

---

# 3. Sharding Strategy

ATR must shard workload at ingestion time.

Sharding key:

    shard_id = topic_id % NUM_WORKERS

Each worker:

- Owns its own queue
- Owns its own governance shard
- Owns its own batch buffer
- Owns its own network socket

No shared global queue allowed.

---

# 4. Worker Model

Each worker thread:

- Pinned to dedicated core
- Owns local ArrayQueue<TachyonPacket>
- Owns local FastRules shard
- Runs infinite processing loop

Thread count:

Equal to number of physical cores
NOT logical cores (avoid SMT interference)

---

# 5. Queue Layout

Instead of:

❌ One global MPMC queue

Use:

✔ Per-worker SPSC or MPSC queue

Preferred:

Python → MPSC shard queues
Rust worker → single consumer per shard

This avoids:

- CAS storms
- Cache invalidation
- Global head/tail contention

---

# 6. Governance Sharding

TokenBucket and SenderQuota must be sharded.

Instead of:

❌ Global Atomic counter

Use:

✔ Per-core local counters

Global limit enforced via:

Periodic reconciliation every 1–10ms.

This prevents cross-core atomic bouncing.

---

# 7. False Sharing Prevention

All hot structs must:

#[repr(C, align(64))]

Every atomic counter must:

Be isolated in its own cache line.

Never place:

AtomicU64 next to another atomic.

---

# 8. NUMA Awareness

On dual-socket systems:

Rules:

- Each NUMA node has independent worker group
- Memory allocated per node
- Threads pinned to same node
- No cross-node queue access

NUMA topology must be detected at startup.

---

# 9. Thread Pinning Strategy

Linux:

Use:
- sched_setaffinity
- isolcpus kernel parameter

Disable:
- CPU frequency scaling
- Turbo fluctuation

Goal:
Deterministic latency.

---

# 10. Work Distribution Models

Option A: Static Hash Sharding (Preferred)

topic_id → shard

Stable
Deterministic
No coordination required

Option B: Work Stealing (NOT allowed in hot path)

Work stealing introduces:

- Locking
- Cross-core traffic
- Latency spikes

Forbidden for 15M target.

---

# 11. Batch Processing Per Core

Each core:

Drain up to N packets
Process governance locally
Dispatch locally

No cross-core coordination per packet.

---

# 12. Network Scaling

Each worker:

Owns dedicated:

- io_uring instance
or
- RDMA queue pair

Never multiplex multiple cores onto single socket fd.

---

# 13. Memory Allocation Policy

Per core:

- Pre-allocate batch Vec
- Pre-allocate arena
- Pre-allocate rule shards

No allocation in hot loop.

---

# 14. Backpressure Model

Backpressure must be:

Shard-local.

If shard queue full:

- Return error to Python
- Drop locally
- Do not block other shards

System must degrade per shard,
not globally.

---

# 15. Expected Scaling Behavior

Example:

Per-core capacity:
3.5M msg/sec stable

8 cores:
≈ 28M msg/sec

16 cores:
≈ 55M msg/sec

Efficiency drop expected:
5–15%

If drop > 30%:
Investigate cache line contention.

---

# 16. Cross-Core Communication Rules

Allowed:

- Periodic stats aggregation
- RCU rule pointer swap

Forbidden:

- Global counters per packet
- Shared HashMap mutation
- Central rate limiter

---

# 17. Metrics Model

Per core expose:

- packets_processed
- packets_dropped
- governance_ns
- queue_depth

Aggregation must happen outside hot path.

---

# 18. Hardware Assumptions

CPU:

- 3.0GHz+
- Large L3 cache
- AVX2/AVX512 optional

Memory:

- DDR4/DDR5
- NUMA-aware configuration

NIC:

- Multiple queues
- RSS enabled

---

# 19. Saturation Indicators

Signs of scaling breakdown:

- Increased L3 misses
- Increased CAS retries
- High cross-socket traffic
- Throughput plateau with more cores

---

# 20. Red Lines

If system uses:

- Global MPMC queue
- Shared Mutex
- Cross-core HashMap
- Single global token bucket

15M scaling will fail.

---

# 21. Target Scaling Milestones

Phase 1:
Single core 3–5M stable

Phase 2:
8 cores 25–35M

Phase 3:
16 cores 50M+

Phase 4:
Dual socket 100M+

---

# 22. Final Principle

Scaling is not about more threads.
Scaling is about removing shared state.

Every shared atomic costs you nanoseconds.
Every nanosecond matters.

---

# END OF SPEC
