"""Persistent state journal for resumable Luminar black-box captures."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .attempt_store import CaptureAttemptStore, write_json_atomic
from .layout import CaptureLayout


class CaptureStatus(StrEnum):
    PREPARING = "preparing"
    APP_READY = "app-ready"
    PHOTO_SELECTED = "photo-selected"
    BASELINE_VERIFIED = "baseline-verified"
    TOOL_OPENED = "tool-opened"
    DEFAULT_CAPTURED = "default-captured"
    EFFECT_APPLIED = "effect-applied"
    PREVIEW_STABLE = "preview-stable"
    AFTER_CAPTURED = "after-captured"
    EXPORTED = "exported"
    READY = "ready"
    FAILED = "failed"
    INVALID_EVIDENCE = "invalid-evidence"


class CaptureJournal:
    schema_version = 2

    def __init__(self, layout: CaptureLayout) -> None:
        self.layout = layout
        self.attempts = CaptureAttemptStore(layout)

    def read(self) -> dict[str, Any]:
        if not self.layout.state_path.is_file():
            return {}
        return json.loads(self.layout.state_path.read_text(encoding="utf-8"))

    def events(self, attempt_id: str | None = None) -> list[dict[str, Any]]:
        state = self.read()
        resolved = attempt_id or state.get("active_attempt_id") or (
            state.get("last_attempt") or {}
        ).get("attempt_id")
        if not resolved:
            return []
        path = self.layout.attempt_event_log_path(str(resolved))
        if not path.is_file():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
        return events

    def begin_attempt(self, **details: Any) -> dict[str, Any]:
        self.layout.prepare()
        now = datetime.now(UTC).isoformat()
        previous = self.read()
        previous_canonical = previous.get("canonical") or {}
        active_attempt_id = previous.get("active_attempt_id")
        if active_attempt_id:
            raise RuntimeError(f"capture attempt is already active: {active_attempt_id}")
        attempt_id = f"{now.replace(':', '').replace('-', '')}-{uuid4().hex[:8]}"
        attempt = {
            "attempt_id": attempt_id,
            "status": CaptureStatus.PREPARING,
            "started_at": now,
            "updated_at": now,
            **details,
        }
        payload = {
            "schema_version": self.schema_version,
            "case_id": self.layout.case_id,
            "status": (
                CaptureStatus.READY
                if previous_canonical.get("status") == CaptureStatus.READY
                else CaptureStatus.PREPARING
            ),
            "updated_at": now,
            "canonical": previous.get("canonical"),
            "last_attempt": attempt,
            "active_attempt_id": attempt_id,
        }
        write_json_atomic(self.layout.state_path, payload)
        event = {"case_id": self.layout.case_id, **attempt}
        self._append_event(attempt_id, event)
        return payload

    def transition(self, status: CaptureStatus | str, **details: Any) -> dict[str, Any]:
        self.layout.prepare()
        now_value = datetime.now(UTC)
        now = now_value.isoformat()
        previous = self.read()
        if not previous.get("active_attempt_id"):
            previous = self.begin_attempt()
        attempt_id = str(previous["active_attempt_id"])
        previous_attempt = dict(previous.get("last_attempt") or {})
        previous_updated_at = previous_attempt.get("updated_at")
        started_at = previous_attempt.get("started_at")

        def elapsed_ms(value: Any) -> float | None:
            if not isinstance(value, str) or not value:
                return None
            try:
                return round(
                    max(0.0, (now_value - datetime.fromisoformat(value)).total_seconds())
                    * 1000.0,
                    3,
                )
            except ValueError:
                return None

        event = {
            "case_id": self.layout.case_id,
            "attempt_id": attempt_id,
            "status": str(status),
            "updated_at": now,
            **details,
            "stage_duration_ms": elapsed_ms(previous_updated_at),
            "attempt_duration_ms": elapsed_ms(started_at),
        }
        attempt = {
            **previous_attempt,
            **{key: value for key, value in event.items() if key != "case_id"},
        }
        canonical = previous.get("canonical")
        terminal = str(status) in {CaptureStatus.READY, CaptureStatus.FAILED}
        if str(status) == CaptureStatus.READY:
            identity = {
                key: previous_attempt[key]
                for key in (
                    "queue_record_id",
                    "semantic_key",
                    "kind",
                    "page",
                    "section",
                )
                if previous_attempt.get(key) is not None
            }
            canonical = {
                "status": CaptureStatus.READY,
                "attempt_id": attempt_id,
                "published_at": now,
                **identity,
                **details,
            }
        payload = {
            "schema_version": self.schema_version,
            "case_id": self.layout.case_id,
            "status": CaptureStatus.READY if canonical else str(status),
            "updated_at": now,
            "canonical": canonical,
            "last_attempt": attempt,
            "active_attempt_id": None if terminal else attempt_id,
        }
        write_json_atomic(self.layout.state_path, payload)
        self._append_event(attempt_id, event)
        if terminal:
            self.attempts.finish(
                attempt_id,
                {
                    "schema_version": self.schema_version,
                    "case_id": self.layout.case_id,
                    **attempt,
                },
            )
        return payload

    def _append_event(self, attempt_id: str, event: dict[str, Any]) -> None:
        self.attempts.append_event(attempt_id, event)
        with self.layout.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def fail(self, error: BaseException | str, **details: Any) -> dict[str, Any]:
        message = str(error)
        error_type = type(error).__name__ if isinstance(error, BaseException) else "Error"
        return self.transition(
            CaptureStatus.FAILED,
            error_type=error_type,
            error=message,
            **details,
        )

    def invalidate_evidence(self, **details: Any) -> dict[str, Any]:
        """Revoke published evidence while retaining the previous canonical audit."""

        self.layout.prepare()
        now = datetime.now(UTC).isoformat()
        previous = self.read()
        active_attempt_id = previous.get("active_attempt_id")
        if active_attempt_id:
            previous_attempt = dict(previous.get("last_attempt") or {})
            if previous_attempt.get("status") != CaptureStatus.INVALID_EVIDENCE:
                raise RuntimeError(
                    "cannot invalidate evidence during an active capture attempt"
                )
            self.attempts.finish(
                str(active_attempt_id),
                {
                    "schema_version": self.schema_version,
                    "case_id": self.layout.case_id,
                    **previous_attempt,
                },
            )
        attempt_id = f"{now.replace(':', '').replace('-', '')}-{uuid4().hex[:8]}"
        event = {
            "case_id": self.layout.case_id,
            "attempt_id": attempt_id,
            "status": CaptureStatus.INVALID_EVIDENCE,
            "started_at": now,
            "updated_at": now,
            **details,
        }
        payload = {
            "schema_version": self.schema_version,
            "case_id": self.layout.case_id,
            "status": CaptureStatus.INVALID_EVIDENCE,
            "updated_at": now,
            "canonical": None,
            "invalidated_canonical": previous.get("canonical"),
            "last_attempt": {
                key: value for key, value in event.items() if key != "case_id"
            },
            "active_attempt_id": None,
        }
        write_json_atomic(self.layout.state_path, payload)
        self._append_event(attempt_id, event)
        self.attempts.finish(
            attempt_id,
            {
                "schema_version": self.schema_version,
                **event,
            },
        )
        return payload
