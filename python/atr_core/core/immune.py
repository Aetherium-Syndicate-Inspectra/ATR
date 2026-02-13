from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from atr_core.core.canonicalization import (
    CanonicalizationError,
    canonical_input,
    canonicalize_json,
    legacy_canonicalization_code,
)
from atr_core.core.rules import Ruleset
from atr_core.core.security import canonical_hash, verify_signature


@dataclass(frozen=True)
class ImmuneResult:
    accepted: bool
    reason: str
    canonical_envelope: bytes


class ImmunePipeline:
    def __init__(self, schema_path: str, ruleset_path: str) -> None:
        schema = json.loads(Path(schema_path).read_text())
        self._validator = Draft202012Validator(schema)
        self._ruleset = Ruleset(ruleset_path)

    def evaluate(self, envelope: dict[str, Any]) -> ImmuneResult:
        errors = sorted(self._validator.iter_errors(envelope), key=lambda e: e.path)
        if errors:
            return ImmuneResult(False, f"schema validation failed: {errors[0].message}", b"")

        try:
            canonical_bytes = canonicalize_json(canonical_input(envelope))
        except CanonicalizationError as err:
            legacy_code = legacy_canonicalization_code(err.code)
            if legacy_code == err.code:
                return ImmuneResult(False, f"canonicalization failed: {err.code}", b"")
            return ImmuneResult(
                False,
                f"canonicalization failed: {err.code} (legacy: {legacy_code})",
                b"",
            )

        digest = canonical_hash(canonical_bytes)
        signature_ok = verify_signature(
            source_agent=envelope["header"]["source_agent"],
            digest=digest,
            signature=envelope["signature"],
        )
        if not signature_ok:
            return ImmuneResult(False, "signature verification failed", canonical_bytes)

        rules_ok, reason = self._ruleset.validate(envelope)
        if not rules_ok:
            return ImmuneResult(False, f"ruleset validation failed: {reason}", canonical_bytes)

        return ImmuneResult(True, "", canonical_bytes)
