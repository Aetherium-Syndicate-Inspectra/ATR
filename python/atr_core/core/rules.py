from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Ruleset:
    def __init__(self, path: str) -> None:
        self._raw = json.loads(Path(path).read_text())

    def validate(self, envelope: dict[str, Any]) -> tuple[bool, str]:
        event_type = envelope["header"]["type"]
        blocked = set(self._raw.get("blocked_types", []))
        if event_type in blocked:
            return False, "blocked event type"

        required = self._raw.get("required_security_level_for_types", {})
        expected_level = required.get(event_type)
        if expected_level is None:
            return True, ""
        actual_level = envelope.get("meta", {}).get("security_level")
        if actual_level != expected_level:
            return False, "security level mismatch"
        return True, ""
