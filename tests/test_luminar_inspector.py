import json
import plistlib
from pathlib import Path

from scripts.luminar_install_inspector import LuminarInstallInspector


def test_tool_sections_preserve_sky_parameter_order() -> None:
    payload = {
        "AdjustmentLayers": {
            "SkyReplacementAdjustmentLayer": [
                {
                    "expandable": True,
                    "title": "Mask Refinement",
                    "children": [[
                        {"parameter": "SkyGlobal"},
                        {"parameter": "FixGaps"},
                        {"parameter": "Sigma"},
                    ]],
                }
            ]
        }
    }
    sections = LuminarInstallInspector._tool_sections(
        payload, "SkyReplacementAdjustmentLayer"
    )
    assert sections == [
        {
            "id": "mask-refinement",
            "title": "Mask Refinement",
            "expandable": True,
            "expanded": True,
            "parameters": ["SkyGlobal", "FixGaps", "Sigma"],
        }
    ]


def test_inspector_rejects_non_application(tmp_path: Path) -> None:
    inspector = LuminarInstallInspector(tmp_path / "missing.app")
    try:
        inspector.inspect()
    except FileNotFoundError as exc:
        assert "invalid Luminar installation" in str(exc)
    else:
        raise AssertionError("missing installation should fail")


def test_inspector_uses_installed_version_in_reference_id(tmp_path: Path) -> None:
    app = tmp_path / "Luminar Neo.app"
    resources = (
        app
        / "Contents/Frameworks/MIPLResources.framework/Versions/A/Resources"
    )
    profiles = resources / "profiles"
    profiles.mkdir(parents=True)
    with (app / "Contents/Info.plist").open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleName": "Luminar Neo",
                "CFBundleShortVersionString": "1.27.1",
                "CFBundleVersion": "22702",
            },
            handle,
        )
    (resources / "EffectsLayoutNeo.json").write_text(
        json.dumps({"AdjustmentLayers": {}}), encoding="utf-8"
    )
    (resources / "MPEditPanelLayoutConfig.json").write_text("[]", encoding="utf-8")
    (resources / "EffectsConfig.json").write_text("{}", encoding="utf-8")

    manifest, contracts, lock = LuminarInstallInspector(app).inspect()

    expected = "luminar-neo-macos-1.27.1-22702"
    assert manifest["reference_build"]["id"] == expected
    assert manifest["counts"]["preset_collections"] == 0
    assert manifest["counts"]["presets"] == 0
    assert manifest["counts"]["presets_declared"] == 0
    assert contracts["reference_build_id"] == expected
    assert lock["reference_build_id"] == expected


def test_overlay_inventory_separates_active_and_orphan_items(tmp_path: Path) -> None:
    app = tmp_path / "Luminar Neo.app"
    inspector = LuminarInstallInspector(app)
    collection = inspector.resources / "OverlayTextures/Free/collection"
    (collection / "active").mkdir(parents=True)
    (collection / "orphan").mkdir()
    (collection / "config.json").write_text(
        '{"identifier": "collection", "items": ["active"]}', encoding="utf-8"
    )
    (collection / "active/config.json").write_text(
        '{"path": "overlay.jpg"}', encoding="utf-8"
    )
    (collection / "active/overlay.jpg").write_bytes(b"raster")
    (collection / "orphan/config.json").write_text("{}", encoding="utf-8")

    records = inspector._overlay_collections()

    assert records[0]["active_item_ids"] == ["active"]
    assert records[0]["active_item_count"] == 1
    assert records[0]["discovered_item_count"] == 2
    assert records[0]["orphan_item_count"] == 1
