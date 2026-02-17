# Immutable Signature Invariants

- Each event signature covers the canonicalized envelope bytes (`header`, `meta`, `payload`).
- The immutable event log is the source of truth (E3); signatures are never recomputed in place.
- Snapshot rebuild must be deterministic from log replay and not mutate original signed bytes.
- Any signature or canonicalization failure is quarantined and cannot be bypassed.
