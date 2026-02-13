# Governance Fast-Path Specification
Document ID: ATR-GOV-FASTPATH-2026
Status: LOCKED CONTRACT
Applies To: Tachyon Data Plane (Rust Only)

---

## 1. Purpose

This document defines the ultra-low-latency governance enforcement layer executed inside the Rust Data Plane.

Goal:
- Enforce policy at 15M msg/sec
- O(1) decision time
- No heap allocation
- No dynamic dispatch
- No locking in hot path

Governance must never downgrade Tachyon throughput.

---

## 2. Architectural Rule

Governance in Tachyon operates in two tiers:

Tier 1: Fast Path (Hot Path)
- Token bucket
- Quota enforcement
- Allowlist / denylist
- Priority override

Tier 2: Deep Validation (Slow Path)
- Signature verification
- Schema validation
- Complex rule engine
- Audit trail

ONLY Tier 1 is allowed inside the Data Plane loop.

---

## 3. Fast-Path Decision Model

Decision function must be:

```text
ALLOW | DROP | THROTTLE
```

Must execute in:

- < 50 nanoseconds per packet
- No syscalls
- No locks
- No allocation

---

## 4. Data Structures

All structures must be:

- Pre-allocated
- Cache-aligned
- Lock-free or atomic
- Fixed capacity

---

## 5. Token Bucket (Per `topic_id`)

### Purpose

Limit throughput per `topic_id`.

### Data Structure

```rust
#[repr(C, align(64))]
pub struct TokenBucket {
    pub tokens: AtomicU64,
    pub last_refill_ns: AtomicU64,
    pub refill_rate: u64,
    pub capacity: u64,
}
```

Stored in:

```rust
Vec<TokenBucket>
```

Indexed by:

```text
topic_id % BUCKET_TABLE_SIZE
```

### Algorithm (Fast Path)

1. Read current time (`rdtsc` or monotonic clock)
2. Calculate elapsed
3. Refill tokens using atomic add
4. If `tokens >= 1`, subtract 1 → `ALLOW`; else `DROP` or `THROTTLE`

No floating point allowed. All math must be integer-based.

---

## 6. Sender Quota (Per `sender_id`)

### Purpose

Prevent abusive sender flooding.

### Data Structure

```rust
#[repr(C, align(64))]
pub struct SenderQuota {
    pub in_flight: AtomicU32,
    pub max_in_flight: u32,
}
```

Stored in fixed-size array.

Check:

```text
if in_flight >= max_in_flight:
    DROP
else:
    in_flight += 1
    ALLOW
```

Decrement when packet completed.

---

## 7. Allowlist / Denylist

Must use bitmaps or fixed hash table.

### Option A: Bitmap (Preferred)

If `topic_id < 65536`:

```rust
static ALLOW_BITMAP: [AtomicU64; 1024];
```

Check:

```text
bit = topic_id % 65536
word = bit / 64
mask = 1 << (bit % 64)

if (ALLOW_BITMAP[word] & mask) != 0:
    ALLOW
else:
    DROP
```

`O(1)`, branch-minimal.

### Option B: Fixed Hash Set

- Open addressing
- No resizing
- No dynamic allocation

---

## 8. Governance Evaluation Order

Order must be:

1. SYSTEM_PACKET bypass
2. Allowlist check
3. SenderQuota check
4. TokenBucket check
5. Priority override

Evaluation must short-circuit immediately on failure.

---

## 9. Rule Injection (Control Plane → Data Plane)

Python must NOT execute governance logic.

Python may only:

- Update rule config
- Push new rate limits
- Modify allowlist

Update mechanism:

RCU (Read-Copy-Update) model:

- Data Plane reads `Arc<Rules>`
- Control Plane builds new `Rules`
- Swap pointer atomically

No lock allowed in fast path.

---

## 10. RCU Rule Container

```rust
pub struct FastRules {
    pub buckets: Vec<TokenBucket>,
    pub sender_quotas: Vec<SenderQuota>,
    pub allow_bitmap: Vec<AtomicU64>,
}
```

Swap using:

```rust
ArcSwap<FastRules>
```

Guarantee:

- Readers never block
- Updates do not stall packet processing

---

## 11. Performance Invariants

Mandatory conditions for 15M msg/sec:

- No `HashMap`
- No `Mutex`
- No `RwLock`
- No `Vec` resize
- No heap allocation
- No branching cascade > 5 levels
- No string comparison

---

## 12. Latency Budget

At 15M msg/sec:

- Time per packet ≈ 66 nanoseconds

Governance budget:

- ≤ 25 ns

Breakdown target:

- Allowlist check: 5 ns
- Quota check: 5 ns
- Token bucket: 10 ns
- Branching: 5 ns

---

## 13. Adaptive Strategy

Under overload:

- Mode 1: Drop immediately
- Mode 2: Defer to batch
- Mode 3: Escalate to slow path

Escalation must not block worker thread.

---

## 14. Multi-Core Scaling

Each worker thread must have:

- Local token bucket shard
- Local quota shard

Global limit enforced by sharded counters + periodic reconciliation.

Never use one global atomic counter for all threads.

---

## 15. NUMA Considerations

On multi-socket systems:

- Shard rules per NUMA node
- Avoid cross-node atomic access
- Pin worker threads

---

## 16. Failure Behavior

If governance data is corrupted:

- Fail-closed (`DROP`)
- Never fail-open in Data Plane

---

## 17. Benchmark Requirement

Governance must be benchmarked standalone.

Target:

- ≥ 50M rule evaluations/sec per core

Before integration with network layer.
