# ATR Backpressure Model Specification
Document ID: ATR-BACKPRESSURE-2026
Status: LOCKED CONTRACT
Applies To: ATR Core (Python Control Plane + Rust Data Plane + Transport)

---

# 1. Purpose

This document defines the deterministic backpressure model for ATR.

Goals:

- Prevent uncontrolled overload collapse
- Maintain liveness of the Data Plane
- Keep governance correctness (fail-closed)
- Contain blast radius per shard
- Provide predictable degradation behavior
- Avoid global stalls, locks, and thundering herds

Backpressure is not a feature.
It is a survival mechanism for Tachyon-grade systems.

---

# 2. Core Principles (Non-Negotiable)

## BP1: Shard-Local First
Backpressure decisions must be taken per shard.
No global "stop-the-world" throttling.

## BP2: Never Block the Hot Path
Rust workers must never block on backpressure.
They enforce it by:
- dropping
- throttling
- reducing work admitted

## BP3: Deterministic Policy Order
Backpressure must apply in a fixed escalation ladder
so behavior is predictable and testable.

## BP4: Fail-Closed for Governance
When in doubt, drop governance-required packets first.

---

# 3. Backpressure Signals (Inputs)

Backpressure decisions use these signals per shard:

| Signal | Meaning | Metric |
|--------|---------|--------|
| Queue Depth | Ingress backlog | queue_depth |
| Queue Full Events | Admission failures | queue_full_total |
| Arena Utilization | Large payload pressure | arena_used_bytes / arena_capacity |
| Arena Failures | Arena OOM / wrap storm | arena_allocation_failures |
| Transport Backlog | CQ depth / io_uring backlog | tx_backlog |
| Latency P99 | Service degradation | latency_p99_us |
| Drop Rate | Current shedding | drops_total rate |
| CPU Saturation | Worker pinned core pressure | cpu_util_per_worker |

---

# 4. Backpressure States

Each shard is always in exactly one state:

| State | Description |
|-------|-------------|
| GREEN | Normal operation |
| YELLOW | Rising backlog; begin soft control |
| ORANGE | Sustained overload; aggressive shedding |
| RED | Critical; protect core; drop most traffic |

State transitions are per shard.

---

# 5. Thresholds (Default)

Thresholds are configurable, but defaults must exist.

## 5.1 Queue thresholds
- `Q_YELLOW`: queue_depth > 50% capacity
- `Q_ORANGE`: queue_depth > 80% capacity
- `Q_RED`: queue_depth > 95% capacity OR queue_full spikes

## 5.2 Arena thresholds
- `A_YELLOW`: arena_used > 60%
- `A_ORANGE`: arena_used > 80%
- `A_RED`: arena_alloc_failures > 0 in last window

## 5.3 Transport thresholds
- `T_ORANGE`: tx_backlog > high watermark
- `T_RED`: completion errors present OR timeout rate rising

## 5.4 Latency thresholds
- `L_YELLOW`: latency_p99_us > budget * 1.25
- `L_ORANGE`: latency_p99_us > budget * 2.0
- `L_RED`: latency_p99_us > budget * 5.0

Budgets defined in `specs/latency_budget.md`.

---

# 6. Escalation Ladder (Deterministic Order)

When a shard is overloaded, ATR applies countermeasures in order.
Once a stronger measure is applied, weaker ones remain active until recovery.

## Level 0 (GREEN): Normal
- Admit all packets
- Standard governance checks
- Standard batching

## Level 1 (YELLOW): Soft Control
1) Increase batch size (within latency constraints)
2) Reduce slow-path sampling (audit/off-hot-path)
3) Prefer inline packets over arena packets (if policy allows)

## Level 2 (ORANGE): Aggressive Shedding
4) Drop LOW priority packets first
5) Enforce stricter token bucket (lower effective refill)
6) Deny large payload modes (REF_ARENA / REF_SHM) if arena pressure high
7) Reduce per-sender quotas temporarily (shard-local)

