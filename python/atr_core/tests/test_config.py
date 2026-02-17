from __future__ import annotations

from pathlib import Path

from atr_core.config import load_config


def test_load_config_works_outside_repo_root(monkeypatch) -> None:
    monkeypatch.chdir("/")
    config = load_config()

    assert Path(config.envelope.schema_path).is_absolute()
    assert Path(config.envelope.schema_path).exists()
    assert Path(config.immune.ruleset_path).is_absolute()
    assert Path(config.immune.ruleset_path).exists()


def test_load_config_prefers_paths_near_config_file(tmp_path) -> None:
    schema_path = tmp_path / "schema.json"
    ruleset_path = tmp_path / "ruleset.json"
    schema_path.write_text("{}")
    ruleset_path.write_text("{}")

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
atr:
  transport_grpc:
    target: "unix:///tmp/atb_et.sock"
    timeout_ms: 2000
  envelope:
    schema_path: "schema.json"
    max_payload_bytes: 4096
  immune:
    ruleset_path: "ruleset.json"
    quarantine_subject: "aether.audit.violation"
""".strip()
    )

    config = load_config(str(config_file))

    assert Path(config.envelope.schema_path) == schema_path
    assert Path(config.immune.ruleset_path) == ruleset_path
