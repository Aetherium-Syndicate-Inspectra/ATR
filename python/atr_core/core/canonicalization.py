from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass
from typing import Any


CANONICALIZATION_CODE_ALIASES: dict[str, str] = {
    "CANON_DUPLICATE_KEY_AFTER_NORMALIZE": "CANON_DUPLICATE_KEY_AFTER_NORMALIZATION",
}
LEGACY_CANONICALIZATION_CODES: dict[str, str] = {
    "CANON_DUPLICATE_KEY_AFTER_NORMALIZATION": "CANON_DUPLICATE_KEY_AFTER_NORMALIZE",
}


@dataclass(frozen=True)
class CanonicalizationError(ValueError):
    code: str
    message: str


def _normalize(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise CanonicalizationError("CANON_INVALID_NUMBER", "non-finite number")
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, inner in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("CANON_NON_STRING_KEY", "map key must be string")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise CanonicalizationError(
                    "CANON_DUPLICATE_KEY_AFTER_NORMALIZATION",
                    "duplicate map key after NFC normalization",
                )
            normalized[normalized_key] = _normalize(inner)
        return normalized
    raise CanonicalizationError("CANON_FORBIDDEN_TYPE", f"unsupported type: {type(value)!r}")


def resolve_canonicalization_code(code: str) -> str:
    return CANONICALIZATION_CODE_ALIASES.get(code, code)


def legacy_canonicalization_code(code: str) -> str:
    return LEGACY_CANONICALIZATION_CODES.get(code, code)


def canonical_input(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "header": envelope["header"],
        "meta": envelope.get("meta", {}),
        "payload": envelope["payload"],
    }


def _encode_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _encode_canonical(value: Any) -> str:
    if isinstance(value, dict):
        ordered_keys = sorted(value, key=lambda key: key.encode("utf-8"))
        parts = [f"{_encode_string(key)}:{_encode_canonical(value[key])}" for key in ordered_keys]
        return "{" + ",".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_encode_canonical(item) for item in value) + "]"
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def canonicalize_json(value: Any) -> bytes:
    normalized = _normalize(value)
    try:
        return _encode_canonical(normalized).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError("CANON_ENCODING_ERROR", str(exc)) from exc
