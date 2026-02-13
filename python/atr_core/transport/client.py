from __future__ import annotations

from dataclasses import dataclass

import grpc

from atr_core.proto import atr_transport_pb2 as pb2


@dataclass(frozen=True)
class PublishAck:
    accepted: bool
    persisted: bool
    stream_sequence: int
    error_code: str
    error_message: str


class AtrTransportClient:
    def __init__(self, target: str, timeout_ms: int) -> None:
        self._target = target
        self._timeout = timeout_ms / 1000.0

    def publish(
        self,
        canonical_envelope: bytes,
        subject: str,
        correlation_id: str = "",
        require_persisted_ack: bool = True,
    ) -> PublishAck:
        with grpc.insecure_channel(self._target) as channel:
            method = channel.unary_unary(
                "/atr.transport.v1.AtrTransport/Publish",
                request_serializer=pb2.PublishRequest.SerializeToString,
                response_deserializer=pb2.PublishResponse.FromString,
            )
            response = method(
                pb2.PublishRequest(
                    canonical_envelope=canonical_envelope,
                    subject=subject,
                    correlation_id=correlation_id,
                    require_persisted_ack=require_persisted_ack,
                ),
                timeout=self._timeout,
            )
            return PublishAck(
                accepted=response.accepted,
                persisted=response.persisted,
                stream_sequence=response.stream_sequence,
                error_code=response.error_code,
                error_message=response.error_message,
            )
