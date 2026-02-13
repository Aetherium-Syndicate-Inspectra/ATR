# ATR Core Invariants (Class D) — Policy for Codex

This repository contains **ATR Core Server (Class D)**: a Deep Core “Ground Truth Authority”.
Treat changes here as **production-critical infrastructure**.

If any instruction conflicts with convenience, prefer:
**determinism > correctness > safety > performance > convenience**.

---

## 0) Non-negotiable scope boundaries

### ATR Core MUST remain a “No-Touch Kernel”
- ATR Core must remain **business-logic agnostic**.
- Do not embed agent reasoning, LLM prompts, or domain workflows inside core.
- Core accepts/enforces **contracts**, records **truth**, and publishes **canonical events**.

### Do not expand external surfaces
Only these 4 gates may exist:
1. Ingress (submit envelope)
2. Stream (subscribe events)
3. Query (state + ledger)
4. Admin (health + governance)

Any new external endpoint requires explicit design review.

---

## 1) Determinism invariants (hard requirement)

### 1.1 Deterministic serialization
- Canonicalization must be defined in **bytes**, not “pretty JSON”.
- Hash/signature MUST be computed over canonical bytes.
- No whitespace / key-order / float formatting may alter canonical bytes.

### 1.2 No hidden non-determinism
Core changes MUST NOT introduce:
- time-dependent logic (except via explicit timestamps in envelope)
- random number usage
- iteration over unordered maps without stable sorting
- concurrency races that alter outcomes

If uncertain: assume non-deterministic and redesign.

---

## 2) AkashicEnvelope invariants (immutability + verification)

### 2.1 Mandatory checks (never bypass)
For every incoming envelope:
- Schema validation MUST run.
- Canonicalization MUST run.
- Signature verification MUST run (Ed25519).
- Inspira ruleset enforcement MUST run.
- Failed checks MUST route to quarantine (audit.violation), never to main stream.

### 2.2 Envelope immutability
Once accepted:
- Envelope payload becomes immutable truth.
- Any transformation must be done by producing a **new** envelope referencing the old one.

---

## 3) Truth model invariants (E3 Hybrid)

Truth model is fixed:
**Truth = Immutable Log (History) + Materialized Snapshot (Present)**

### 3.1 Log invariants
- Accepted envelopes must be persisted to the log before returning success to Ingress.
- Log must be replayable to reconstruct state deterministically.

### 3.2 Snapshot invariants
- Snapshot is a materialized view derived from log.
- Snapshot may be rebuilt from log at any time.
- Snapshot writes must be idempotent.

### 3.3 Ordering invariants
- Do not claim global time ordering from system clocks.
- Prefer broker sequence / stream sequence for authoritative ordering.

---

## 4) Delivery semantics invariants

### 4.1 Default claim: “effectively-once”
The system may deliver at-least-once, but must guarantee:
- **no double side-effects** in state transitions (idempotent apply)
- dedup window based on `event_id` (uuid-v7)

Do not claim “exactly-once” unless proven under failure injection tests.

---

## 5) Failure-mode invariants (Class D correctness)

Core must fail predictably:
- Overload must trigger backpressure (429/503) rather than uncontrolled memory growth.
- No silent drops of verified events.
- Crash recovery must preserve log truth and converge state deterministically.

Any change touching persistence, acking, replay, or snapshot requires failure injection tests.

---

## 6) Security invariants

- Signature verification is mandatory and must not be weakened.
- Admin endpoints must remain secured (token/MTLS as designed).
- Governance rule reload must be audited (who/when/version) and must not require restart.

---

## 7) Performance invariants (benchmarks are contracts)

Benchmarks are contracts, not suggestions.

- Do not change `specs/benchmark_contract.yaml` thresholds without:
  1) bumping its contract version
  2) documenting rationale
  3) updating acceptance criteria
  4) re-running benchmark suite

Performance work must not compromise determinism or correctness.

---

## 8) Change control: what Codex should do before editing core

Before proposing changes, Codex must:
1. Identify which invariant section is impacted (1–7).
2. State the expected effect on: determinism, correctness, security, performance.
3. Add or update tests:
   - unit tests for canonicalization/hash/signature
   - replay/snapshot equivalence tests
   - crash recovery tests (failure injection)
   - backpressure behavior tests

If unable to test a claim, label it explicitly as unverified.

---

## 9) What NOT to do (explicit prohibitions)

- Do NOT add “helpful” business logic or agent reasoning into core.
- Do NOT accept raw JSON without envelope validation and signature verification.
- Do NOT add new public endpoints casually.
- Do NOT relax quarantine rules.
- Do NOT weaken tail-latency requirements by removing percentile reporting.
