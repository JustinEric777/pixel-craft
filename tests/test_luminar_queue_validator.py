import hashlib
import json
from pathlib import Path

from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.queue_validator import validate_queue
from scripts.luminar_capture.sampling_queue import SamplingQueueRecord
from scripts.luminar_capture.state_machine import CaptureJournal, CaptureStatus


def _ui_record() -> SamplingQueueRecord:
    return SamplingQueueRecord.from_payload(
        {
            "id": "ui:1440x900:catalog",
            "kind": "ui",
            "viewport": [1440, 900],
            "ui_state": "catalog",
            "matrix_state_id": "catalog",
            "matrix_fingerprint": "a" * 64,
            "matrix_kind": "workspace-state",
            "workspace_state": "catalog",
            "status": "pending-reference",
            "page": "catalog",
            "section": "page-state",
            "scan_order": 1,
        }
    )


def test_queue_evidence_stays_blocked_until_ready_artifacts_exist(tmp_path: Path) -> None:
    record = _ui_record()
    capture_root = tmp_path / "captures"
    ui_root = tmp_path / "ui"

    pending = validate_queue(
        (record,), capture_root=capture_root, ui_reference_root=ui_root
    )

    assert pending["gate"] == "blocked"
    assert pending["ready"] == 0

    screenshot = ui_root / "1440x900/catalog.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"png")
    screenshot.with_suffix(".ax.json").write_text("{}", encoding="utf-8")
    journal = CaptureJournal(CaptureLayout(capture_root, record.capture_id))
    journal.begin_attempt(
        queue_record_id=record.record_id,
        semantic_key=record.semantic_key,
        kind=record.kind.value,
        page=record.page,
        section=record.section,
    )
    journal.transition(
        CaptureStatus.READY,
        screenshot=str(screenshot),
        matrix_state_id=record.payload["matrix_state_id"],
        matrix_fingerprint=record.payload["matrix_fingerprint"],
        viewport=record.payload["viewport"],
        screenshot_sha256=hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        accessibility_tree_sha256=hashlib.sha256(
            screenshot.with_suffix(".ax.json").read_bytes()
        ).hexdigest(),
    )

    ready = validate_queue(
        (record,), capture_root=capture_root, ui_reference_root=ui_root
    )

    assert ready["gate"] == "passed"
    assert ready["ready"] == 1
    assert json.dumps(ready)
