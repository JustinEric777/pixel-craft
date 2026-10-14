from pathlib import Path

import pytest
import yaml

from configs.reference import load_reference_catalog


def _write_catalog(path: Path) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "active_reference": "current",
                "references": {
                    reference_id: {
                        "product": "Luminar Neo",
                        "version": version,
                        "build": build,
                        "bundle_id": "com.skylum.luminarneo",
                        "locale": "zh-Hans",
                        "platform": "macOS",
                        "cases_path": f"references/{reference_id}/cases.json",
                        "matrix_path": f"references/{reference_id}/matrix.json",
                        "manifest_path": f"references/{reference_id}/manifest.json",
                        "capture_root": f"references/{reference_id}/captures",
                        "ui_reference_root": f"references/{reference_id}/ui",
                        "observations_root": f"references/{reference_id}/observations",
                        "diagnostics_root": f"diagnostics/{reference_id}",
                        "exact_gate_enabled": reference_id == "current",
                    }
                    for reference_id, version, build in (
                        ("current", "1.25.1", "21065"),
                        ("retained", "1.26.0", "21267"),
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_reference_catalog_defaults_to_current_and_retains_old(tmp_path: Path) -> None:
    catalog = load_reference_catalog(
        _write_catalog(tmp_path / "reference.yaml"), project_root=tmp_path
    )

    assert catalog.resolve().version == "1.25.1"
    assert catalog.resolve("retained").version == "1.26.0"
    assert catalog.resolve().cases_path == tmp_path / "references/current/cases.json"


def test_reference_profile_rejects_wrong_application_build(tmp_path: Path) -> None:
    profile = load_reference_catalog(
        _write_catalog(tmp_path / "reference.yaml"), project_root=tmp_path
    ).resolve()

    with pytest.raises(RuntimeError, match="does not match reference"):
        profile.validate_app_version(
            {
                "version": "1.26.0",
                "build": "21267",
                "bundle_id": "com.skylum.luminarneo",
            }
        )


def test_reference_profile_accepts_exact_application_identity(tmp_path: Path) -> None:
    profile = load_reference_catalog(
        _write_catalog(tmp_path / "reference.yaml"), project_root=tmp_path
    ).resolve()

    profile.validate_app_version(
        {
            "version": "1.25.1",
            "build": "21065",
            "bundle_id": "com.skylum.luminarneo",
        }
    )
