import json
from pathlib import Path

import yaml

from configs.reference import ReferenceProfile
from scripts.build_release_fingerprint import (
    _fingerprint,
    _scope_summary,
    _validation_roots,
)


def test_fingerprint_is_order_independent_for_mappings() -> None:
    assert _fingerprint({"a": 1, "b": 2}) == _fingerprint({"b": 2, "a": 1})


def test_fingerprint_changes_with_artifact_hash(tmp_path: Path) -> None:
    first = [{"path": "model.onnx", "sha256": "a", "size": 1}]
    second = [{"path": "model.onnx", "sha256": "b", "size": 1}]

    assert _fingerprint(first) != _fingerprint(second)


def test_scope_summary_is_generated_from_contract_files(tmp_path: Path) -> None:
    (tmp_path / "configs/parity").mkdir(parents=True)
    (tmp_path / "configs/ui").mkdir(parents=True)
    (tmp_path / "configs/parity/core-ui-state-matrix.json").write_text(
        json.dumps(
            {
                "records": [
                    {"id": "edit", "comparison_mode": "pixel"},
                    {"id": "export", "comparison_mode": "semantic"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "configs/parity/core-interaction-matrix.json").write_text(
        json.dumps({"records": [{"id": "open"}, {"id": "save"}]}),
        encoding="utf-8",
    )
    (tmp_path / "configs/ui/editor.json").write_text(
        json.dumps(
            {
                "tool_groups": [{"capabilities": ["tone", "crop"]}],
                "catalog_actions": [{"capability_id": "export"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "configs/model.yaml").write_text(
        yaml.safe_dump({"models": [{"id": "one"}, {"id": "two"}]}),
        encoding="utf-8",
    )

    assert _scope_summary(tmp_path) == {
        "ui_state_count": 2,
        "pixel_ui_state_count": 1,
        "semantic_ui_state_count": 1,
        "interaction_contract_count": 2,
        "visible_capability_count": 3,
        "active_model_count": 2,
    }


def test_validation_roots_follow_selected_reference_profile(tmp_path: Path) -> None:
    profile = ReferenceProfile(
        id="candidate",
        product="Luminar Neo",
        version="1.28.1",
        build="23487",
        bundle_id="com.skylum.luminarneo",
        locale="zh-Hans",
        platform="macOS",
        cases_path=tmp_path / "references/candidate/cases.json",
        matrix_path=tmp_path / "references/candidate/reference-matrix.json",
        manifest_path=tmp_path / "references/candidate/manifest.json",
        capture_root=tmp_path / "outputs/candidate/captures",
        ui_reference_root=tmp_path / "outputs/candidate/ui",
        observations_root=tmp_path / "outputs/candidate/observations",
        diagnostics_root=tmp_path / "outputs/candidate/diagnostics",
        exact_gate_enabled=False,
    )

    roots = _validation_roots(tmp_path, profile)

    assert "references/candidate" in roots
    assert "outputs/candidate/diagnostics/sampling-queue.json" in roots
    assert not any("1.28.0" in root for root in roots)
