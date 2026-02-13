# ATR Core Technical Specification

## 1) AkashicEnvelope Specification

All incoming payloads must conform to AkashicEnvelope v2 contract.

Required envelope fields:
- `header.id` (uuid-v7)
- `header.timestamp`
- `header.source_agent`
- `payload`
- `signature` (Ed25519)

Mandatory ingress pipeline:
1. Schema validation
2. Deterministic canonicalization
3. Signature verification
4. Inspira ruleset enforcement

Failure behavior:
- Failed envelopes are quarantined to `audit.violation`.
- Failed envelopes MUST NOT enter main stream or state path.

---

## 2) Canonicalization and Hashing Rules

- Canonical form is byte-deterministic and independent of formatter preferences.
- Hash/signature input MUST be canonical bytes.
- No whitespace, key-order drift, or serializer float style may alter identity.

---

## 3) Delivery Semantics

Default guarantee: **effectively-once**.

Implemented as:
- at-least-once transport,
- idempotent apply logic,
- dedup window keyed by `event_id` (uuid-v7).

Exactly-once claims are forbidden unless validated through failure-injection suites.

---

## 4) State Authority Model (E3 Hybrid)

Truth model:

**Truth = Immutable Log + Materialized Snapshot**

Requirements:
- Log append must complete before ingress success acknowledgement.
- Snapshot is derived state and must be rebuildable from log.
- Replay must reconstruct deterministic state equivalence.
- Snapshot writes must remain idempotent.

---

## 5) Security Requirements

- Signature verification is mandatory and cannot be bypassed.
- Schema validation is mandatory and cannot be bypassed.
- Governance ruleset reloads must be auditable (who/when/version).
- Admin surface must remain secured by configured auth controls.

---

## 6) Performance Contract

Benchmark acceptance criteria are defined in `specs/benchmark_contract.yaml`.

At minimum:
- Containerized mode keeps tail latency within contract thresholds.
- Tachyon mode targets sub-millisecond p99 class and high-throughput thresholds.
- Any threshold changes require contract version bump and rationale.

---

## 7) Failure and Recovery Requirements

Required correctness behaviors:
- No silent drop of verified events.
- Predictable overload handling (429/503 + bounded resource growth).
- Crash recovery must preserve log truth and deterministic state convergence.
