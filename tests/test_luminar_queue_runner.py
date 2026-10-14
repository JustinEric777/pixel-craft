import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.queue_runner import SamplingQueueRunner
from scripts.luminar_capture.sampling_queue import (
    SamplingKind,
    SamplingQueue,
    SamplingQueueRecord,
)
from scripts.luminar_capture.state_machine import CaptureJournal, CaptureStatus
from scripts.run_luminar_sampling_queue import (
    _one_record_per_kind,
    _pending_records,
    _selection_summary,
)


def _input(path: Path) -> dict[str, str]:
    Image.new("RGB", (8, 6), (10, 20, 30)).save(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _records(tmp_path: Path) -> list[dict]:
    source = _input(tmp_path / "source.png")
    asset = _input(tmp_path / "asset.png")
    kinds = ["ui", "effect", "preset", "sky", "overlay", "workflow"]
    base = [
        {
            "id": "ui:catalog",
            "kind": "ui",
            "viewport": [1440, 900],
            "ui_state": "catalog",
            "matrix_state_id": "catalog",
            "matrix_fingerprint": "a" * 64,
            "matrix_kind": "workspace-state",
            "workspace_state": "catalog",
            "page": "catalog",
            "section": "page-state",
        },
        {
            "id": "effect:case",
            "kind": "effect",
            "case_id": "case",
            "capability_id": "ai_enhance",
            "locator_id": "tool",
            "input": source,
            "parameters": {"amount": 0.5},
            "page": "edit",
            "section": "tools",
            "strategy": "primary_slider",
        },
        {
            "id": "preset:preset",
            "kind": "preset",
            "preset_id": "preset",
            "name": "Preset",
            "input": source,
            "page": "presets",
            "section": "preset-grid",
            "strategy": "preset",
        },
        {
            "id": "sky:asset",
            "kind": "sky",
            "asset_id": "asset.png",
            "asset_path": asset["path"],
            "asset_sha256": asset["sha256"],
            "input": source,
            "page": "edit",
            "section": "sky-picker",
            "strategy": "asset_picker",
        },
        {
            "id": "overlay:asset",
            "kind": "overlay",
            "asset_id": "asset.png",
            "asset_path": asset["path"],
            "asset_sha256": asset["sha256"],
            "input": source,
            "page": "edit",
            "section": "layer-library",
            "strategy": "asset_picker",
        },
        {
            "id": "workflow:hdr",
            "kind": "workflow",
            "capability_id": "hdr_merge",
            "inputs": [source, source],
            "page": "catalog",
            "section": "multi-image-tools",
            "strategy": "multi_image",
        },
    ]
    assert [item["kind"] for item in base] == kinds
    return [{**item, "scan_order": index} for index, item in enumerate(base, 1)]


def test_queue_loads_filters_and_preserves_scan_order(tmp_path: Path) -> None:
    records = _records(tmp_path)
    path = tmp_path / "queue.json"
    path.write_text(
        json.dumps(
            {
                "reference_id": "reference",
                "record_count": len(records),
                "records": records,
            }
        )
    )

    queue = SamplingQueue.load(path, expected_reference_id="reference")
    selected = queue.select(
        kinds={SamplingKind.PRESET, SamplingKind.SKY}, start_order=2
    )

    assert [record.kind for record in selected] == [
        SamplingKind.PRESET,
        SamplingKind.SKY,
    ]
    assert selected[0].to_capture_case().capability_id == "preset_apply"
    assert selected[1].to_capture_case().asset_id == "asset.png"


def test_runner_requires_all_handlers_and_resumes_ready_records(tmp_path: Path) -> None:
    records = tuple(SamplingQueueRecord.from_payload(item) for item in _records(tmp_path))
    called: list[str] = []

    def ready(record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        called.append(record.record_id)
        CaptureJournal(layout).transition(CaptureStatus.READY)

    handlers = {kind: ready for kind in SamplingKind}
    runner = SamplingQueueRunner(tmp_path / "captures", handlers)

    first = runner.run(records, resume=True)
    second = runner.run(records, resume=True)

    assert first["ready"] == 6
    assert first["failed"] == 0
    assert second["skipped"] == 6
    assert len(called) == 6


def test_runner_fails_when_handler_does_not_finalize_evidence(tmp_path: Path) -> None:
    record = SamplingQueueRecord.from_payload(_records(tmp_path)[0])

    def incomplete(record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        pass

    runner = SamplingQueueRunner(
        tmp_path / "captures", {kind: incomplete for kind in SamplingKind}
    )
    report = runner.run((record,), resume=False)

    assert report["failed"] == 1
    assert "did not finalize ready evidence" in report["results"][0]["error"]


def test_runner_recovers_interrupted_attempt_before_retry(tmp_path: Path) -> None:
    record = SamplingQueueRecord.from_payload(_records(tmp_path)[0])
    capture_root = tmp_path / "captures"
    layout = CaptureLayout(capture_root, record.capture_id)
    journal = CaptureJournal(layout)
    interrupted = journal.begin_attempt(queue_record_id=record.record_id)

    def ready(record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        CaptureJournal(layout).transition(CaptureStatus.READY)

    runner = SamplingQueueRunner(
        capture_root, {kind: ready for kind in SamplingKind}
    )
    report = runner.run((record,), resume=True)

    state = journal.read()
    terminal = layout.attempt_path(interrupted["active_attempt_id"])
    assert report["ready"] == 1
    assert state["status"] == CaptureStatus.READY
    assert state["active_attempt_id"] is None
    assert json.loads(terminal.read_text())["status"] == CaptureStatus.FAILED


def test_dry_run_summary_covers_all_six_kinds_without_native_driver(
    tmp_path: Path,
) -> None:
    records = tuple(
        SamplingQueueRecord.from_payload(item) for item in _records(tmp_path)
    )

    summary = _selection_summary(records)

    assert summary["record_count"] == 6
    assert summary["counts"] == {
        "effect": 1,
        "overlay": 1,
        "preset": 1,
        "sky": 1,
        "ui": 1,
        "workflow": 1,
    }


def test_one_record_per_kind_selects_six_kind_smoke_batch(tmp_path: Path) -> None:
    payloads = _records(tmp_path)
    payloads.insert(1, {**payloads[0], "id": "ui:catalog:second", "scan_order": 2})
    for index, payload in enumerate(payloads, 1):
        payload["scan_order"] = index
    records = tuple(SamplingQueueRecord.from_payload(item) for item in payloads)

    selected = _one_record_per_kind(records)

    assert [record.kind for record in selected] == list(SamplingKind)
    assert selected[0].record_id == "ui:catalog"


def test_capture_id_is_stable_when_scan_order_changes(tmp_path: Path) -> None:
    payload = _records(tmp_path)[0]
    first = SamplingQueueRecord.from_payload(payload)
    second = SamplingQueueRecord.from_payload({**payload, "scan_order": 99})

    assert first.capture_id == second.capture_id
    assert first.capture_id.startswith("queue-ui-")


def test_pending_records_filters_ready_before_batch_limit(tmp_path: Path) -> None:
    records = tuple(SamplingQueueRecord.from_payload(item) for item in _records(tmp_path))
    capture_root = tmp_path / "captures"
    ui_reference_root = tmp_path / "ui"
    first = records[0]
    screenshot = ui_reference_root / "1440x900" / "catalog.png"
    accessibility = screenshot.with_suffix(".ax.json")
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"screenshot")
    accessibility.write_bytes(b"accessibility")
    CaptureJournal(CaptureLayout(capture_root, first.capture_id)).transition(
        CaptureStatus.READY,
        reference_id="reference",
        app_version={
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
        matrix_state_id="catalog",
        matrix_fingerprint="a" * 64,
        viewport=[1440, 900],
        screenshot_sha256=hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        accessibility_tree_sha256=hashlib.sha256(accessibility.read_bytes()).hexdigest(),
    )

    pending, ready, failed, stale = _pending_records(
        records,
        capture_root,
        ui_reference_root,
        expected_reference_id="reference",
        expected_app={
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
        retry_failed=False,
    )

    assert ready == 1
    assert failed == 0
    assert stale == ()
    assert [record.record_id for record in pending[:2]] == [
        records[1].record_id,
        records[2].record_id,
    ]


def test_pending_records_only_retries_failed_when_requested(tmp_path: Path) -> None:
    records = tuple(SamplingQueueRecord.from_payload(item) for item in _records(tmp_path))
    capture_root = tmp_path / "captures"
    ui_reference_root = tmp_path / "ui"
    first = records[0]
    CaptureJournal(CaptureLayout(capture_root, first.capture_id)).transition(
        CaptureStatus.FAILED
    )

    pending, _, failed, _ = _pending_records(
        records,
        capture_root,
        ui_reference_root,
        expected_reference_id="reference",
        expected_app={
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
        retry_failed=False,
    )
    retried, _, retried_failed, _ = _pending_records(
        records,
        capture_root,
        ui_reference_root,
        expected_reference_id="reference",
        expected_app={
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
        retry_failed=True,
    )

    assert failed == 1
    assert first not in pending
    assert retried_failed == 0
    assert first in retried
