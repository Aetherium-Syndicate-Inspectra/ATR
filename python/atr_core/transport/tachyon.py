from __future__ import annotations

from dataclasses import dataclass


try:
    from tachyon_core import submit_packet as _submit_packet
except ImportError:  # pragma: no cover - optional native path
    _submit_packet = None


@dataclass(frozen=True)
class PacketSubmitResult:
    accepted: bool
    queue_depth: int
    error: str = ""


def submit_packet(event_id_hi: int, event_id_lo: int, sequence: int, unix_ns: int, payload: bytes, flags: int) -> PacketSubmitResult:
    if _submit_packet is None:
        return PacketSubmitResult(False, 0, "tachyon_core extension not available")

    queue_depth = _submit_packet(event_id_hi, event_id_lo, sequence, unix_ns, payload, flags)
    return PacketSubmitResult(True, queue_depth)
