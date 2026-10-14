"""Yield native UI control while the local user is actively providing input."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class LocalInputGuard:
    required_idle_seconds: float = 5.0
    poll_seconds: float = 0.5
    synthetic_tolerance_seconds: float = 0.25

    def __post_init__(self) -> None:
        if self.required_idle_seconds < 0:
            raise ValueError("required idle seconds must not be negative")
        if self.poll_seconds <= 0:
            raise ValueError("idle poll seconds must be positive")
        self._last_automation_input_at: float | None = None
        self._wait_count = 0
        self._wait_seconds = 0.0
        self._last_reason: str | None = None

    def note_automation_input(self) -> None:
        self._last_automation_input_at = time.monotonic()

    def wait(
        self,
        idle_probe: Callable[[], float],
        *,
        reason: str,
    ) -> None:
        started_at: float | None = None
        while self._local_user_is_active(idle_probe()):
            if started_at is None:
                started_at = time.monotonic()
                self._wait_count += 1
                self._last_reason = reason
            time.sleep(self.poll_seconds)
        if started_at is not None:
            self._wait_seconds += time.monotonic() - started_at

    def _local_user_is_active(self, hid_idle_seconds: float) -> bool:
        if hid_idle_seconds < 0:
            raise ValueError("HID idle seconds must not be negative")
        if hid_idle_seconds >= self.required_idle_seconds:
            return False
        if self._last_automation_input_at is None:
            return True
        automation_age = time.monotonic() - self._last_automation_input_at
        return hid_idle_seconds + self.synthetic_tolerance_seconds < automation_age

    def report(self) -> dict[str, object]:
        return {
            "mode": "low-interference",
            "required_idle_seconds": self.required_idle_seconds,
            "poll_seconds": self.poll_seconds,
            "wait_count": self._wait_count,
            "wait_seconds": round(self._wait_seconds, 3),
            "last_wait_reason": self._last_reason,
        }
