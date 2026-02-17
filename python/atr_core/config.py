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
    config_path = _resolve_config_path(path)
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text())
    atr = raw["atr"]
    return AppConfig(
        transport=TransportConfig(**atr["transport_grpc"]),
        immune=ImmuneConfig(
            ruleset_path=_resolve_data_path(atr["immune"]["ruleset_path"], config_path),
            quarantine_subject=atr["immune"]["quarantine_subject"],
        ),
        envelope=EnvelopeConfig(
            schema_path=_resolve_data_path(atr["envelope"]["schema_path"], config_path),
            max_payload_bytes=atr["envelope"]["max_payload_bytes"],
        ),
    )


def _resolve_config_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists():
        return candidate

    return _repo_root() / candidate


def _resolve_data_path(path: str, config_path: Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)

    in_config_dir = (config_path.parent / candidate).resolve()
    if in_config_dir.exists():
        return str(in_config_dir)

    in_repo_root = (_repo_root() / candidate).resolve()
    if in_repo_root.exists():
        return str(in_repo_root)

    return str(in_repo_root)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
