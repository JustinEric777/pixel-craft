"""Import version-locked preset artwork from the local Luminar Neo app.

Only collection covers and preset icons referenced by ``configs/presets/free.json``
are copied. The source application version is verified before any write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _app_version(app: Path) -> tuple[str, str]:
    with (app / "Contents" / "Info.plist").open("rb") as handle:
        payload = plistlib.load(handle)
    return str(payload.get("CFBundleShortVersionString", "")), str(
        payload.get("CFBundleVersion", "")
    )


def run(
    app: Path,
    preset_config: Path,
    destination: Path,
    *,
    expected_version: str,
    expected_build: str,
) -> dict[str, Any]:
    app = app.resolve()
    version, build = _app_version(app)
    if (version, build) != (expected_version, expected_build):
        raise ValueError(
            f"Luminar source is {version}-{build}; "
            f"expected {expected_version}-{expected_build}"
        )

    collections = (
        app
        / "Contents"
        / "Frameworks"
        / "MIPLResources.framework"
        / "Versions"
        / "A"
        / "Resources"
        / "TemplatePacks"
        / "Collections"
    )
    configured = json.loads(preset_config.read_text(encoding="utf-8"))["presets"]
    preset_roots: dict[str, Path] = {}
    for path in collections.rglob("*.lnp"):
        if not path.is_dir():
            continue
        preset_roots[path.stem.upper()] = path
        template = path / "template.lmps"
        if template.is_file():
            internal_uuid = json.loads(template.read_text(encoding="utf-8-sig")).get("uuid")
            if internal_uuid:
                preset_roots[str(internal_uuid).upper()] = path
    destination.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    categories: dict[str, dict[str, str]] = {}
    missing_icons: list[str] = []

    for preset in configured:
        preset_id = str(preset["id"])
        preset_uuid = str(preset["source"]["uuid"]).upper()
        source_root = preset_roots.get(preset_uuid)
        if source_root is None:
            raise FileNotFoundError(f"configured preset is absent from Luminar: {preset_uuid}")
        collection_id = source_root.parent.name
        target_root = destination / "Collections" / collection_id
        icon = source_root / "icon.jpg"
        icon_relative: str | None = None
        if icon.is_file():
            icon_target = target_root / source_root.name / "icon.jpg"
            icon_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(icon, icon_target)
            icon_relative = icon_target.relative_to(destination).as_posix()
        else:
            missing_icons.append(preset_uuid)

        category = str(preset["category"])
        category_record = categories.setdefault(
            category,
            {"collection_id": collection_id},
        )
        if category_record["collection_id"] != collection_id:
            raise ValueError(f"category spans multiple Luminar collections: {category}")
        for variant in ("big", "small"):
            cover = source_root.parent / f"{variant}.jpg"
            if cover.is_file():
                cover_target = target_root / f"{variant}.jpg"
                cover_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cover, cover_target)
                category_record[variant] = cover_target.relative_to(destination).as_posix()

        records.append(
            {
                "id": preset_id,
                "uuid": preset_uuid,
                "category": category,
                "collection_id": collection_id,
                "icon": icon_relative,
                "icon_sha256": _sha256(icon) if icon.is_file() else None,
            }
        )

    index = {
        "version": "1.0",
        "source": {
            "product": "Luminar Neo",
            "version": version,
            "build": build,
            "application": str(app),
        },
        "count": len(records),
        "icon_count": sum(record["icon"] is not None for record in records),
        "missing_icons": missing_icons,
        "categories": categories,
        "records": records,
    }
    (destination / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--app", type=Path, default=Path("/Applications/Luminar Neo.app"))
    parser.add_argument(
        "--preset-config", type=Path, default=ROOT / "configs" / "presets" / "free.json"
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=ROOT / "assets" / "materials" / "PresetPacks",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    report = run(
        args.app,
        args.preset_config,
        args.destination,
        expected_version=profile.version,
        expected_build=profile.build,
    )
    print(
        json.dumps(
            {
                "source": report["source"],
                "count": report["count"],
                "icon_count": report["icon_count"],
                "category_count": len(report["categories"]),
                "missing_icons": report["missing_icons"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
