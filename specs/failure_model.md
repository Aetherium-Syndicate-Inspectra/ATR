# ATR Failure Model Specification
Document ID: ATR-FAILURE-2026
Status: LOCKED CONTRACT
Applies To: ATR Core (Python Control Plane + Rust Data Plane + Transport)

---

# 1. Purpose

This document defines the failure model, error taxonomy, and mandatory
failure behaviors of ATR.

Goals:

- Deterministic behavior under faults
- Shard isolation (blast radius containment)
- Fail-closed by default for governance-critical paths
- No cascading collapse
- No deadlocks, no global stalls
- Observable recovery with clear invariants

This is not a "best effort" system. ATR is a Class-D Deep Core.

---

# 2. Core Principles (Non-Negotiable)

## P1: Shard Isolation
Failures must be confined to:
- one worker
- one shard
- one transport lane

No global lock, no shared global queue that can stall the entire system.

## P2: Fail-Closed for Governance
If governance state is unavailable or inconsistent:
- DROP (fail closed)
- never ALLOW by default

## P3: Never Block the Hot Path
Data Plane worker loop must never:
- block on I/O
- wait on locks
- allocate heap under pressure
- retry indefinitely

## P4: Predictable Degradation
Under overload or partial failure:
- drop/throttle selectively
- preserve system liveness
- protect control plane and rule plane

---

# 3. Failure Domains

ATR recognizes distinct failure domains:

| Domain | Examples | Isolation Target |
|--------|----------|------------------|
| Control Plane | Python crash, invalid rule payload | process boundary |
| Rule Plane | malformed ruleset, swap failure | ruleset version boundary |
| Data Plane | queue overflow, panic, memory corruption | per-worker/shard |
| Transport | RDMA CQ error, QP reset, socket failure | per-lane/per-QP |
| Storage | disk full, JetStream unavailable | per-stream / persistence subsystem |
| Network | packet loss, congestion | per-link/per-fabric |

---

# 4. Error Taxonomy (Canonical Codes)

All errors must map to canonical failure codes.

## 4.1 Ingress / Submission Errors
- `E_INGRESS_BAD_PACKET`: invalid packet structure / invariant violated
- `E_INGRESS_QUEUE_FULL`: shard queue full (backpressure)
- `E_INGRESS_MODE_FORBIDDEN`: payload mode not allowed (INLINE vs REF)
- `E_INGRESS_TOO_LARGE`: payload length exceeds arena policy

## 4.2 Governance Errors
- `E_GOV_RULESET_UNAVAILABLE`: rules pointer null (MUST NOT HAPPEN)
- `E_GOV_RULESET_INVALID`: ruleset failed validation
- `E_GOV_DENYLISTED`: topic/sender not allowed
- `E_GOV_THROTTLED`: token bucket depleted
- `E_GOV_QUOTA_EXCEEDED`: in-flight quota exceeded

## 4.3 Arena / Memory Errors
- `E_ARENA_OOM`: arena out of contiguous space
- `E_ARENA_CORRUPT`: checksum mismatch / header invalid
- `E_ARENA_REF_INVALID`: offset/len out of bounds
- `E_ARENA_WRAP_STORM`: excessive wrap-around frequency indicates overload

## 4.4 Transport Errors (io_uring / RDMA)
- `E_TX_SUBMIT_FAIL`: transport submission failed
- `E_TX_CQ_ERROR`: completion queue returned error
- `E_TX_QP_RESET`: RDMA queue pair reset
- `E_TX_TIMEOUT`: completion did not arrive in time
- `E_TX_CONGESTION`: ECN/PFC indicates persistent congestion

## 4.5 Persistence Errors (If enabled)
- `E_PERSIST_UNAVAILABLE`: persistence layer unreachable
- `E_PERSIST_TIMEOUT`: sync ack exceeded budget
- `E_PERSIST_DISK_FULL`: disk full / quota exceeded
- `E_PERSIST_CORRUPT`: WAL/log integrity failure

## 4.6 Internal Errors
- `E_INTERNAL_PANIC`: Rust panic (MUST isolate worker)
- `E_INTERNAL_INVARIANT`: unreachable state, logic corruption
- `E_INTERNAL_OVERFLOW`: counter overflow / timestamp anomaly

