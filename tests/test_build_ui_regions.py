from __future__ import annotations

import json
from pathlib import Path

from scripts.build_ui_regions import build
from scripts.ui_regions import sha256_file, validate_region_manifest


def test_build_uses_only_current_matrix_ids_and_verified_native_evidence(
    tmp_path: Path,
) -> None:
    reference_root = tmp_path / "ui"
    ax_path = reference_root / "2880x1800" / "workspace:catalog.ax.json"
    ax_path.parent.mkdir(parents=True)
    ax_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "description": "教程",
                        "position": [1, 1],
                        "size": [1, 1],
                    },
                    {
                        "identifier": "NavigationPanel.Tab.Help",
                        "position": [2, 1],
                        "size": [1, 1],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix = {
        "reference_id": "reference",
        "matrix_fingerprint": "a" * 64,
        "records": [{"id": "workspace:catalog"}],
    }
    reference_manifest = {
        "reference_id": "reference",
        "matrix_fingerprint": "a" * 64,
        "records": [
            {
                "matrix_state_id": "workspace:catalog",
                "viewport": [2880, 1800],
                "accessibility_tree": "2880x1800/workspace:catalog.ax.json",
                "accessibility_tree_sha256": sha256_file(ax_path),
                "status": "verified",
                "issues": [],
            }
        ],
    }

    payload = build(
        matrix=matrix,
        reference_manifest=reference_manifest,
        reference_root=reference_root,
    )

    assert [record["state"] for record in payload["records"]] == [
        "workspace:catalog"
    ]
    issues, masks = validate_region_manifest(
        payload,
        reference_root=reference_root,
        reference_id="reference",
        expected={("2880x1800", "workspace:catalog")},
    )
    assert issues == []
    assert masks[("2880x1800", "workspace:catalog")].any()


def test_build_rejects_reference_states_outside_the_current_matrix(
    tmp_path: Path,
) -> None:
    matrix = {"records": [{"id": "workspace:edit"}]}
    reference_manifest = {
        "records": [{"matrix_state_id": "legacy-edit", "status": "verified"}]
    }

    try:
        build(
            matrix=matrix,
            reference_manifest=reference_manifest,
            reference_root=tmp_path,
        )
    except ValueError as error:
        assert "does not match the UI matrix" in str(error)
    else:
        raise AssertionError("stale reference state should have been rejected")
