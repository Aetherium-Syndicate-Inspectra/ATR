# Contributing to ATR Core

ATR Core is **production-critical Class D infrastructure**.
Every change must preserve determinism, immutability, and validation guarantees.

## 1) Before Opening a PR

- Read `AGENTS.md` (core invariants policy).
- Read `ARCHITECTURE.md` and `SPEC.md`.
- Identify impacted invariant sections (determinism/correctness/security/performance).
- Document risk and expected behavior changes in PR description.

## 2) Required Validation by Change Type

### Core logic changes (`core/`, `internal/`, gate handling)
Must include relevant tests:
- Canonicalization/hash/signature unit tests
- Replay/snapshot equivalence tests
- Idempotency/dedup tests
- Failure-injection tests for persistence/ack/recovery paths

### Spec-only or documentation-only changes
- Ensure consistency with benchmark contract and invariants.
- Avoid modifying acceptance criteria without explicit versioned rationale.

## 3) Prohibited Changes

- Embedding business logic in core kernel.
- Bypassing schema/canonicalization/signature/ruleset enforcement.
- Relaxing quarantine policy for invalid envelopes.
- Claiming exactly-once without formal failure-injection evidence.
- Weakening benchmark thresholds without contract version bump.

## 4) Commit Message Convention

Use axis-scoped commit subjects:
- `[transport] ...`
- `[immune] ...`
- `[state] ...`
- `[governance] ...`
- `[docs] ...`

Examples:
- `[immune] enforce canonical float normalization`
- `[state] fix deterministic snapshot replay ordering`
- `[docs] align architecture and spec with Class D invariants`

## 5) Review Expectations

Core-impacting changes should receive:
- at least one architecture-aware reviewer,
- benchmark validation evidence when performance path is touched,
- explicit acknowledgment of invariant compliance.
