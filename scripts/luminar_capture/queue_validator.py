"""Evidence validation for complete Luminar sampling queues."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from .layout import CaptureLayout
from .sampling_queue import SamplingKind, SamplingQueueRecord
from .state_machine import CaptureStatus


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _ui_paths(record: SamplingQueueRecord, ui_reference_root: Path) -> tuple[Path, ...]:
    width, height = record.payload["viewport"]
    screenshot = (
        ui_reference_root
        / f"{width}x{height}"
        / f"{record.payload['ui_state']}.png"
    )
    return screenshot, screenshot.with_suffix(".ax.json")


def _capture_paths(layout: CaptureLayout) -> tuple[Path, ...]:
    return (
        layout.metadata_path,
        layout.preview_path,
        layout.export_path,
        layout.before_path,
        layout.after_path,
        layout.before_ax_path,
        layout.after_ax_path,
    )


def _metadata_identity_errors(
    record: SamplingQueueRecord,
    metadata: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    if record.kind is SamplingKind.WORKFLOW:
        inputs = record.payload["inputs"]
        expected = {
            "case_id": record.capture_id,
            "capability_id": record.payload["capability_id"],
            "input_sha256": inputs[0]["sha256"],
            "parameters": {"inputs": inputs, "defaults": True},
            "asset_id": None,
            "asset_sha256": None,
        }
    else:
        case = record.to_capture_case()
        expected = {
            "case_id": record.capture_id,
            "capability_id": case.capability_id,
            "input_sha256": case.input_sha256,
            "parameters": case.parameters,
            "asset_id": case.asset_id,
            "asset_sha256": case.asset_sha256,
        }
    for field, value in expected.items():
        if metadata.get(field) != value:
            errors.append(f"metadata-{field.replace('_', '-')}-mismatch")
    return errors


def validate_record(
    record: SamplingQueueRecord,
    *,
    capture_root: Path,
    ui_reference_root: Path,
    expected_reference_id: str | None = None,
    expected_app: dict[str, str] | None = None,
) -> dict[str, object]:
    layout = CaptureLayout(capture_root, record.capture_id)
    state = (
        json.loads(layout.state_path.read_text(encoding="utf-8"))
        if layout.state_path.is_file()
        else {}
    )
    required = (
        _ui_paths(record, ui_reference_root)
        if record.kind is SamplingKind.UI
        else _capture_paths(layout)
    )
    missing = [str(path) for path in required if not path.is_file()]
    errors: list[str] = []
    if state.get("status") != CaptureStatus.READY:
        errors.append(f"state={state.get('status', 'missing')}")
    canonical = state.get("canonical") if isinstance(state.get("canonical"), dict) else {}
    semantic_key = canonical.get("semantic_key")
    if semantic_key is not None and semantic_key != record.semantic_key:
        errors.append("canonical-semantic-key-mismatch")
    if expected_reference_id is not None:
        recorded_reference = (
            canonical.get("reference_id")
            if record.kind is SamplingKind.UI
            else None
        )
        if recorded_reference is not None and recorded_reference != expected_reference_id:
            errors.append("canonical-reference-id-mismatch")
    if expected_app is not None and isinstance(canonical.get("app_version"), dict):
        for field, value in expected_app.items():
            if str(canonical["app_version"].get(field, "")) != str(value):
                errors.append(f"canonical-app-{field}-mismatch")
    if not missing and record.kind is SamplingKind.UI:
        screenshot, accessibility = required
        expected_ui = {
            "matrix_state_id": record.payload["matrix_state_id"],
            "matrix_fingerprint": record.payload["matrix_fingerprint"],
            "viewport": record.payload["viewport"],
        }
        for field, value in expected_ui.items():
            if canonical.get(field) != value:
                errors.append(f"canonical-{field.replace('_', '-')}-mismatch")
        for field, path in (
            ("screenshot_sha256", screenshot),
            ("accessibility_tree_sha256", accessibility),
        ):
            if canonical.get(field) != _sha256(path):
                errors.append(f"canonical-{field.replace('_', '-')}-mismatch")
        source = record.payload.get("input")
        if isinstance(source, dict) and canonical.get("fixture_hash") != source.get("sha256"):
            errors.append("canonical-fixture-hash-mismatch")
    if not missing and record.kind is not SamplingKind.UI:
        try:
            metadata = json.loads(layout.metadata_path.read_text(encoding="utf-8"))
            errors.extend(_metadata_identity_errors(record, metadata))
            if expected_reference_id is not None and metadata.get("reference_build") != expected_reference_id:
                errors.append("metadata-reference-build-mismatch")
            if expected_app is not None:
                metadata_app = metadata.get("app_version") or {}
                for field, value in expected_app.items():
                    if str(metadata_app.get(field, "")) != str(value):
                        errors.append(f"metadata-app-{field}-mismatch")
            evidence_sources = metadata.get("evidence_sources", {})
            if evidence_sources.get("preview") != "native-window-preview":
                errors.append("metadata-preview-evidence-not-native")
            if evidence_sources.get("export") != "native-export":
                errors.append("metadata-export-evidence-not-native")
            declared = metadata.get("sha256", {})
            for name, path in (
                ("preview", layout.preview_path),
                ("export", layout.export_path),
                ("ui_before", layout.before_path),
                ("ui_after", layout.after_path),
                ("ax_before", layout.before_ax_path),
                ("ax_after", layout.after_ax_path),
            ):
                if declared.get(name) != _sha256(path):
                    errors.append(f"metadata-sha256-mismatch:{name}")
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            errors.append(f"invalid-metadata:{type(exc).__name__}")
    status = "ready" if not missing and not errors else "pending"
    return {
        "id": record.record_id,
        "capture_id": record.capture_id,
        "scan_order": record.scan_order,
        "kind": record.kind.value,
        "status": status,
        "missing": missing,
        "errors": errors,
    }


def validate_queue(
    records: tuple[SamplingQueueRecord, ...],
    *,
    capture_root: Path,
    ui_reference_root: Path,
    expected_reference_id: str | None = None,
    expected_app: dict[str, str] | None = None,
) -> dict[str, object]:
    results = [
        validate_record(
            record,
            capture_root=capture_root,
            ui_reference_root=ui_reference_root,
            expected_reference_id=expected_reference_id,
            expected_app=expected_app,
        )
        for record in records
    ]
    by_kind: dict[str, dict[str, int]] = {}
    for kind in SamplingKind:
        selected = [item for item in results if item["kind"] == kind.value]
        statuses = Counter(str(item["status"]) for item in selected)
        by_kind[kind.value] = {
            "total": len(selected),
            "ready": statuses.get("ready", 0),
            "pending": statuses.get("pending", 0),
        }
    ready = sum(item["status"] == "ready" for item in results)
    return {
        "record_count": len(results),
        "ready": ready,
        "pending": len(results) - ready,
        "gate": "passed" if results and ready == len(results) else "blocked",
        "by_kind": by_kind,
        "records": results,
    }
