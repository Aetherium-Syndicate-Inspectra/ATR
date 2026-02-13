# ATR Observability Contract
Document ID: ATR-OBS-2026
Status: LOCKED CONTRACT
Applies To: ATR Core (Control Plane + Data Plane + Transport + Persistence)

---

# 1. Purpose

This document defines the canonical observability contract for ATR:

- Prometheus metric naming and label rules
- SLI/SLO definitions (latency/throughput/errors/drops)
- Dashboard contract (Grafana panels + PromQL templates)
- Alerting contract (severity + routing)
- Hot-path observability constraints (no performance regressions)

Observability is part of governance.
If it is not measurable, it is not real.

---

# 2. Golden Rules (Non-Negotiable)

## G1: Hot Path Isolation
No per-packet logging.
No per-packet allocations for metrics.
No label cardinality explosion.

Metrics must not meaningfully reduce throughput.

## G2: Metric Stability
Once a metric name is shipped:
- Never change semantics
- Never change units
- Never change label meaning
Deprecate instead of modifying.

## G3: Bounded Cardinality
Labels must be bounded and enumerable.
No user_id, request_id, raw topic strings, or arbitrary keys as labels.

## G4: Canonical Units
- Latency: seconds in Prometheus, report conversions in dashboards
- Throughput: messages/sec (derived via rate())
- Sizes: bytes
- Time: seconds (Prometheus standard)
- CPU: seconds (process_cpu_seconds_total)

---

# 3. Naming Convention

All ATR metrics MUST follow:

`atr_<subsystem>_<metric>_<unit>`

Examples:
- atr_dp_packets_processed_total
- atr_dp_batch_duration_seconds
- atr_tx_rdma_posts_total
- atr_bp_state

Rules:
- Counters end with `_total`
- Histograms end with `_seconds` / `_bytes`
- Gauges do NOT end with `_total`

---

# 4. Label Convention

Allowed labels (bounded):

- `shard` (small integer string, e.g. "0".."63")
- `worker` (small integer string)
- `transport` ("rdma" | "io_uring" | "nats" | "disabled")
- `decision` ("allow" | "drop" | "throttled")
- `reason` (canonical reason codes only)
- `priority` ("p0" | "p1" | "p2" | "p3")
- `mode` ("inline" | "arena" | "shm")
- `phase` ("ingress" | "governance" | "dispatch" | "persist")

Forbidden labels:
- topic string
- sender string
- request_id
- envelope_id
- correlation_id
- arbitrary exception text
- raw error message

---

# 5. Required Metrics (Canonical Set)

## 5.1 Control Plane (Python)

### Throughput / Admission
- `atr_cp_submit_calls_total{shard}`
- `atr_cp_submit_failures_total{shard,reason}`

### Batching
- `atr_cp_batch_size_current{shard}` (gauge)
- `atr_cp_batch_build_duration_seconds{shard}` (histogram)

---

## 5.2 Data Plane (Rust)

### Packet Flow
- `atr_dp_packets_processed_total{shard,priority}`
- `atr_dp_packets_dropped_total{shard,reason,priority}`
- `atr_dp_packets_throttled_total{shard,reason,priority}`

### Queue
- `atr_dp_queue_depth{shard}` (gauge)
- `atr_dp_queue_full_total{shard}` (counter)

### Batch
- `atr_dp_batch_size{shard}` (histogram or gauge)
- `atr_dp_batch_duration_seconds{shard}` (histogram)

### Governance Fast Path
- `atr_gov_eval_total{shard,decision}`
- `atr_gov_eval_duration_seconds{shard}` (histogram)
- `atr_gov_ruleset_version{shard}` (gauge)
- `atr_gov_ruleset_swaps_total{shard}` (counter)
- `atr_gov_ruleset_validation_failures_total{shard}` (counter)

---

## 5.3 Arena (Large Payload)

- `atr_arena_used_bytes{shard}` (gauge)
- `atr_arena_capacity_bytes{shard}` (gauge)
- `atr_arena_alloc_failures_total{shard}` (counter)
- `atr_arena_wraparounds_total{shard}` (counter)

---

## 5.4 Transport

### Generic
- `atr_tx_dispatch_total{shard,transport}`
- `atr_tx_errors_total{shard,transport,reason}`
- `atr_tx_backlog{shard,transport}` (gauge)
- `atr_tx_dispatch_duration_seconds{shard,transport}` (histogram)

### RDMA-specific
- `atr_tx_rdma_posts_total{shard}`
- `atr_tx_rdma_completions_total{shard}`
- `atr_tx_rdma_cq_errors_total{shard}`
- `atr_tx_rdma_cq_poll_cycles_total{shard}`

### io_uring-specific (optional)
- `atr_tx_uring_submits_total{shard}`
- `atr_tx_uring_completions_total{shard}`
- `atr_tx_uring_errors_total{shard}`

