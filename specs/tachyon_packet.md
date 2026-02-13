# TachyonPacket Specification
Document ID: ATR-TACHYON-PACKET-2026  
Status: LOCKED CONTRACT  
Applies To: AetherBus Tachyon (Rust Data Plane)

---

## 1. Purpose

TachyonPacket is the fixed-size, cache-aligned transport unit used inside the Tachyon Data Plane. It replaces dynamic message objects, JSON payloads, and heap-allocated envelopes in the hot path.

This structure is optimized for:

- 15M+ msg/sec raw throughput
- Lock-free queue transport
- Single cache-line fetch per message
- Zero dynamic allocation
- SIMD-friendly processing
- Deterministic memory layout

---

## 2. Memory Layout Contract

### Design Principles

1. Exactly 64 bytes (1 CPU cache line)
2. `#[repr(C, align(64))]`
3. `Copy + Clone` (no `Drop` implementation)
4. No heap allocation
5. No internal pointer ownership
6. Safe to move across threads without GC interaction

---

## 3. Rust Definition (Authoritative)

```rust
#[repr(C, align(64))]
#[derive(Copy, Clone)]
pub struct TachyonPacket {
    // 8 bytes
    pub flags: u64,

    // 4 bytes
    pub topic_id: u32,

    // 4 bytes
    pub sender_id: u32,

    // 48 bytes
    pub data: [u8; 48],
}

const _: () = assert!(std::mem::size_of::<TachyonPacket>() == 64);
```

Total size: 64 bytes exactly.

---

## 4. Header Field Specification

### 4.1 `flags` (`u64`)

Bitmask controlling packet semantics.

| Bit | Meaning |
|---:|---|
| 0 | INLINE_PAYLOAD |
| 1 | REF_ARENA |
| 2 | REF_SHM |
| 3 | GOVERNANCE_REQUIRED |
| 4 | SYSTEM_PACKET |
| 5 | PRIORITY_HIGH |
| 6–15 | Reserved |
| 16–63 | Custom extension bits |

Rules:

- Exactly one payload mode bit must be set.
- Governance bit determines whether fast-path rule evaluation applies.

### 4.2 `topic_id` (`u32`)

- 32-bit hash of canonical topic string
- Pre-hashed in Control Plane
- No string comparison in Data Plane
- Hash collision resolution must not occur in hot path

### 4.3 `sender_id` (`u32`)

- Node or agent identifier
- Used for rate limiting / quota enforcement
- Must not require dynamic lookup

---

## 5. Payload Modes

The 48-byte `data` region operates in one of three modes.

### 5.1 INLINE_PAYLOAD

Used for small control signals or compact commands.

Layout (example convention):

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | `timestamp_ns` |
| 8 | 4 | `type_id` |
| 12 | 36 | payload bytes |

Rules:

- No deserialization in hot path.
- Interpretation must be zero-copy.

### 5.2 REF_ARENA

Used when payload exceeds 48 bytes.

Layout inside `data`:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | `arena_id` |
| 4 | 8 | `offset` |
| 12 | 4 | `length` |
| 16 | 8 | `checksum` |
| 24 | 24 | reserved |

Arena rules:

- Arena must be pre-allocated.
- No per-message allocation allowed.
- Lifecycle controlled by Rust Data Plane.
- Python must never own arena memory.

### 5.3 REF_SHM

Used for shared memory segment (inter-process or RDMA).

Layout:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | `shm_segment_id` |
| 8 | 8 | `offset` |
| 16 | 4 | `length` |
| 20 | 8 | `checksum` |
| 28 | 20 | reserved |

Requirements:

- Memory must be pinned (no paging).
- Lifetime must outlive packet processing.
- RDMA registration must occur at startup.

---

## 6. Performance Invariants

Mandatory guarantees:

- No JSON
- No `Vec` allocation per packet
- No `String` allocation
- No `Drop` semantics
- No heap reference in struct
- No pointer dereference in fast path

---

## 7. Governance Integration

Fast-path governance operates only on:

- `topic_id`
- `sender_id`
- `flags`

Rules must evaluate in `O(1)`.

Examples:

- token bucket per `topic_id`
- max in-flight per `sender_id`
- deny-list bitmap

Deep validation must occur off hot path.

---

## 8. Queue Compatibility

`TachyonPacket` must be compatible with:

- `crossbeam::ArrayQueue<TachyonPacket>`
- Lock-free MPMC ring
- Pre-allocated batch `Vec<TachyonPacket>`

Batch size target: `256–4096` packets per dispatch.

---

## 9. SIMD & Serialization

If serialization is required:

- Use `rkyv` / FlatBuffers
- Never use JSON
- Never use `serde_json` in Data Plane

SIMD optimization allowed only if:

- data is aligned
- no branch-heavy parsing

---

## 10. Safety Rules

Forbidden in Data Plane:

- `Rc` / `Arc` inside packet
- `Box`
- `Vec`
- `String`
- Dynamic dispatch
- Trait objects
- Panic in hot path

Allowed:

- Copy types
- Fixed arrays
- Atomic operations
- Lock-free structures

---

## 11. Versioning Strategy

Packet layout changes require:

- New flag version bit
- Backward compatibility layer outside hot path
- Full integration test before deployment

---

## 12. Target Throughput Conditions

`15M msg/sec` is achievable only if:

- packet is exactly 64 bytes
- no dynamic allocation
- no per-message FFI crossing
- no syscall per message
- Rust owns dispatch loop
- NUMA-aware core pinning
- L3 cache miss minimized

---

## Constitution Note

This file is the memory constitution of the Tachyon Data Plane. Implementations (human or agent-generated) must not violate this contract.
