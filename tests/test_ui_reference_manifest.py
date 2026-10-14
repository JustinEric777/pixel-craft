from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from scripts.validate_ui_references import run

UI_MATRIX = {
    "reference_id": "reference",
    "matrix_fingerprint": "c" * 64,
    "records": [{"id": "edit"}],
}


def test_ui_reference_manifest_is_required_by_strict_execution(tmp_path: Path) -> None:
    config = tmp_path / "parity.yaml"
    config.write_text(
        "capture:\n  ui_viewports: [[4, 3]]\n  ui_states: [edit]\n"
        "thresholds:\n  ui:\n    mae_max: 0.0\n    changed_pixel_ratio_max: 0.0\n",
        encoding="utf-8",
    )
    references = tmp_path / "references" / "4x3"
    candidates = tmp_path / "candidates" / "4x3"
    references.mkdir(parents=True)
    candidates.mkdir(parents=True)
    Image.new("RGB", (4, 3), (10, 20, 30)).save(references / "edit.png")
    Image.new("RGB", (4, 3), (10, 20, 30)).save(candidates / "edit.png")
    invalid = {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "records": [
            {
                "matrix_state_id": "edit",
                "viewport": [4, 3],
                "status": "invalid-evidence",
                "issues": ["app-version-missing-or-mismatch"],
            }
        ],
    }

    report = run(
        config,
        tmp_path / "references",
        tmp_path / "candidates",
        ui_matrix=UI_MATRIX,
        reference_manifest=json.loads(json.dumps(invalid)),
        reference_id="reference",
    )

    assert report["gate"] == "blocked"
    assert report["reference_manifest_gate"] == "blocked"
    assert report["passed"] == 0


def test_verified_ui_reference_manifest_allows_pixel_gate(tmp_path: Path) -> None:
    config = tmp_path / "parity.yaml"
    config.write_text(
        "capture:\n  ui_viewports: [[4, 3]]\n  ui_states: [edit]\n"
        "thresholds:\n  ui:\n    mae_max: 0.0\n    changed_pixel_ratio_max: 0.0\n",
        encoding="utf-8",
    )
    references = tmp_path / "references" / "4x3"
    candidates = tmp_path / "candidates" / "4x3"
    references.mkdir(parents=True)
    candidates.mkdir(parents=True)
    Image.new("RGB", (4, 3), (10, 20, 30)).save(references / "edit.png")
    Image.new("RGB", (4, 3), (10, 20, 30)).save(candidates / "edit.png")
    manifest = {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "records": [
            {
                "matrix_state_id": "edit",
                "viewport": [4, 3],
                "status": "verified",
                "issues": [],
            }
        ],
    }

    report = run(
        config,
        tmp_path / "references",
        tmp_path / "candidates",
        ui_matrix=UI_MATRIX,
        reference_manifest=manifest,
        reference_id="reference",
    )

    assert report["gate"] == "passed"
    assert report["passed"] == 1


def test_semantic_ui_state_is_delegated_to_interaction_gate(tmp_path: Path) -> None:
    config = tmp_path / "parity.yaml"
    config.write_text(
        "capture:\n  ui_viewports: [[4, 3]]\n"
        "thresholds:\n  ui:\n    mae_max: 0.0\n    changed_pixel_ratio_max: 0.0\n",
        encoding="utf-8",
    )
    matrix = {
        "reference_id": "reference",
        "matrix_fingerprint": "d" * 64,
        "records": [
            {
                "id": "export-dialog",
                "surface_owner": "os",
                "comparison_mode": "semantic",
            }
        ],
    }
    manifest = {
        "reference_id": "reference",
        "matrix_fingerprint": "d" * 64,
        "records": [
            {
                "matrix_state_id": "export-dialog",
                "viewport": [4, 3],
                "status": "verified",
                "issues": [],
            }
        ],
    }

    report = run(
        config,
        tmp_path / "references",
        tmp_path / "candidates",
        ui_matrix=matrix,
        reference_manifest=manifest,
        reference_id="reference",
    )

    assert report["gate"] == "passed"
    assert report["pixel_case_count"] == 0
    assert report["semantic_case_count"] == 1
    assert report["semantic_delegated"] == 1
    assert report["records"][0]["delegated_gate"] == "interaction-execution"


def test_multiple_viewports_do_not_duplicate_matrix_states(tmp_path: Path) -> None:
    config = tmp_path / "parity.yaml"
    config.write_text(
        "capture:\n  ui_viewports: [[4, 3], [8, 6]]\n"
        "thresholds:\n  ui:\n    mae_max: 0.0\n    changed_pixel_ratio_max: 0.0\n",
        encoding="utf-8",
    )
    matrix = {
        "reference_id": "reference",
        "matrix_fingerprint": "e" * 64,
        "records": [
            {
                "id": "export-dialog",
                "surface_owner": "os",
                "comparison_mode": "semantic",
            }
        ],
    }
    manifest = {
        "reference_id": "reference",
        "matrix_fingerprint": "e" * 64,
        "records": [
            {
                "matrix_state_id": "export-dialog",
                "viewport": viewport,
                "status": "verified",
                "issues": [],
            }
            for viewport in ([4, 3], [8, 6])
        ],
    }

    report = run(
        config,
        tmp_path / "references",
        tmp_path / "candidates",
        ui_matrix=matrix,
        reference_manifest=manifest,
        reference_id="reference",
    )

    assert report["case_count"] == 2
    assert report["semantic_case_count"] == 2
    assert len(report["records"]) == 2
