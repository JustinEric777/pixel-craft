from __future__ import annotations

import json
from pathlib import Path

from scripts.build_native_parameter_binding_audit import build_audit

ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_native_parameter_audit_covers_every_current_parameter_once() -> None:
    matrix = _json("configs/parity/core-ui-state-matrix.json")
    audit = build_audit(
        matrix=matrix,
        schema=_json("configs/capabilities/parameter-schema.json"),
        sampling_path=ROOT / "configs/luminar_sampling.yaml",
        ui_root=ROOT / "test_data/outputs/luminar-1.28.0-23071/ui/2880x1800",
    )
    expected = {
        item["id"]
        for item in matrix["records"]
        if item["kind"] == "tool-parameter-state"
    }

    assert audit["record_count"] == 74
    assert {item["matrix_state_id"] for item in audit["records"]} == expected
    assert sum(audit["counts"].values()) == 74
    assert audit["counts"] == {"supported": 74}
    assert audit["gate"] == "passed"


def test_native_parameter_audit_contains_no_non_native_tool_opacity() -> None:
    audit = build_audit(
        matrix=_json("configs/parity/core-ui-state-matrix.json"),
        schema=_json("configs/capabilities/parameter-schema.json"),
        sampling_path=ROOT / "configs/luminar_sampling.yaml",
        ui_root=ROOT / "test_data/outputs/luminar-1.28.0-23071/ui/2880x1800",
    )
    opacity = [item for item in audit["records"] if item["parameter"] == "opacity"]

    assert opacity == []
    assert "blocked-native-mismatch" not in audit["counts"]
    assert all(item["native"] is None for item in opacity)


def test_supported_native_parameters_have_exact_evidence_and_binding() -> None:
    audit = build_audit(
        matrix=_json("configs/parity/core-ui-state-matrix.json"),
        schema=_json("configs/capabilities/parameter-schema.json"),
        sampling_path=ROOT / "configs/luminar_sampling.yaml",
        ui_root=ROOT / "test_data/outputs/luminar-1.28.0-23071/ui/2880x1800",
    )
    supported = [item for item in audit["records"] if item["status"] == "supported"]

    assert supported
    assert all(item["native"] for item in supported)
    assert all(len(item["evidence"]["sha256"]) == 64 for item in supported)
    assert next(
        item for item in supported if item["matrix_state_id"] == "tool:denoise:parameter:denoise_level:modified"
    )["native"]["control_locator_id"] == "NSButton.Noiseless.Low"
    assert next(
        item for item in supported if item["matrix_state_id"] == "tool:denoise:parameter:luminosity:modified"
    )["native"]["control_locator_id"] == "Slider.MIPLDenoiseAIEffect.Luminosity Denoise.Slider"
    assert next(
        item for item in supported if item["matrix_state_id"] == "tool:deblur:parameter:face_enhancer_enabled:modified"
    )["native"]["control_locator_id"] == "NSButton.Supersharp.FaceEnhancer"
    crop_box = next(
        item
        for item in supported
        if item["matrix_state_id"] == "tool:crop_ai:parameter:crop_box:modified"
    )["native"]
    assert crop_box["kind"] == "crop-box"
    assert crop_box["drag"] == [0.0, 0.0, 0.1, 0.1]
    crop_ratio = next(
        item
        for item in supported
        if item["matrix_state_id"] == "tool:crop_ai:parameter:crop_ratio:modified"
    )["native"]
    assert crop_ratio == {
        "kind": "menu-choice",
        "control_locator_id": "NSButton.Crop.AspectRatio",
        "choice_title": "自由",
        "value": "free",
    }
