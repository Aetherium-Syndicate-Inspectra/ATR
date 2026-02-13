# Ruleset Update RCU Specification
Document ID: ATR-RCU-2026
Status: LOCKED CONTRACT
Applies To: Governance Fast Path (Rust Data Plane)

---

## 1. Purpose

This document defines the atomic snapshot swap protocol used to update governance rules in the Tachyon Data Plane without:

- Blocking packet processing
- Introducing locks
- Causing race conditions
- Violating memory safety
- Breaking 15M msg/sec throughput

The update model MUST follow RCU (Read-Copy-Update).

---

## 2. Core Principle

Data Plane Threads:
- NEVER lock
- NEVER block
- NEVER mutate shared rules

Control Plane:
- Builds a new immutable rules snapshot
- Swaps pointer atomically
- Old snapshot is retired only when safe

---

## 3. RCU Model Overview

We use:

- `Arc<FastRules>`
- `ArcSwap<FastRules>`

Readers:

- Load pointer
- Use immutable snapshot
- Drop `Arc` when done

Writer:

- Build new `FastRules`
- Swap pointer atomically
- Old version drops automatically when `refcount = 0`

---

## 4. Rule Container Definition

```rust
use arc_swap::ArcSwap;
use std::sync::Arc;

pub struct GovernanceRCU {
    pub active: ArcSwap<FastRules>,
}
```

`FastRules` must satisfy:

- Immutable after construction
- No interior mutability
- All fields pre-allocated
- No heap growth after init

---

## 5. FastRules Requirements

```rust
pub struct FastRules {
    pub buckets: Vec<TokenBucket>,
    pub sender_quotas: Vec<SenderQuota>,
    pub allow_bitmap: Vec<AtomicU64>,
    pub version: u64,
}
```

Invariants:

- Length of vectors fixed
- No resizing
- No push/pop after creation
- All fields fully initialized before publish

---

## 6. Update Protocol (Control Plane)

Step 1:
Control Plane sends new rule config (`JSON`, `YAML`, etc.).

Step 2:
Rust builds a NEW `FastRules` instance.
- Validate completely
- Precompute hashes
- Initialize token buckets
- Pre-fill allow bitmap

Step 3:
Wrap in `Arc<FastRules>`.

Step 4:
Atomic swap:

```rust
let old = rcu.active.swap(new_rules_arc);
```

Step 5:
Drop old `Arc` automatically when no reader holds a reference.

---

## 7. Reader Protocol (Data Plane Thread)

Inside hot path:

```rust
let rules = rcu.active.load();

if !rules.allow(topic_id) {
    return DROP;
}
```

Important:

- `load()` must be outside deep loop, only once per batch
- Do NOT load per packet when avoidable

Recommended pattern:

```rust
let rules = rcu.active.load();

for packet in batch {
    fast_path_check(&rules, packet);
}
```

---

## 8. Memory Ordering Guarantees

`ArcSwap` uses Acquire/Release semantics.

Writer:
- `swap()` = Release

Reader:
- `load()` = Acquire

Guarantee:

- Reader always sees fully initialized snapshot
- No torn state
- No partial update
- No inconsistent rule table

---

## 9. Latency Impact Constraint

Swap must:

- Take < 200 ns
- Never block
- Never stall worker threads

Rule update frequency must be low relative to packet flow.

Acceptable examples:

- 1/sec
- 10/sec

Not acceptable:

- 1000/sec continuous rule rebuild

---

## 10. Snapshot Versioning

`FastRules` must include:

```rust
pub version: u64
```

Rules:

- Increment monotonically
- Logged for audit
- Exposed to metrics

---

## 11. Failure Handling

If new rules fail validation:

- DO NOT swap
- Log error
- Continue with previous rules

Never leave active pointer null.
Never partially construct rules.

---

## 12. Graceful Retirement (Advanced RCU Optimization)

Optional enhancement: epoch-based reclamation.

Instead of relying solely on Arc reference counting, you may implement epoch tracking:

- Worker thread enters epoch
- After swap, old version retired when all threads exit epoch

This reduces Arc contention under extreme load.

Not mandatory for Phase 1.

---

## 13. Multi-Core Considerations

Each worker thread:

- Loads pointer locally
- Keeps snapshot for entire batch
- Avoids repeated atomic loads

Never share mutable global state across cores.

RCU snapshot ensures:

- No cross-core locking
- No global mutex
- No cache-line bouncing

---

## 14. Forbidden Patterns

- ❌ `Mutex` around rule table
- ❌ `RwLock` read per packet
- ❌ `HashMap` mutation in fast path
- ❌ `Vec` resizing
- ❌ Partial field update
- ❌ Interior mutability inside `FastRules`

---

## 15. Snapshot Consistency Guarantee

The system guarantees:

For any packet processed, it is evaluated entirely under one consistent rule version.

No packet is evaluated under half-old / half-new rules.

---

## 16. Observability Requirements

Expose metrics:

- `active_rules_version`
- `last_swap_timestamp`
- `rule_swap_count`
- `rule_validation_failures`

These must not be inside hot path.

---

## 17. Atomic Swap Example (Full Code)

```rust
pub fn update_rules(rcu: &GovernanceRCU, new_config: RuleConfig) -> Result<(), Error> {
    let new_rules = build_rules(new_config)?;
    let arc = Arc::new(new_rules);

    let _old = rcu.active.swap(arc);

    Ok(())
}
```

---

## 18. Performance Target

RCU must support:

- ≥ 15M packet/sec
- ≤ 25ns governance evaluation
- Zero blocking
- Zero deadlock risk

---

## 19. Physics Constraint

At 15M msg/sec:

- 66 nanoseconds per packet

If you lock even once, you lose.

RCU is the safe update strategy for this class of data-plane loop.
