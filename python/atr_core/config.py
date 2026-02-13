from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TransportConfig:
    target: str
    timeout_ms: int


@dataclass(frozen=True)
class ImmuneConfig:
    ruleset_path: str
    quarantine_subject: str


@dataclass(frozen=True)
class EnvelopeConfig:
    schema_path: str
    max_payload_bytes: int


@dataclass(frozen=True)
class AppConfig:
    transport: TransportConfig
    immune: ImmuneConfig
    envelope: EnvelopeConfig


def load_config(path: str = "configs/default.yaml") -> AppConfig:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    atr = raw["atr"]
    return AppConfig(
        transport=TransportConfig(**atr["transport_grpc"]),
        immune=ImmuneConfig(**atr["immune"]),
        envelope=EnvelopeConfig(
            schema_path=atr["envelope"]["schema_path"],
            max_payload_bytes=atr["envelope"]["max_payload_bytes"],
        ),
    )