---

# 5. Mandatory Failure Behaviors

## 5.1 Queue Full (E_INGRESS_QUEUE_FULL)
Behavior:
- Return immediate error to Control Plane
- Apply shard-local backpressure
- Do NOT block producer

Policy Options (choose one per deployment):
A) Drop-newest (default for real-time)
B) Drop-oldest (for freshness)
C) Throttle (sleep/yield in Control Plane only)

Data Plane must remain live.

---

## 5.2 Arena OOM (E_ARENA_OOM)
Behavior:
- DROP packet (fail closed)
- Increment metric `arena_allocation_failures`
- Optionally signal Control Plane to reduce batch or shed load

Forbidden:
- heap allocation fallback
- resizing arena
- blocking until space frees

---

## 5.3 Governance State Failure
If ruleset invalid or unavailable:
- DROP all packets requiring governance
- SYSTEM_PACKET may bypass only if explicitly allowed in flags

No "best effort allow".

---

## 5.4 Transport Failures (RDMA / io_uring)
Transport failures must isolate to lane/shard:

- Mark lane unhealthy
- Stop posting work to that lane
- Attempt bounded reconnection / reset
- Continue processing other shards

Max retry policy:
- bounded retries (e.g., 3)
- exponential backoff outside hot loop
- no infinite retry in worker

Fallback option:
- if RDMA fails, switch to io_uring (if configured)
- otherwise drop traffic for affected shard

---

## 5.5 Rust Panic / Crash
Worker panic handling:

- Panic must never crash whole process (use panic=abort ONLY if process-level isolation desired)
Preferred:
- isolate worker task
- restart worker thread
- reinitialize queue and arena (or mark shard degraded)

If panic indicates memory corruption:
- fail shard permanently until admin intervention

---

# 6. Overload Model (Graceful Degradation)

Overload indicators:
- queue depth rising
- arena wrap storm
- CQ backlog
- latency P99 rising

Mandatory response ladder (in order):

1) Increase batch size (if within latency budget)
2) Drop low-priority packets
3) Enforce stricter token bucket (throttle)
4) Shed traffic per shard
5) Disable slow-path audit sampling temporarily

Never:
- block worker
- allocate memory to "catch up"

---

# 7. Consistency vs Availability (CAP Stance)

ATR stance:

- Governance-critical events: Consistency > Availability (fail closed)
- Telemetry / metrics: Availability > Consistency (best effort)
- System health: must remain available to report status

---

# 8. Recovery Semantics

## 8.1 Data Plane Restart
On worker restart:
- Load current RCU rules snapshot
- Reset shard-local counters
- Arena reinitialized (discard old payload regions)
- No attempt to recover in-flight packets (at-most-once for those)

## 8.2 Persistence Recovery (if enabled)
If persistence requires durability:
- fail ingestion until persistence returns (configurable)
If real-time mode:
- allow ingestion, mark events as non-durable (explicit flag)

---

# 9. Observability Contract

Must expose metrics (per shard):

- queue_depth
- drops_total (by error code)
- throttled_total
- arena_used_bytes
- arena_allocation_failures
- governance_denies_total
- transport_errors_total
- worker_restart_total
- ruleset_version_active

Logs:
- must be async
- must never occur in hot path per packet
- must include ruleset version and shard id

---

# 10. Audit & Forensics

For events that are dropped due to governance:
- Emit optional audit sample (rate-limited)
- Must not exceed 0.1% of traffic (configurable)
- Must include:
  - topic_id, sender_id, decision, reason code, ruleset version

---

# 11. Hard Red Lines

If any of these occur, the system is considered incorrect:

- Global deadlock
- Global stall due to one shard failure
- Fail-open governance on invalid rules
- Heap allocation in hot loop under overload
- Infinite retry loop in worker
- Rule swap causing multi-millisecond stop-the-world

---

# 12. Acceptance Criteria (Operational)

System must demonstrate:

- Under 2x overload: continues operating with bounded drop rate
- Under 10x overload: does not crash, preserves control plane responsiveness
- Under transport lane failure: other shards continue normally
- Under ruleset invalid update: ruleset rejected, old remains active
- Under arena OOM: drop occurs with metrics and no stall

---

# END OF SPEC
