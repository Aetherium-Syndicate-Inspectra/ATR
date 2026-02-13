from __future__ import annotations

from typing import Any

from atr_core.core.canonicalization import CanonicalizationError, canonical_input, canonicalize_json


def serialize_for_quarantine(envelope: dict[str, Any], canonical_envelope: bytes) -> bytes:
    if canonical_envelope:
        return canonical_envelope
    try:
        return canonicalize_json(canonical_input(envelope))
    except (KeyError, TypeError, CanonicalizationError):
        return canonicalize_json(envelope)
