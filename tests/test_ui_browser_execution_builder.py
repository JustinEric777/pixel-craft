import json
from pathlib import Path

from PIL import Image

from scripts.build_ui_browser_execution import build_execution


def _matrix(tmp_path: Path, states: list[str]) -> Path:
    path = tmp_path / "ui-matrix.json"
    path.write_text(
        json.dumps(
            {
                "reference_id": "reference",
                "matrix_fingerprint": "c" * 64,
                "records": [{"id": state} for state in states],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_build_execution_links_verified_fixture_and_current_screenshot(tmp_path: Path) -> None:
    diagnostics = tmp_path / "diagnostics"
    candidates = diagnostics / "ui-candidates"
    sources = diagnostics / "ui-capture-raw"
    source = sources / "40x30" / "catalog.png"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (40, 30)).save(source)
    (source.parent / "catalog.dom.json").write_text(
        json.dumps({"html": "<main>catalog</main>"}),
        encoding="utf-8",
    )
    (source.parent / "catalog.ax.json").write_text(
        json.dumps({"tree": "main: catalog"}),
        encoding="utf-8",
    )
    screenshot = candidates / "40x30" / "catalog.png"
    screenshot.parent.mkdir(parents=True)
    with Image.open(source) as image:
        image.save(screenshot)
    manifest = tmp_path / "reference-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "reference_id": "reference",
                "matrix_fingerprint": "c" * 64,
                "records": [
                    {
                        "matrix_state_id": "catalog",
                        "viewport": [40, 30],
                        "fixture_id": "catalog:fixture",
                        "fixture_hash": "a" * 64,
                        "status": "verified",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "src" / "main.tsx").write_text("export {};", encoding="utf-8")
    fixture = diagnostics / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "collection": "fixture",
                "expected_count": 1,
                "catalog_count": 1,
                "unique_source_hash_count": 1,
                "fixture_fingerprint": "b" * 64,
                "records": [{"filename": "image.jpg", "source_sha256": "c" * 64}],
            }
        ),
        encoding="utf-8",
    )

    payload = build_execution(
        reference_manifest=manifest,
        ui_matrix=_matrix(tmp_path, ["catalog"]),
        fixture_manifest=fixture,
        candidate_root=candidates,
        source_capture_root=sources,
        diagnostics_root=diagnostics,
        frontend_root=frontend,
        browser="browser",
        browser_version="1",
        capture_engine="Chrome Headless CDP",
        locale="zh-Hans",
        timezone="Asia/Shanghai",
        logical_viewport=(20, 15),
        device_scale_factor=2,
    )

    assert payload["reference_id"] == "reference"
    assert payload["matrix_fingerprint"] == "c" * 64
    assert payload["environment"]["logical_viewport"] == [20, 15]
    assert payload["environment"]["physical_viewport"] == ["40x30"]
    assert payload["environment"]["device_scale_factor"] == 2
    assert payload["records"][0]["screenshot"] == "ui-candidates/40x30/catalog.png"
    assert payload["records"][0]["source_capture"] == "ui-capture-raw/40x30/catalog.png"
    assert payload["records"][0]["dom_snapshot"] == "ui-capture-raw/40x30/catalog.dom.json"
    assert payload["records"][0]["accessibility_tree"] == "ui-capture-raw/40x30/catalog.ax.json"
    assert payload["records"][0]["capture_method"] == "native-dpr2"
    assert payload["records"][0]["matrix_state_id"] == "catalog"
    assert "state" not in payload["records"][0]
    assert payload["records"][0]["actual_fixture_fingerprint"] == "b" * 64
    assert payload["fixture"]["manifest"] == "fixture.json"
    assert len(payload["records"][0]["screenshot_sha256"]) == 64


def test_build_execution_can_publish_incomplete_evidence_as_blocked(tmp_path: Path) -> None:
    diagnostics = tmp_path / "diagnostics"
    manifest = tmp_path / "reference-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "reference_id": "reference",
                "matrix_fingerprint": "c" * 64,
                "records": [
                    {
                        "matrix_state_id": "multi-image-complete",
                        "viewport": [40, 30],
                        "fixture_id": "catalog:fixture",
                        "fixture_hash": "a" * 64,
                        "status": "verified",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "src" / "main.tsx").write_text("export {};", encoding="utf-8")
    fixture = diagnostics / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        json.dumps(
            {
                "collection": "fixture",
                "expected_count": 1,
                "catalog_count": 1,
                "unique_source_hash_count": 1,
                "fixture_fingerprint": "b" * 64,
                "records": [],
            }
        ),
        encoding="utf-8",
    )

    payload = build_execution(
        reference_manifest=manifest,
        ui_matrix=_matrix(tmp_path, ["multi-image-complete"]),
        fixture_manifest=fixture,
        candidate_root=diagnostics / "ui-candidates",
        source_capture_root=diagnostics / "ui-capture-raw",
        diagnostics_root=diagnostics,
        frontend_root=frontend,
        browser="browser",
        browser_version="1",
        capture_engine="Chrome Headless CDP",
        locale="zh-Hans",
        timezone="Asia/Shanghai",
        logical_viewport=(20, 15),
        device_scale_factor=2,
        allow_incomplete=True,
    )

    assert payload["gate"] == "blocked"
    assert payload["records"] == []
    assert payload["missing_records"] == [
        {
            "viewport": "40x30",
            "matrix_state_id": "multi-image-complete",
            "reason": "missing-ui-candidate",
        }
    ]


def test_build_execution_reports_unverified_native_reference_when_incomplete(
    tmp_path: Path,
) -> None:
    diagnostics = tmp_path / "diagnostics"
    manifest = tmp_path / "reference-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "reference_id": "reference",
                "matrix_fingerprint": "c" * 64,
                "records": [
                    {
                        "matrix_state_id": "parameter:modified",
                        "viewport": [40, 30],
                        "status": "invalid-evidence",
                        "issues": ["screenshot-missing"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "src" / "main.tsx").write_text("export {};", encoding="utf-8")
    fixture = diagnostics / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        json.dumps(
            {
                "collection": "fixture",
                "expected_count": 1,
                "catalog_count": 1,
                "unique_source_hash_count": 1,
                "fixture_fingerprint": "b" * 64,
                "records": [],
            }
        ),
        encoding="utf-8",
    )

    payload = build_execution(
        reference_manifest=manifest,
        ui_matrix=_matrix(tmp_path, ["parameter:modified"]),
        fixture_manifest=fixture,
        candidate_root=diagnostics / "ui-candidates",
        source_capture_root=diagnostics / "ui-capture-raw",
        diagnostics_root=diagnostics,
        frontend_root=frontend,
        browser="browser",
        browser_version="1",
        capture_engine="Chrome Headless CDP",
        locale="zh-Hans",
        timezone="Asia/Shanghai",
        logical_viewport=(20, 15),
        device_scale_factor=2,
        allow_incomplete=True,
    )

    assert payload["gate"] == "blocked"
    assert payload["records"] == []
    assert payload["missing_records"] == [
        {
            "viewport": "40x30",
            "matrix_state_id": "parameter:modified",
            "reason": "native-reference-not-verified",
            "native_issues": ["screenshot-missing"],
        }
    ]
