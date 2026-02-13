# ATR Core Invariants (Condensed)

- ATR Core (Python) enforces: schema, canonicalization, signature, ruleset, quarantine, E3 truth.
- ATB-ET sidecar (Rust) owns transport/persistence adapter and must return broker sequence acks.

Non-negotiables:
1) No bypass of schema/canonical/signature/ruleset checks.
2) Canonicalization is bytes-defined; signature over canonical bytes only.
3) Truth model is E3: log is immutable truth; snapshot is rebuildable view.
4) Delivery is effectively-once via event_id + idempotent apply; never claim exactly-once without failure injection proof.
5) Only 4 external gates: Ingress, Stream, Query, Admin.
