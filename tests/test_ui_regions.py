from __future__ import annotations

import json
from pathlib import Path

from scripts.ui_regions import content_sha256, sha256_file, validate_region_manifest


def _manifest(tmp_path: Path) -> tuple[dict[str, object], Path]:
    reference_root = tmp_path / "references"
    ax = reference_root / "4x3" / "edit.ax.json"
    ax.parent.mkdir(parents=True)
    ax.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "identifier": "NavigationPanel.Tab.Help",
                        "position": [1, 1],
                        "size": [1, 1],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    payload: dict[str, object] = {
        "version": "1.0",
        "reference_id": "reference",
        "coordinate_space": "physical-pixels",
        "content_sha256": "",
        "records": [
            {
                "state": "edit",
                "viewport": [4, 3],
                "reference_ax": "4x3/edit.ax.json",
                "reference_ax_sha256": sha256_file(ax),
                "include": [[0, 0, 4, 3]],
                "exclude": [
                    {
                        "id": "help",
                        "bounds": [1, 1, 1, 1],
                        "native_ax_selector": {
                            "identifier": "NavigationPanel.Tab.Help"
                        },
                        "scope_reason": "Help is outside the requested product scope.",
                    }
                ],
            }
        ],
    }
    payload["content_sha256"] = content_sha256(payload)
    return payload, reference_root


def _validate(payload: dict[str, object], reference_root: Path):
    payload["content_sha256"] = content_sha256(payload)
    return validate_region_manifest(
        payload,
        reference_root=reference_root,
        reference_id="reference",
        expected={("4x3", "edit")},
    )


def test_region_manifest_builds_native_anchored_mask(tmp_path: Path) -> None:
    payload, reference_root = _manifest(tmp_path)

    issues, masks = _validate(payload, reference_root)

    assert issues == []
    assert masks[("4x3", "edit")].sum() == 11


def test_region_manifest_rejects_out_of_bounds_and_overlap(tmp_path: Path) -> None:
    payload, reference_root = _manifest(tmp_path)
    record = payload["records"][0]
    record["exclude"].append(
        {
            "id": "overlap",
            "bounds": [1, 1, 4, 1],
            "native_ax_selector": {"identifier": "NavigationPanel.Tab.Help"},
            "scope_reason": "excluded",
        }
    )

    issues, _masks = _validate(payload, reference_root)

    assert {issue["id"] for issue in issues} >= {
        "region-out-of-bounds",
        "exclude-outside-include",
        "ambiguous-overlapping-exclusions",
    }


def test_region_manifest_requires_ax_selector_and_scope_reason(tmp_path: Path) -> None:
    payload, reference_root = _manifest(tmp_path)
    exclusion = payload["records"][0]["exclude"][0]
    exclusion["native_ax_selector"] = {"identifier": "missing"}
    exclusion["scope_reason"] = ""

    issues, _masks = _validate(payload, reference_root)

    assert {issue["id"] for issue in issues} >= {
        "region-native-ax-selector-missing",
        "missing-region-scope-reason",
    }


def test_region_manifest_rejects_changed_native_ax_hash(tmp_path: Path) -> None:
    payload, reference_root = _manifest(tmp_path)
    (reference_root / "4x3" / "edit.ax.json").write_text(
        json.dumps({"nodes": []}), encoding="utf-8"
    )

    issues, _masks = _validate(payload, reference_root)

    assert {issue["id"] for issue in issues} >= {
        "region-native-ax-hash-mismatch",
        "region-native-ax-selector-missing",
    }
