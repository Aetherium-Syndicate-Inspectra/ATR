# ATR Memory Arena Design Specification
Document ID: ATR-ARENA-2026
Status: LOCKED CONTRACT
Applies To: Tachyon Data Plane (Rust Only)

---

# 1. Purpose

This document defines the memory arena architecture used when payload
exceeds the 48-byte inline capacity of TachyonPacket.

Goals:

- Zero allocation in hot path
- Zero fragmentation
- Deterministic memory reuse
- NUMA-aware locality
- RDMA-ready layout
- Lock-free access

Arena exists to support large payloads without destroying latency.

---

# 2. Design Philosophy

The Arena is:

- Pre-allocated
- Fixed capacity
- Circular
- Shard-local
- Non-growing
- Non-compacting

The Arena is NOT:

- A general-purpose allocator
- A garbage collector
- A Vec wrapper
- A HashMap

---

# 3. Arena Ownership Model

Each worker thread owns:

struct Arena {
    base_ptr: *mut u8,
    size: usize,
    write_offset: AtomicUsize,
    read_offset: AtomicUsize,
}

No arena is shared across cores.

No global arena allowed.

---

# 4. Allocation Model (Lock-Free Circular Buffer)

Allocation:

1. Read write_offset
2. Check available space
3. Reserve region
4. Write payload
5. Advance write_offset

Freeing:

Implicit via advancing read_offset
when packet processing completed.

---

# 5. Memory Layout

Arena memory is contiguous:

| Header | Payload 1 | Payload 2 | Payload 3 | ... |

Each payload must include:

struct ArenaHeader {
    length: u32,
    checksum: u32,
    reserved: u64,
}

Payload aligned to:

64-byte boundary

---

# 6. Alignment Rules

All payloads must:

- Be 64-byte aligned
- Not cross page boundary if possible
- Not cause false sharing

Alignment enforced via:

round_up_to_64(size)

---

# 7. NUMA Constraint

Arena memory must be allocated using:

numa_alloc_onnode()

Worker thread pinned to same NUMA node.

Cross-node arena access forbidden.

---

# 8. RDMA Compatibility

Arena region must optionally:

- Be registered as RDMA memory region
- Use ibv_reg_mr at startup
- Never re-register dynamically

Payload reference passed via:

(ArenaID, offset, length)

---

# 9. Allocation Failure Policy

If insufficient contiguous space:

Option A: Wrap-around (preferred)
Option B: Drop packet
Option C: Backpressure shard

Never:

Block worker thread.
Attempt heap allocation fallback.

---

# 10. Reclamation Strategy

Safe reclaim when:

Packet referencing region has been fully processed.

Implementation:

Worker maintains:

last_processed_offset

Arena free region =

write_offset - read_offset

No global GC.

---

# 11. Memory Safety Rules

Arena must not:

- Return raw mutable references to Python
- Allow pointer escaping
- Allow resizing

All access inside Rust only.

Python sees only:

ArenaRef { arena_id, offset, length }

---

# 12. Fragmentation Prevention

Fragmentation avoided by:

- Strict circular allocation
- Fixed alignment
- No variable header expansion

Worst-case internal waste:

< 63 bytes per allocation

Acceptable for performance.

---

# 13. Batch Integration

Batch building process:

1. Inline small payloads
2. Large payloads stored in arena
3. Packet stores ArenaRef

ArenaRef structure must fit within 48 bytes inline_data area.

---

# 14. Size Guidelines

Recommended arena size per worker:

64MB – 512MB

Depends on:

- Expected payload size
- In-flight window
- Network latency

Arena must handle:

At least 10ms of peak traffic.

---

# 15. Throughput Impact

Arena operations must cost:

≤ 15ns per allocation

Operations allowed:

- Atomic load
- Integer arithmetic
- memcpy (small payload only)

No malloc.
No free.
No lock.

---

# 16. Memory Fence Requirements

write_offset update:

Release ordering

read_offset update:

Release ordering

Readers use:

Acquire ordering

Ensures no torn payload.

---

# 17. Failure Mode

If corruption detected:

- Drop packet
- Log async
- Continue

Never panic in hot path.

---

# 18. Monitoring Metrics

Expose per shard:

- arena_used_bytes
- arena_capacity
- allocation_failures
- wraparound_count

Metrics must not touch hot path atomics.

---

# 19. Hard Red Lines

Arena must never:

- Allocate memory dynamically
- Resize
- Be shared across cores
- Use Mutex
- Use Vec::push
- Trigger page fault in hot path

---

# 20. Physics Reminder

Memory latency:

L1: ~1ns
L2: ~4ns
L3: ~10ns
RAM: ~80-120ns

If arena access misses cache,
15M target collapses.

Keep working set small.
Keep arena shard-local.
Keep hot metadata cache-resident.

---

# 21. Lifecycle

Arena initialized at startup.

Never destroyed until shutdown.

No mid-flight resize allowed.

---

# 22. Future Extension

Optional:

- HugePages backing
- Transparent Huge Pages disabled
- Memory pre-touching at boot

---

# END OF SPEC
