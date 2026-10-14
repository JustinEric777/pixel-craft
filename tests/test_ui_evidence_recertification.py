from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingQueue, SamplingQueueRecord
from scripts.recertify_current_ui_evidence import recertify


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_recertify_rebinds_only_verified_current_build_evidence(tmp_path: Path) -> None:
    predecessor = "a" * 64
    current = "b" * 64
    record = SamplingQueueRecord.from_payload({
        "id": "ui:workspace:catalog",
        "scan_order": 1,
        "kind": "ui",
        "page": "catalog",
        "section": "page-state",
        "viewport": [16, 12],
        "ui_state": "workspace:catalog",
        "matrix_state_id": "workspace:catalog",
        "matrix_fingerprint": current,
        "matrix_kind": "workspace-state",
        "workspace_state": "catalog",
    })
    queue = SamplingQueue(reference_id="reference", records=(record,))
    ui_dir = tmp_path / "ui" / "16x12"
    ui_dir.mkdir(parents=True)
    screenshot = ui_dir / "workspace:catalog.png"
    Image.new("RGB", (16, 12), (10, 20, 30)).save(screenshot)
    ax = screenshot.with_suffix(".ax.json")
    ax.write_text('{"nodes": []}\n', encoding="utf-8")
    layout = CaptureLayout(tmp_path / "captures", record.capture_id)
    layout.prepare()
    layout.state_path.write_text(json.dumps({
        "schema_version": 2,
        "case_id": record.capture_id,
        "status": "ready",
        "canonical": {
            "status": "ready",
            "reference_id": "reference",
            "app_version": {"version": "1", "build": "2", "bundle_id": "app"},
            "matrix_state_id": "workspace:catalog",
            "ui_state": "workspace:catalog",
            "matrix_fingerprint": predecessor,
            "viewport": [16, 12],
            "screenshot_sha256": _sha(screenshot),
            "accessibility_tree_sha256": _sha(ax),
        },
        "last_attempt": {"attempt_id": "immutable"},
    }), encoding="utf-8")

    report = recertify(
        queue,
        capture_root=tmp_path / "captures",
        ui_reference_root=tmp_path / "ui",
        predecessor_fingerprint=predecessor,
        expected_app={"version": "1", "build": "2", "bundle_id": "app"},
    )

    state = json.loads(layout.state_path.read_text(encoding="utf-8"))
    assert report["counts"]["recertified"] == 1
    assert state["canonical"]["matrix_fingerprint"] == current
    assert state["canonical"]["semantic_key"] == record.semantic_key
    assert state["last_attempt"] == {"attempt_id": "immutable"}


def test_recertify_refuses_modified_artifact(tmp_path: Path) -> None:
    predecessor = "a" * 64
    record = SamplingQueueRecord.from_payload({
        "id": "ui:workspace:catalog",
        "scan_order": 1,
        "kind": "ui",
        "page": "catalog",
        "section": "page-state",
        "viewport": [16, 12],
        "ui_state": "workspace:catalog",
        "matrix_state_id": "workspace:catalog",
        "matrix_fingerprint": "b" * 64,
        "matrix_kind": "workspace-state",
        "workspace_state": "catalog",
    })
    queue = SamplingQueue(reference_id="reference", records=(record,))
    ui_dir = tmp_path / "ui" / "16x12"
    ui_dir.mkdir(parents=True)
    screenshot = ui_dir / "workspace:catalog.png"
    Image.new("RGB", (16, 12)).save(screenshot)
    ax = screenshot.with_suffix(".ax.json")
    ax.write_text("{}", encoding="utf-8")
    layout = CaptureLayout(tmp_path / "captures", record.capture_id)
    layout.prepare()
    layout.state_path.write_text(json.dumps({
        "status": "ready",
        "canonical": {
            "status": "ready",
            "reference_id": "reference",
            "app_version": {"version": "1", "build": "2", "bundle_id": "app"},
            "matrix_state_id": "workspace:catalog",
            "ui_state": "workspace:catalog",
            "matrix_fingerprint": predecessor,
            "viewport": [16, 12],
            "screenshot_sha256": "0" * 64,
            "accessibility_tree_sha256": _sha(ax),
        },
    }), encoding="utf-8")

    report = recertify(
        queue,
        capture_root=tmp_path / "captures",
        ui_reference_root=tmp_path / "ui",
        predecessor_fingerprint=predecessor,
        expected_app={"version": "1", "build": "2", "bundle_id": "app"},
    )

    assert report["counts"]["refused"] == 1
    assert json.loads(layout.state_path.read_text())["canonical"]["matrix_fingerprint"] == predecessor
