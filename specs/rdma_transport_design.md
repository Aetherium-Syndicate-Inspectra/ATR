# ATR RDMA Transport Design Specification
Document ID: ATR-RDMA-2026
Status: LOCKED CONTRACT
Applies To: Tachyon Data Plane (Rust Only)

---

# 1. Purpose

This document defines the RDMA-based transport architecture
for ATR Tachyon Edition.

Objective:

- Achieve < 1µs hop latency
- Achieve 15M+ msg/sec sustained throughput
- Zero kernel overhead
- Zero copy per packet
- Deterministic hardware-level dispatch

RDMA is not an optimization.
It is a physics-level requirement for sub-microsecond systems.

---

# 2. Architectural Overview

Transport Stack:

Python (Control Plane)
    ↓
Rust Data Plane
    ↓
Pinned Memory Region
    ↓
RDMA NIC (ibverbs / RoCEv2)
    ↓
Remote NIC
    ↓
Remote Pinned Memory

CPU does not copy payload.
Kernel does not mediate packet flow.

---

# 3. RDMA Modes Supported

Mode A: SEND / RECV
Mode B: WRITE (Preferred)
Mode C: WRITE_WITH_IMM (Optional for signaling)

Preferred:

RDMA WRITE
→ remote memory update without remote CPU involvement.

---

# 4. Memory Registration Model

All transmit buffers must be:

- Pre-allocated
- Page-locked (pinned)
- Registered via ibv_reg_mr()
- Aligned to 64 bytes

No dynamic memory registration allowed in hot path.

Memory must remain registered for lifetime of process.

---

# 5. Memory Region Layout

Each worker thread owns:

struct RDMARegion {
    base_ptr: *mut u8,
    size: usize,
    lkey: u32,
    rkey: u32,
}

Region must be:

- Shard-local
- NUMA-aware
- Cache-aligned

Packet layout inside region:

| Offset | Content |
|--------|----------|
| 0      | Batch header |
| 64     | TachyonPacket[4096] |
| ...    | Reserved |

---

# 6. Queue Pair (QP) Model

Each worker thread owns:

- Dedicated Queue Pair
- Dedicated Completion Queue
- Dedicated Send Queue
- Dedicated Receive Queue (if needed)

No sharing QP across cores.

---

# 7. Flow: Batch Dispatch

Worker loop:

1. Drain local packet queue
2. Fill batch buffer in pinned region
3. Post RDMA WRITE
4. Poll completion queue
5. Recycle buffer

No blocking allowed.
Polling allowed on dedicated core.

---

# 8. Completion Queue Strategy

CQ polling modes:

Mode A: Busy polling (Ultra low latency)
Mode B: Adaptive polling (fallback)

For <1µs target:

Busy polling on dedicated core.

CPU cost accepted.
Latency deterministic.

---

# 9. Zero-Copy Guarantee

Data must move:

TachyonPacket (stack)
    →
Pinned batch buffer
    →
NIC DMA read
    →
Wire

No memcpy after batch assembly.

Serialization must occur before copy to pinned region.

---

# 10. NUMA Constraint

Memory region must be allocated on same NUMA node as:

- Worker thread
- NIC PCIe lane

Cross-socket RDMA incurs ~100ns penalty.

---

# 11. Transport Latency Budget

Local dispatch:

Queue pop → RDMA post:
≤ 200ns

Wire latency:
~500ns (datacenter fabric)

Remote write completion:
~500ns

Total hop:
≤ 1.5µs

---

# 12. Throughput Physics

NIC limit:

100GbE ≈ 12.5GB/sec

If packet size = 64 bytes:

12.5GB/sec / 64B ≈ 195M packets/sec (theoretical)

Practical limit:
15–50M msg/sec depending on CPU + batching.

Network bandwidth is not bottleneck.
Memory and CPU are.

---

# 13. Congestion Control

Must use:

RoCEv2 with PFC (Priority Flow Control)
ECN recommended

Lossless fabric required.

Packet loss invalidates latency guarantees.

---

# 14. Backpressure Model

If CQ depth > threshold:

- Stop posting new WR
- Signal shard-local backpressure
- Drop or throttle upstream

Never block worker thread.

---

# 15. Failure Handling

If RDMA error:

- Log asynchronously
- Isolate shard
- Fail closed (drop traffic)

Never stall other shards.

---

# 16. Security Considerations

RKey must:

- Be per-connection
- Rotatable
- Not exposed to Python

Memory bounds must be validated before write.

---

# 17. Multi-Core Scaling

Each core:

- Own RDMA QP
- Own pinned region
- Own completion queue

No shared send queue across cores.

---

# 18. Integration with Governance

Governance must execute before:

RDMA post

Never after network dispatch.

Packets must be clean before hardware submission.

---

# 19. Observability

Expose per-core metrics:

- rdma_posts
- rdma_completions
- cq_poll_cycles
- write_failures
- avg_dispatch_ns

Metrics must not pollute hot path.

---

# 20. Fallback Mode

If RDMA not available:

Fallback to:

io_uring with batch send

Architecture must be pluggable via:

TransportSelector

---

# 21. Hard Red Lines

If system does:

- Per-packet ibv_reg_mr()
- Shared QP across threads
- Mutex around CQ
- Dynamic memory allocation in hot path
- Blocking recv()

Sub-microsecond target is impossible.

---

# 22. Deployment Requirements

Hardware:

- Mellanox ConnectX-5+
- 100GbE+ fabric
- Lossless switch
- NUMA-aware BIOS configuration
- Hyperthreading disabled (recommended)

Kernel:

- HugePages enabled
- IRQ affinity configured
- CPU isolation enabled

---

# 23. Physics Reminder

RDMA does not make bad architecture fast.

If governance path takes 200ns,
RDMA will not save you.

RDMA removes kernel overhead.
It does not remove bad memory design.

---

# END OF SPEC