## Level 3 (RED): Core Protection
8) Allow only SYSTEM_PACKET (optional, if configured)
9) Drop all governance-required packets that exceed minimal criteria
10) Drop everything except keepalive/health telemetry (configurable)
11) Freeze shard admission (return E_INGRESS_QUEUE_FULL to control plane)

NOTE:
- "Freeze admission" must not block workers.
- It is an admission-side decision.

---

# 7. Priority Classes (Required)

Each packet must be classified before admission:

| Class | Meaning | Default action under load |
|------|---------|---------------------------|
| P0 | SYSTEM / HEALTH | Preserve longest |
| P1 | Governance-critical | Preserve until ORANGE, may drop in RED |
| P2 | Normal | Drop in ORANGE |
| P3 | Best-effort | Drop first in YELLOW/ORANGE |

Priority encoding:
- Either in `flags` bitmask
- Or derived from topic_id mapping

No string lookup in hot path.

---

# 8. Admission Control Rules

Admission control happens at the boundary (Control Plane → Data Plane).

## 8.1 If queue is full
Return:
- `E_INGRESS_QUEUE_FULL`

Do NOT:
- block
- spin
- sleep in Rust

Control Plane may:
- retry with jittered backoff
- batch more aggressively
- route to alternate shard (only if sharding allows)

## 8.2 If arena is constrained
If payload mode is REF_ARENA/REF_SHM:
- deny admission or downgrade to DROP based on state (ORANGE/RED)

---

# 9. Adaptive Batch Policy

Batch size may increase under backlog, but must respect latency budget.

Constraint:

- Batch fill time must not exceed configured max (e.g. 5–10µs)
- Batch size must be capped (e.g. 4096)

Rules:
- In YELLOW, increase batch size up to cap
- In ORANGE, lock batch size at cap
- In RED, stop waiting to fill; process immediately to drain

---

# 10. Transport-Aware Backpressure

If transport backlog increases:

- Stop posting new RDMA WR beyond limit
- Switch to smaller batches (to reduce buffer residency) OR
  switch to larger batches (to reduce post frequency) depending on mode:

Decision:
- RDMA: prefer larger batch to reduce CQ churn
- io_uring: prefer medium batch to avoid tail latency spikes

Transport selector must expose:
- backlog watermark
- completion error counts

---

# 11. Recovery Model (Hysteresis)

State recovery must use hysteresis to avoid oscillation.

Example:

- YELLOW → GREEN only if queue_depth < 30% for 3 windows
- ORANGE → YELLOW only if queue_depth < 60% for 5 windows
- RED → ORANGE only if queue_depth < 85% for 10 windows and no errors

Window length default:
- 100ms (tunable)

---

# 12. Coordination Between Planes

## 12.1 Data Plane → Control Plane signals
Control Plane receives:
- shard_state
- recommended_batch_size
- reason codes (queue, arena, transport, latency)

Must be rate-limited.

## 12.2 Control Plane behavior under backpressure
Control Plane must:
- increase batch size
- reduce submission frequency
- shed low-priority traffic early

Control Plane must not:
- retry in tight loop
- explode into thundering herd

---

# 13. Observability Contract

Expose metrics per shard:

- backpressure_state{shard}
- recommended_batch_size{shard}
- queue_depth{shard}
- drops_total{shard,reason}
- throttled_total{shard,reason}
- arena_used_bytes{shard}
- tx_backlog{shard}

Expose global summary:
- shards_in_red
- total_drop_rate

Logs:
- state changes only (not per packet)
- include thresholds crossed and reason

---

# 14. Testing Requirements (Acceptance)

The model must pass:

1) 2x overload test:
- system remains live
- drop rate bounded
- no global stall

2) 10x overload test:
- shards isolate
- control plane remains responsive

3) Arena stress:
- large payload flood triggers ORANGE/RED correctly
- no heap allocation fallback

4) Transport failure injection:
- affected shard enters RED
- other shards unaffected

---

# 15. Hard Red Lines

Invalid implementations:

- Global lock controlling admission for all shards
- Blocking Rust worker on queue full
- Per-packet logging during overload
- Global atomic rate limiter per packet
- Infinite retry loop in control plane

Any of these void this specification.

---

# END OF SPEC
