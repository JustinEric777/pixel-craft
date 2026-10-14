import json
import plistlib
from pathlib import Path

import pytest

from scripts.import_luminar_preset_artwork import run


def _fake_app(root: Path, *, version: str = "1.28.1", build: str = "23487") -> Path:
    app = root / "Luminar Neo.app"
    info = app / "Contents" / "Info.plist"
    info.parent.mkdir(parents=True)
    with info.open("wb") as handle:
        plistlib.dump(
            {"CFBundleShortVersionString": version, "CFBundleVersion": build}, handle
        )
    collection = (
        app
        / "Contents/Frameworks/MIPLResources.framework/Versions/A/Resources"
        / "TemplatePacks/Collections/COLLECTION"
    )
    preset = collection / "PRESET.lnp"
    preset.mkdir(parents=True)
    (preset / "icon.jpg").write_bytes(b"icon")
    (collection / "big.jpg").write_bytes(b"big")
    (collection / "small.jpg").write_bytes(b"small")
    return app


def test_imports_only_configured_version_locked_artwork(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    config = tmp_path / "free.json"
    config.write_text(
        json.dumps(
            {
                "presets": [
                    {
                        "id": "luminar_preset",
                        "category": "Category",
                        "source": {"uuid": "PRESET"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = run(
        app,
        config,
        tmp_path / "output",
        expected_version="1.28.1",
        expected_build="23487",
    )

    assert report["icon_count"] == 1
    assert report["categories"]["Category"]["collection_id"] == "COLLECTION"
    assert (tmp_path / "output/Collections/COLLECTION/PRESET.lnp/icon.jpg").read_bytes() == b"icon"


def test_rejects_source_from_a_different_build(tmp_path: Path) -> None:
    app = _fake_app(tmp_path, build="17225")
    config = tmp_path / "free.json"
    config.write_text('{"presets": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="expected 1.28.1-23487"):
        run(
            app,
            config,
            tmp_path / "output",
            expected_version="1.28.1",
            expected_build="23487",
        )
