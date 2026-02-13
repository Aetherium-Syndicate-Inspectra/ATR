from __future__ import annotations

import base64
import json

from nacl.signing import SigningKey

from atr_core.core.canonicalization import canonical_input, canonicalize_json
from atr_core.core.immune import ImmunePipeline
from atr_core.core.security import canonical_hash, verify_signature


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _envelope(signing_key: SigningKey) -> dict:
    body = {
        "header": {
            "id": "018f9e53-6908-7b5f-bf2c-3f4a56d3f900",
            "timestamp": 1700000000000000000,
            "source_agent": signing_key.verify_key.encode().hex(),
            "type": "state.mutation",
            "version": "2.0.0",
        },
        "meta": {"security_level": "confidential", "correlation_id": "c1"},
        "payload": {"x": 1, "y": 2},
    }
    digest = canonical_hash(canonicalize_json(canonical_input(body)))
    sig = signing_key.sign(digest).signature
    body["signature"] = _b64u(sig)
    return body


def test_schema_validation() -> None:
    sk = SigningKey.generate()
    env = _envelope(sk)
    env["header"].pop("type")
    pipeline = ImmunePipeline("specs/envelope_schema.json", "configs/inspirafirma_ruleset.json")
    result = pipeline.evaluate(env)
    assert not result.accepted
    assert "schema validation failed" in result.reason


def test_canonicalization_determinism() -> None:
    a = {"b": 1, "a": {"d": 2, "c": 3}}
    b = {"a": {"c": 3, "d": 2}, "b": 1}
    assert canonicalize_json(a) == canonicalize_json(b)


def test_signature_verify_ed25519() -> None:
    sk = SigningKey.generate()
    env = _envelope(sk)
    digest = canonical_hash(canonicalize_json(canonical_input(env)))
    assert verify_signature(env["header"]["source_agent"], digest, env["signature"])


def test_quarantine_routing() -> None:
    sk = SigningKey.generate()
    env = _envelope(sk)
    env["signature"] = "invalid"
    pipeline = ImmunePipeline("specs/envelope_schema.json", "configs/inspirafirma_ruleset.json")
    result = pipeline.evaluate(env)
    assert not result.accepted
    assert "signature verification failed" in result.reason
    assert json.loads(result.canonical_envelope.decode())["header"]["id"] == env["header"]["id"]


def test_canonicalization_rejects_nan() -> None:
    pipeline = ImmunePipeline("specs/envelope_schema.json", "configs/inspirafirma_ruleset.json")
    sk = SigningKey.generate()
    env = _envelope(sk)
    env["payload"] = {"value": float("nan")}
    result = pipeline.evaluate(env)
    assert not result.accepted
    assert result.reason.endswith("CANON_INVALID_NUMBER")
