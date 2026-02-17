#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def apply_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    payload = event.get("payload", {})
    op = payload.get("op")
    key = payload.get("key")

    if op == "set":
        state[key] = payload.get("value")
    elif op == "delete":
        state.pop(key, None)
    elif op == "incr":
        state[key] = int(state.get(key, 0)) + int(payload.get("value", 0))


def rebuild_snapshot(events: list[dict[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for event in events:
        apply_event(state, event)
    return state


def canonical_snapshot_hash(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.blake2b(canonical, digest_size=32).hexdigest()


def load_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove deterministic snapshot rebuild from immutable event log")
    parser.add_argument("event_log", type=Path, help="JSONL immutable event log")
    parser.add_argument("--runs", type=int, default=100)
    args = parser.parse_args()

    events = load_events(args.event_log)
    hashes = {canonical_snapshot_hash(rebuild_snapshot(events)) for _ in range(args.runs)}
    if len(hashes) != 1:
        print("non-deterministic rebuild detected")
        return 1

    stable_hash = next(iter(hashes))
    print(f"deterministic: runs={args.runs} snapshot_hash={stable_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
