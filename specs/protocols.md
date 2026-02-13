# ATR Gate Protocols (High-Level)

## Gate 1: Ingress
- Accept AkashicEnvelope v2 submissions.
- Enforce immune pipeline before admission.
- Return deterministic accept/reject outcome.

## Gate 2: Stream
- Publish canonical accepted events.
- Preserve authoritative stream sequence metadata.

## Gate 3: Query
- Expose materialized snapshot and immutable ledger query surfaces.
- Query must not mutate state.

## Gate 4: Admin
- Health and governance operations only.
- Access control and auditability are mandatory.
