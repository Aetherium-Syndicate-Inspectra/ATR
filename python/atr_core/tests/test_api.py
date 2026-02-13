from __future__ import annotations

import json

from atr_core.api.quarantine import serialize_for_quarantine


def test_serialize_for_quarantine_prefers_canonical_bytes() -> None:
    canonical = b'{"header":{"id":"1"}}'
    envelope = {"header": {"id": "1"}}
    assert serialize_for_quarantine(envelope, canonical) == canonical


def test_serialize_for_quarantine_falls_back_for_schema_invalid_envelope() -> None:
    malformed = {"meta": {"correlation_id": "c1"}, "signature": "sig"}
    serialized = serialize_for_quarantine(malformed, b"")
    assert json.loads(serialized.decode("utf-8")) == malformed