---

## 5.5 Persistence (Optional)

- `atr_persist_writes_total{shard}`
- `atr_persist_write_duration_seconds{shard}` (histogram)
- `atr_persist_errors_total{shard,reason}`
- `atr_persist_backlog{shard}` (gauge)

---

## 5.6 Backpressure

- `atr_bp_state{shard}` (gauge: 0=GREEN,1=YELLOW,2=ORANGE,3=RED)
- `atr_bp_state_changes_total{shard,from,to}`
- `atr_bp_recommended_batch_size{shard}` (gauge)
- `atr_bp_drop_rate{shard}` (gauge, optional computed)

---

## 5.7 Process / System

Use standard exporters:
- `process_cpu_seconds_total`
- `process_resident_memory_bytes`
- `go_goroutines` (if any Go components)
- node_exporter metrics (CPU freq, irq, net)

---

# 6. SLI / SLO Contract

## 6.1 Latency SLO (Data Plane)
SLI: batch processing latency (P99)
PromQL:
- `histogram_quantile(0.99, sum(rate(atr_dp_batch_duration_seconds_bucket[5m])) by (le))`

SLO Targets:
- Internal mode: P99 ≤ 5 µs
- Network mode: P99 ≤ 10 µs
- RDMA mode: P99 ≤ 2 µs

---

## 6.2 Throughput SLO
SLI: processed msg/sec
PromQL:
- `sum(rate(atr_dp_packets_processed_total[1m]))`

Target:
- Option C baseline: ≥ 5,000,000 msg/sec sustained (cluster total)

---

## 6.3 Drop Rate SLO
SLI: drop rate ratio
PromQL:
- `sum(rate(atr_dp_packets_dropped_total[1m])) / sum(rate(atr_dp_packets_processed_total[1m]))`

Targets:
- Normal load: < 0.1%
- Overload: bounded, must not exceed configured cap per shard (e.g. 20% in RED)

---

## 6.4 Governance Correctness SLO
SLI: rule swap failures
PromQL:
- `sum(rate(atr_gov_ruleset_validation_failures_total[5m]))`

Target:
- 0 failures in normal operation

---

## 6.5 Transport Health SLO
SLI: transport error rate
PromQL:
- `sum(rate(atr_tx_errors_total[1m]))`

Target:
- 0 sustained errors
- burst errors must self-recover within 30s

---

# 7. Grafana Dashboard Contract (Panels)

A canonical dashboard MUST include:

## Overview Row
1) Total Throughput (msg/s)
2) P99 Batch Latency (µs)
3) Drop Rate (%)
4) Backpressure State Summary (GREEN/YELLOW/ORANGE/RED)

## Data Plane Row
5) Queue Depth per Shard
6) Batch Size distribution
7) Batch Duration histogram

## Governance Row
8) Decisions (ALLOW/DROP/THROTTLED) per shard
9) Ruleset Version per shard
10) Rule swap count & failures

## Arena Row
11) Arena utilization per shard
12) Allocation failures & wraparounds

## Transport Row
13) Dispatch throughput per transport
14) Backlog per transport lane
15) RDMA CQ errors / completions (if rdma)

## Backpressure Row
16) State over time per shard
17) Recommended batch size per shard
18) Drops by priority under backpressure

---

# 8. Alerting Contract

Alerts must be defined by severity.

## SEV0 (Page Immediately)
- shard stuck in RED for > 60s
- sustained transport errors > 0 for > 30s
- ruleset pointer invalid (should never happen)
- worker restart loop (restarts > 3 in 5m)

## SEV1 (Urgent)
- P99 latency > 2x SLO for > 5m
- drop rate > 1% under normal load (GREEN/YELLOW)
- arena alloc failures > 0 for > 1m

## SEV2 (Watch)
- ORANGE state > 10m
- throughput below baseline for > 10m
- CQ backlog rising persistently

Alerts must include:
- shard
- transport
- reason
- current ruleset version

---

# 9. Logging Contract

Logs are NOT metrics.

Logging rules:
- No per-packet logs
- Log only state transitions, worker lifecycle events, ruleset updates, transport failures
- All logs must include:
  - shard
  - worker
  - ruleset_version
  - transport mode

---

# 10. Sampling & Audit Channel

For forensic needs:
- allow sampled audit events (e.g., 0.01% traffic)
- emitted to separate channel (not hot path)
- must be rate limited and bounded

Audit sample must include:
- topic_id
- sender_id
- priority
- decision
- reason
- ruleset_version

---

# 11. Acceptance Criteria

System is compliant if:

- All canonical metrics exist with correct units
- No forbidden label cardinality
- Dashboards render with PromQL listed above
- Alerts fire correctly in fault injection tests
- Throughput impact from metrics < 2% under peak load

---

# END OF CONTRACT
