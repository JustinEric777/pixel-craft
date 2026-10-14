from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.validate_ui_execution_evidence import (
    frontend_build_hash,
    validate_execution_evidence,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    config = tmp_path / "parity.yaml"
    config.write_text(
        "capture:\n  ui_viewports: [[4, 3]]\n  ui_states: [edit]\n",
        encoding="utf-8",
    )
    matrix = tmp_path / "ui-matrix.json"
    matrix.write_text(
        json.dumps(
            {
                "reference_id": "reference",
                "matrix_fingerprint": "c" * 64,
                "records": [{"id": "edit"}],
            }
        ),
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "package.json").write_text('{"name":"fixture"}\n', encoding="utf-8")
    (frontend / "src/App.tsx").write_text("export default 1;\n", encoding="utf-8")
    execution_root = tmp_path / "diagnostics"
    candidate_root = execution_root / "ui-candidates"
    screenshot = candidate_root / "4x3/edit.png"
    screenshot.parent.mkdir(parents=True)
    Image.new("RGB", (4, 3), (20, 30, 40)).save(screenshot)
    source = execution_root / "ui-capture-raw/4x3/edit.png"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (4, 3), (20, 30, 40)).save(source)
    (source.parent / "edit.dom.json").write_text(
        json.dumps({"html": "<main />"}), encoding="utf-8"
    )
    (source.parent / "edit.ax.json").write_text(
        json.dumps({"role": "main"}), encoding="utf-8"
    )
    (execution_root / "fixture.json").write_text(
        json.dumps(
            {
                "collection": "fixture",
                "expected_count": 1,
                "catalog_count": 1,
                "unique_source_hash_count": 1,
                "fixture_fingerprint": "b" * 64,
                "records": [{"filename": "image.jpg", "source_sha256": "a" * 64}],
            }
        ),
        encoding="utf-8",
    )
    return config, matrix, frontend, execution_root, candidate_root


def _payload(frontend: Path, execution_root: Path, screenshot: Path) -> dict[str, object]:
    source = execution_root / "ui-capture-raw/4x3/edit.png"
    dom_snapshot = source.parent / "edit.dom.json"
    accessibility_tree = source.parent / "edit.ax.json"
    fixture = execution_root / "fixture.json"
    return {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "fixture": {
            "manifest": "fixture.json",
            "manifest_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "fixture_fingerprint": "b" * 64,
            "collection": "fixture",
            "expected_count": 1,
            "catalog_count": 1,
            "unique_source_hash_count": 1,
        },
        "environment": {
            "browser": "in-app",
            "browser_version": "1",
            "capture_engine": "Chrome Headless CDP",
            "logical_viewport": [4, 3],
            "physical_viewport": ["4x3"],
            "device_scale_factor": 1,
            "locale": "zh-Hans",
            "timezone": "Asia/Shanghai",
            "motion": "reduce",
            "build_hash": frontend_build_hash(frontend),
        },
        "records": [
            {
                "viewport": "4x3",
                "matrix_state_id": "edit",
                "fixture_id": "single-image",
                "fixture_hash": "a" * 64,
                "actual_fixture_fingerprint": "b" * 64,
                "screenshot": str(screenshot.relative_to(execution_root)),
                "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                "source_capture": str(source.relative_to(execution_root)),
                "source_capture_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "dom_snapshot": str(dom_snapshot.relative_to(execution_root)),
                "dom_snapshot_sha256": hashlib.sha256(
                    dom_snapshot.read_bytes()
                ).hexdigest(),
                "accessibility_tree": str(
                    accessibility_tree.relative_to(execution_root)
                ),
                "accessibility_tree_sha256": hashlib.sha256(
                    accessibility_tree.read_bytes()
                ).hexdigest(),
                "capture_method": "native-dpr2",
            }
        ],
    }


def test_ui_evidence_requires_current_build_fixture_and_screenshot(tmp_path: Path) -> None:
    config, matrix, frontend, execution_root, candidates = _fixture(tmp_path)
    screenshot = candidates / "4x3/edit.png"

    report = validate_execution_evidence(
        _payload(frontend, execution_root, screenshot),
        config_path=config,
        ui_matrix_path=matrix,
        candidate_root=candidates,
        frontend_root=frontend,
        execution_root=execution_root,
        reference_id="reference",
    )

    assert report["gate"] == "passed"
    assert report["passed"] == 1


