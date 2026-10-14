import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.audit_sampling_effect_changes import audit_record
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingQueueRecord
from scripts.luminar_capture.state_machine import CaptureJournal, CaptureStatus


def _record(source: Path, *, amount: float | None = None) -> SamplingQueueRecord:
    parameter_binding = (
        {"parameter": "amount", "value": amount, "value_space": "normalized-signed"}
        if amount is not None
        else None
    )
    return SamplingQueueRecord.from_payload(
        {
            "id": "effect:case",
            "kind": "effect",
            "case_id": "case",
            "capability_id": "ai_enhance",
            "input": {
                "path": str(source),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            "locator_id": "tool",
            "strategy": "primary_slider",
            "page": "edit",
            "section": "tools",
            "scan_order": 1,
            "parameter_binding": parameter_binding,
        }
    )


def test_audit_rejects_unchanged_export_and_accepts_local_change(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (100, 100), (10, 20, 30)).save(source)
    record = _record(source)
    capture_root = tmp_path / "captures"
    layout = CaptureLayout(capture_root, record.capture_id)
    layout.prepare()
    Image.open(source).save(layout.export_path)
    layout.metadata_path.write_text(
        json.dumps({"input_path": str(source)}), encoding="utf-8"
    )

    invalid = audit_record(
        record,
        capture_root=capture_root,
        mae_min=0.01,
        pixel_delta=0.04,
        pixel_fraction_min=0.001,
    )
    changed = Image.open(source)
    for x in range(10):
        for y in range(10):
            changed.putpixel((x, y), (255, 255, 255))
    changed.save(layout.export_path)
    ready = audit_record(
        record,
        capture_root=capture_root,
        mae_min=0.01,
        pixel_delta=0.04,
        pixel_fraction_min=0.001,
    )

    assert invalid["status"] == "invalid-unchanged-export"
    assert ready["status"] == "ready"


def test_audit_allows_neutral_anchor_unless_recipe_requires_change(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(source)
    record = _record(source, amount=0.0)
    capture_root = tmp_path / "captures"
    layout = CaptureLayout(capture_root, record.capture_id)
    layout.prepare()
    Image.open(source).save(layout.export_path)
    layout.metadata_path.write_text(
        json.dumps({"input_path": str(source)}), encoding="utf-8"
    )

    neutral = audit_record(
        record,
        capture_root=capture_root,
        mae_min=0.01,
        pixel_delta=0.04,
        pixel_fraction_min=0.001,
    )
    forced = audit_record(
        record,
        capture_root=capture_root,
        mae_min=0.01,
        pixel_delta=0.04,
        pixel_fraction_min=0.001,
        force_render_change=True,
    )

    assert neutral["status"] == "valid-neutral-anchor"
    assert forced["status"] == "invalid-unchanged-export"


def test_invalidating_evidence_revokes_canonical_ready_state(tmp_path: Path) -> None:
    layout = CaptureLayout(tmp_path / "captures", "case")
    journal = CaptureJournal(layout)
    journal.begin_attempt()
    journal.transition(CaptureStatus.READY, output="old.png")

    invalidated = journal.invalidate_evidence(metrics={"mae": 0.0})

    assert invalidated["status"] == CaptureStatus.INVALID_EVIDENCE
    assert invalidated["canonical"] is None
    assert invalidated["invalidated_canonical"]["status"] == CaptureStatus.READY
    assert invalidated["active_attempt_id"] is None
