from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass
from typing import Any


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
            normalized[unicodedata.normalize("NFC", key)] = _normalize(inner)
        return normalized
    raise CanonicalizationError("CANON_FORBIDDEN_TYPE", f"unsupported type: {type(value)!r}")


def canonical_input(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "header": envelope["header"],
        "meta": envelope.get("meta", {}),
        "payload": envelope["payload"],
    }


def canonicalize_json(value: Any) -> bytes:
    normalized = _normalize(value)
    try:
        return json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError("CANON_ENCODING_ERROR", str(exc)) from exc