def test_ui_evidence_rejects_stale_build_and_duplicate_state(tmp_path: Path) -> None:
    config, matrix, frontend, execution_root, candidates = _fixture(tmp_path)
    screenshot = candidates / "4x3/edit.png"
    payload = _payload(frontend, execution_root, screenshot)
    payload["environment"]["build_hash"] = "stale"  # type: ignore[index]
    payload["records"].append(dict(payload["records"][0]))  # type: ignore[union-attr,index]

    report = validate_execution_evidence(
        payload,
        config_path=config,
        ui_matrix_path=matrix,
        candidate_root=candidates,
        frontend_root=frontend,
        execution_root=execution_root,
        reference_id="reference",
    )

    assert report["gate"] == "blocked"
    assert {issue["id"] for issue in report["issues"]} >= {
        "stale-frontend-build",
        "duplicate-state",
    }


def test_ui_evidence_rejects_hash_mismatch(tmp_path: Path) -> None:
    config, matrix, frontend, execution_root, candidates = _fixture(tmp_path)
    screenshot = candidates / "4x3/edit.png"
    payload = json.loads(json.dumps(_payload(frontend, execution_root, screenshot)))
    payload["records"][0]["screenshot_sha256"] = "0" * 64

    report = validate_execution_evidence(
        payload,
        config_path=config,
        ui_matrix_path=matrix,
        candidate_root=candidates,
        frontend_root=frontend,
        execution_root=execution_root,
        reference_id="reference",
    )

    assert report["gate"] == "blocked"
    assert any(issue["id"] == "screenshot-hash-mismatch" for issue in report["issues"])


def test_ui_evidence_rejects_viewport_contract_mismatch(tmp_path: Path) -> None:
    config, matrix, frontend, execution_root, candidates = _fixture(tmp_path)
    screenshot = candidates / "4x3/edit.png"
    payload = _payload(frontend, execution_root, screenshot)
    payload["environment"]["device_scale_factor"] = 2  # type: ignore[index]

    report = validate_execution_evidence(
        payload,
        config_path=config,
        ui_matrix_path=matrix,
        candidate_root=candidates,
        frontend_root=frontend,
        execution_root=execution_root,
        reference_id="reference",
    )

    assert report["gate"] == "blocked"
    assert any(issue["id"] == "viewport-contract-mismatch" for issue in report["issues"])


def test_ui_evidence_requires_dom_and_accessibility_tree(tmp_path: Path) -> None:
    config, matrix, frontend, execution_root, candidates = _fixture(tmp_path)
    screenshot = candidates / "4x3/edit.png"
    payload = _payload(frontend, execution_root, screenshot)
    Path(execution_root / "ui-capture-raw/4x3/edit.dom.json").unlink()

    report = validate_execution_evidence(
        payload,
        config_path=config,
        ui_matrix_path=matrix,
        candidate_root=candidates,
        frontend_root=frontend,
        execution_root=execution_root,
        reference_id="reference",
    )

    assert report["gate"] == "blocked"
    assert any(issue["id"] == "missing-dom-snapshot" for issue in report["issues"])


def test_ui_evidence_rejects_derived_lanczos_capture(tmp_path: Path) -> None:
    config, matrix, frontend, execution_root, candidates = _fixture(tmp_path)
    screenshot = candidates / "4x3/edit.png"
    payload = _payload(frontend, execution_root, screenshot)
    record = payload["records"][0]  # type: ignore[index]
    record.pop("capture_method")
    record["scale_method"] = "lanczos"

    report = validate_execution_evidence(
        payload,
        config_path=config,
        ui_matrix_path=matrix,
        candidate_root=candidates,
        frontend_root=frontend,
        execution_root=execution_root,
        reference_id="reference",
    )

    assert report["gate"] == "blocked"
    assert {issue["id"] for issue in report["issues"]} >= {
        "capture-method-mismatch",
        "derived-capture-not-allowed",
    }


def test_ui_evidence_rejects_changed_region_manifest_hash(tmp_path: Path) -> None:
    config, matrix, frontend, execution_root, candidates = _fixture(tmp_path)
    screenshot = candidates / "4x3/edit.png"
    payload = _payload(frontend, execution_root, screenshot)
    regions = tmp_path / "ui-regions.json"
    regions.write_text('{"version":"1"}', encoding="utf-8")
    payload["regions"] = {  # type: ignore[index]
        "manifest": str(regions),
        "manifest_sha256": "0" * 64,
    }

    report = validate_execution_evidence(
        payload,
        config_path=config,
        ui_matrix_path=matrix,
        candidate_root=candidates,
        frontend_root=frontend,
        execution_root=execution_root,
        reference_id="reference",
        region_manifest_path=regions,
    )

    assert any(
        issue["id"] == "region-manifest-hash-mismatch"
        for issue in report["issues"]
    )
