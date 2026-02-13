from __future__ import annotations

from dataclasses import dataclass
import sys
import types

import pytest
from fastapi import HTTPException


fake_transport_client = types.ModuleType("atr_core.transport.client")


class AtrTransportClient:  # pragma: no cover - import shim only
    def __init__(self, target: str, timeout_ms: int) -> None:  # noqa: ARG002
        pass

    def publish(self, canonical_envelope: bytes, subject: str, correlation_id: str = ""):  # noqa: ANN201,ARG002
        raise NotImplementedError


fake_transport_client.AtrTransportClient = AtrTransportClient
sys.modules.setdefault("atr_core.transport.client", fake_transport_client)

from atr_core.api import app as app_module
from atr_core.core.immune import ImmuneResult


@dataclass
class Ack:
    accepted: bool
    error_message: str = ""
    stream_sequence: int = 0


@dataclass
class StubImmune:
    result: ImmuneResult

    def evaluate(self, envelope: dict) -> ImmuneResult:
        return self.result


@dataclass
class StubTransport:
    ack: Ack

    def publish(self, canonical_envelope: bytes, subject: str, correlation_id: str = "") -> Ack:  # noqa: ARG002
        return self.ack


def test_submit_returns_503_when_quarantine_publish_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "immune",
        StubImmune(ImmuneResult(False, "signature verification failed", b'{"header":{"id":"x"}}')),
    )
    monkeypatch.setattr(app_module, "transport", StubTransport(Ack(False, "quarantine publish failed")))

    with pytest.raises(HTTPException) as exc:
        app_module.submit_envelope({"meta": {}, "header": {"type": "state.mutation"}})

    assert exc.value.status_code == 503
    assert exc.value.detail == "quarantine publish failed"


def test_submit_returns_403_when_signature_fails_and_quarantine_publish_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "immune",
        StubImmune(ImmuneResult(False, "signature verification failed", b'{"header":{"id":"x"}}')),
    )
    monkeypatch.setattr(app_module, "transport", StubTransport(Ack(True)))

    with pytest.raises(HTTPException) as exc:
        app_module.submit_envelope({"meta": {}, "header": {"type": "state.mutation"}})

    assert exc.value.status_code == 403
    assert exc.value.detail == "signature verification failed"


def test_submit_returns_400_when_schema_fails_and_quarantine_publish_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "immune",
        StubImmune(ImmuneResult(False, "schema validation failed: missing property", b"")),
    )
    monkeypatch.setattr(app_module, "transport", StubTransport(Ack(True)))

    with pytest.raises(HTTPException) as exc:
        app_module.submit_envelope({"meta": {}, "header": {"type": "state.mutation"}})

    assert exc.value.status_code == 400
    assert exc.value.detail == "schema validation failed: missing property"
