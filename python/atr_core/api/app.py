from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from atr_core.config import load_config
from atr_core.core.immune import ImmunePipeline
from atr_core.api.quarantine import serialize_for_quarantine
from atr_core.transport.client import AtrTransportClient

config = load_config()
immune = ImmunePipeline(config.envelope.schema_path, config.immune.ruleset_path)
transport = AtrTransportClient(config.transport.target, config.transport.timeout_ms)

app = FastAPI(title="ATR Core Server")



@app.post("/v1/submit", status_code=202)
def submit_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    result = immune.evaluate(envelope)
    correlation_id = envelope.get("meta", {}).get("correlation_id", "")

    if result.accepted:
        ack = transport.publish(
            canonical_envelope=result.canonical_envelope,
            subject=f"aether.stream.core.{envelope['header']['type']}",
            correlation_id=correlation_id,
        )
        if not ack.accepted:
            raise HTTPException(status_code=503, detail=ack.error_message or "publish rejected")
        return {"accepted": True, "stream_sequence": ack.stream_sequence}

    quarantine_bytes = serialize_for_quarantine(envelope, result.canonical_envelope)
    quarantine_ack = transport.publish(
        canonical_envelope=quarantine_bytes,
        subject=config.immune.quarantine_subject,
        correlation_id=correlation_id,
    )
    if not quarantine_ack.accepted:
        raise HTTPException(
            status_code=503,
            detail=quarantine_ack.error_message or "quarantine publish rejected",
        )

    status = 403 if "signature" in result.reason or "ruleset" in result.reason else 400
    raise HTTPException(status_code=status, detail=result.reason)


@app.get("/v1/state/{key}")
def query_state(key: str) -> dict[str, Any]:
    return {"key": key, "state": None, "status": "stub"}


@app.get("/v1/ledger/{event_id}")
def query_ledger(event_id: str) -> dict[str, Any]:
    return {"event_id": event_id, "entry": None, "status": "stub"}
