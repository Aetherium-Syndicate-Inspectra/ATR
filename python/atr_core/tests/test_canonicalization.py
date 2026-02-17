from __future__ import annotations

from atr_core.core.canonicalization import (
    canonicalize_json,
    legacy_canonicalization_code,
    resolve_canonicalization_code,
)
from atr_core.core.security import canonical_hash


def test_canonicalization_is_stable_across_repeated_runs() -> None:
    value = {
        "payload": {
            "é": "accent",
            "items": [{"b": 2, "a": 1}, {"z": [3, 2, 1]}],
        },
        "header": {"type": "state.mutation", "source_agent": "a"},
        "meta": {"correlation_id": "x"},
    }

    hashes = {canonical_hash(canonicalize_json(value)) for _ in range(100)}
    assert len(hashes) == 1


def test_canonicalization_removes_whitespace_and_sorts_by_utf8_key_bytes() -> None:
    # UTF-8 byte order: "A"(0x41) < "a"(0x61) < "é"(0xC3A9)
    value = {"é": 3, "a": 2, "A": 1}
    assert canonicalize_json(value) == '{"A":1,"a":2,"é":3}'.encode('utf-8')


def test_duplicate_key_alias_support() -> None:
    assert resolve_canonicalization_code("CANON_DUPLICATE_KEY_AFTER_NORMALIZE") == (
        "CANON_DUPLICATE_KEY_AFTER_NORMALIZATION"
    )
    assert legacy_canonicalization_code("CANON_DUPLICATE_KEY_AFTER_NORMALIZATION") == (
        "CANON_DUPLICATE_KEY_AFTER_NORMALIZE"
    )
