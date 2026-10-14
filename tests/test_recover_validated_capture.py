from pathlib import Path

import pytest
from PIL import Image

from scripts.recover_validated_capture import (
    validate_recovery_evidence,
    validate_state_authoritative_recovery,
)


def _image(path: Path, value: int) -> Path:
    Image.new("RGB", (16, 12), (value, value, value)).save(path)
    return path


def test_recovery_accepts_stable_bound_native_evidence(tmp_path: Path) -> None:
    baseline = _image(tmp_path / "baseline.png", 100)
    preview = _image(tmp_path / "preview.png", 101)
    exported = _image(tmp_path / "export.png", 101)
    binding = {"parameter": "amount", "value": -1.0, "value_space": "normalized-signed"}

    result = validate_recovery_evidence(
        attempt={"status": "failed", "parameter_binding": binding, "stable_samples": 3},
        parameter_binding=binding,
        baseline_preview=baseline,
        preview=preview,
        native_export=exported,
        screenshot_mae_max=0.002,
        change_pixel_delta_min=0.04,
        change_pixel_fraction_min=0.001,
        stable_samples=3,
        comparison_size=16,
        preview_export_rgb_mae_max=0.03,
        preview_export_luma_mae_max=0.02,
    )

    assert result["preview_change"]["mae"] > 0.002


def test_recovery_rejects_parameter_binding_mismatch(tmp_path: Path) -> None:
    image = _image(tmp_path / "same.png", 100)

    with pytest.raises(RuntimeError, match="parameter binding"):
        validate_recovery_evidence(
            attempt={"status": "failed", "parameter_binding": {}, "stable_samples": 3},
            parameter_binding={"parameter": "amount", "value": -1.0},
            baseline_preview=image,
            preview=image,
            native_export=image,
            screenshot_mae_max=0.002,
            change_pixel_delta_min=0.04,
            change_pixel_fraction_min=0.001,
            stable_samples=3,
            comparison_size=16,
            preview_export_rgb_mae_max=0.03,
            preview_export_luma_mae_max=0.02,
        )


def test_state_authoritative_recovery_accepts_changed_native_export(
    tmp_path: Path,
) -> None:
    source = _image(tmp_path / "source.png", 100)
    preview = _image(tmp_path / "preview.png", 100)
    exported = _image(tmp_path / "export.png", 130)

    result = validate_state_authoritative_recovery(
        attempt={
            "status": "failed",
            "stable_samples": 1,
            "edit_state": {"verified": True, "enabled": True},
        },
        source=source,
        preview=preview,
        native_export=exported,
        change_pixel_delta_min=0.04,
        export_source_mae_min=0.01,
        change_pixel_fraction_min=0.001,
    )

    assert result["export_change"]["mae"] > 0.01
    assert result["render_completion"] == "native-export-stable-file"
