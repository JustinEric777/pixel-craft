"""Fail-closed dispatch and resume logic for sampling queue records."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from .layout import CaptureLayout
from .sampling_queue import SamplingKind, SamplingQueueRecord
from .state_machine import CaptureJournal, CaptureStatus


@dataclass(frozen=True)
class QueueExecutionResult:
    record_id: str
    scan_order: int
    kind: str
    status: str
    capture_id: str
    error: str | None = None


QueueHandler = Callable[[SamplingQueueRecord, CaptureLayout], None]


class SamplingQueueRunner:
    def __init__(
        self,
        capture_root: Path,
        handlers: dict[SamplingKind, QueueHandler],
    ) -> None:
        missing = sorted(kind.value for kind in SamplingKind if kind not in handlers)
        if missing:
            raise ValueError(f"sampling queue handlers are missing: {', '.join(missing)}")
        self.capture_root = capture_root
        self.handlers = handlers

    def run(
        self,
        records: tuple[SamplingQueueRecord, ...],
        *,
        resume: bool,
    ) -> dict[str, object]:
        results = [self._run_record(record, resume=resume) for record in records]
        statuses = Counter(result.status for result in results)
        return {
            "attempted": statuses.get("ready", 0) + statuses.get("failed", 0),
            "ready": statuses.get("ready", 0),
            "failed": statuses.get("failed", 0),
            "skipped": statuses.get("skipped", 0),
            "results": [asdict(result) for result in results],
        }

    def _run_record(
        self,
        record: SamplingQueueRecord,
        *,
        resume: bool,
    ) -> QueueExecutionResult:
        layout = CaptureLayout(self.capture_root, record.capture_id)
        journal = CaptureJournal(layout)
        current = journal.read()
        if resume and current.get("status") == CaptureStatus.READY:
            return self._result(record, "skipped")
        try:
            record.verify_inputs()
            if current.get("active_attempt_id"):
                journal.fail(
                    "previous capture process stopped before the attempt became terminal",
                    recovered=True,
                    queue_record_id=record.record_id,
                    scan_order=record.scan_order,
                    kind=record.kind.value,
                )
            journal.begin_attempt(
                queue_record_id=record.record_id,
                semantic_key=record.semantic_key,
                scan_order=record.scan_order,
                kind=record.kind.value,
                page=record.page,
                section=record.section,
            )
            self.handlers[record.kind](record, layout)
            state = journal.read()
            if state.get("status") != CaptureStatus.READY:
                raise RuntimeError(
                    f"{record.record_id} handler did not finalize ready evidence"
                )
            return self._result(record, "ready")
        except Exception as exc:  # noqa: BLE001 - native application boundary
            journal.fail(
                exc,
                queue_record_id=record.record_id,
                scan_order=record.scan_order,
                kind=record.kind.value,
            )
            return self._result(record, "failed", error=str(exc))

    @staticmethod
    def _result(
        record: SamplingQueueRecord,
        status: str,
        *,
        error: str | None = None,
    ) -> QueueExecutionResult:
        return QueueExecutionResult(
            record_id=record.record_id,
            scan_order=record.scan_order,
            kind=record.kind.value,
            status=status,
            capture_id=record.capture_id,
            error=error,
        )
