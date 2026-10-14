import hashlib
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from scripts.build_luminar_sampling_queue import build_queue


def _image(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 6), color).save(path)
    return path


def _case(case_id: str, capability_id: str, source: Path) -> dict:
    return {
        "case_id": case_id,
        "capability_id": capability_id,
        "input": {
            "path": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "parameters": {"amount": 0.5},
    }


def test_complete_sampling_queue_separates_effect_asset_ui_and_workflow(tmp_path: Path) -> None:
    dramatic = _image(tmp_path / "dramatic.jpg", (10, 20, 30))
    sky_input = _image(tmp_path / "sky-input.jpg", (30, 60, 90))
    sky_asset = _image(tmp_path / "skies/Blue/One.jpg", (60, 90, 120))
    _image(tmp_path / "overlays/Free/glow/Glow.jpg", (120, 90, 60))
    (tmp_path / "overlays/Free/config.json").write_text(
        '{"items": ["glow"]}', encoding="utf-8"
    )
    (tmp_path / "overlays/Free/glow/config.json").write_text(
        '{"path": "Glow.jpg"}', encoding="utf-8"
    )
    localization = tmp_path / "overlays/Free/localizations/zh-Hans.strings"
    localization.parent.mkdir(parents=True, exist_ok=True)
    localization.write_text('"Name" = "耀斑";\n', encoding="utf-8")
    for workflow in ("hdr_merge", "focus_stacking", "panorama_stitching"):
        _image(tmp_path / "multi" / workflow / "one.jpg", (10, 20, 30))
        _image(tmp_path / "multi" / workflow / "two.jpg", (20, 30, 40))

    report = build_queue(
        reference_id="reference",
        cases_payload={
            "dataset_fingerprint": "fingerprint",
            "cases": [
                _case("enhance", "ai_enhance", dramatic),
                _case("sky", "sky_replace", sky_input),
                _case("sky-parameter-anchor", "sky_replace", sky_input),
                _case("upscale", "super_resolution", dramatic),
            ]
        },
        presets_payload={"presets": [{"id": "preset", "name": "Preset"}]},
        recipes={
            "ai_enhance": SimpleNamespace(
                locator_id="enhance", strategy="primary_slider", workspace="edit"
            ),
            "sky_replace": SimpleNamespace(
                locator_id="sky", strategy="asset_picker", workspace="edit"
            ),
            "super_resolution": SimpleNamespace(
                locator_id="upscale", strategy="panel_only", workspace="catalog"
            ),
        },
        sky_root=sky_asset.parents[1],
        overlay_root=tmp_path / "overlays",
        validation_root=tmp_path / "multi",
        viewports=((1440, 900),),
        ui_states=("catalog", "edit"),
        page_order=("catalog", "presets", "edit"),
        ui_state_pages={"catalog": "catalog", "edit": "edit"},
        ui_matrix_payload={
            "reference_id": "reference",
            "matrix_fingerprint": "a" * 64,
            "records": [
                {
                    "id": "workspace:catalog",
                    "kind": "workspace-state",
                    "workspace": "catalog",
                },
                {
                    "id": "workspace:edit",
                    "kind": "workspace-state",
                    "workspace": "edit",
                },
            ],
        },
        excluded_feature_groups=("generative-tools", "enhancement-tools"),
        excluded_capabilities=frozenset({"super_resolution"}),
        overlay_collection_order=("Free",),
        canonical_input_sha256={
            "preset": hashlib.sha256(dramatic.read_bytes()).hexdigest(),
            "overlay": hashlib.sha256(dramatic.read_bytes()).hexdigest(),
        },
    )

    assert report["counts"] == {
        "effect": 2,
        "overlay": 1,
        "preset": 1,
        "sky": 1,
        "ui": 2,
        "workflow": 3,
    }
    assert report["status_counts"] == {"pending-reference": 10}
    assert report["dataset_fingerprint"] == "fingerprint"
    assert report["traversal"] == {
        "page_order": ["catalog", "presets", "edit"],
        "within_page": "left-to-right, top-to-bottom",
    }
    assert [record["page"] for record in report["records"]] == [
        "catalog",
        "catalog",
        "catalog",
        "catalog",
        "presets",
        "edit",
        "edit",
        "edit",
        "edit",
        "edit",
    ]
    assert [record["scan_order"] for record in report["records"]] == list(
        range(1, 11)
    )
    assert not any(
        record.get("capability_id") == "super_resolution"
        for record in report["records"]
    )
    ui_records = [record for record in report["records"] if record["kind"] == "ui"]
    assert [record["matrix_state_id"] for record in ui_records] == [
        "workspace:catalog",
        "workspace:edit",
    ]
    assert all(record["matrix_fingerprint"] == "a" * 64 for record in ui_records)
    assert report["scope"] == {
        "excluded_feature_groups": ["generative-tools", "enhancement-tools"],
        "excluded_capabilities": ["super_resolution"],
        "effect_case_policy": "one-default-case-per-image-and-capability",
    }
    assert not any(
        record["id"] == "effect:sky-parameter-anchor"
        for record in report["records"]
    )
