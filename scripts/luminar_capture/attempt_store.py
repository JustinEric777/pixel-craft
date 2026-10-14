"""Append-only attempt evidence for one Luminar capture case."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .layout import CaptureLayout


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


class CaptureAttemptStore:
    """Store per-attempt events and publish one immutable terminal summary."""

    def __init__(self, layout: CaptureLayout) -> None:
        self.layout = layout

    def append_event(self, attempt_id: str, event: dict[str, Any]) -> None:
        path = self.layout.attempt_event_log_path(attempt_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def finish(self, attempt_id: str, summary: dict[str, Any]) -> Path:
        path = self.layout.attempt_path(attempt_id)
        if path.exists():
            raise RuntimeError(f"capture attempt is already terminal: {attempt_id}")
        write_json_atomic(path, summary)
        return path
