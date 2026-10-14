"""Validate project-owned visual assets against a selected Luminar reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _equivalent(source: Path, candidate: Path) -> bool:
    if source.suffix.lower() == ".json":
        return json.loads(source.read_text(encoding="utf-8-sig")) == json.loads(
            candidate.read_text(encoding="utf-8-sig")
        )
    if source.suffix.lower() == ".strings":
        return source.read_text(encoding="utf-8-sig").replace(
            "\r\n", "\n"
        ) == candidate.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return _sha256(source) == _sha256(candidate)


def _compare_tree(source: Path, candidate: Path) -> dict[str, Any]:
    source_files = {
        path.relative_to(source).as_posix(): path
        for path in source.rglob("*")
        if path.is_file()
    }
    candidate_files = {
        path.relative_to(candidate).as_posix(): path
        for path in candidate.rglob("*")
        if path.is_file()
    }
    common = source_files.keys() & candidate_files.keys()
    different = sorted(
        relative
        for relative in common
        if not _equivalent(source_files[relative], candidate_files[relative])
    )
    return {
        "source_count": len(source_files),
        "candidate_count": len(candidate_files),
        "missing": sorted(source_files.keys() - candidate_files.keys()),
        "extra": sorted(candidate_files.keys() - source_files.keys()),
        "different": different,
        "passed": not different and source_files.keys() == candidate_files.keys(),
    }


def run(
    app: Path, asset_root: Path, *, target_version: str, target_build: str
) -> dict[str, Any]:
    target = (target_version, target_build)
    with (app / "Contents" / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    actual = (
        str(info.get("CFBundleShortVersionString", "")),
        str(info.get("CFBundleVersion", "")),
    )
    resources = (
        app
        / "Contents/Frameworks/MIPLResources.framework/Versions/A/Resources"
    )
    materials = asset_root / "materials"
    families = {
        "sky": _compare_tree(resources / "SkyTextures", materials / "SkyTextures"),
        "overlay": _compare_tree(
            resources / "OverlayTextures", materials / "OverlayTextures"
        ),
        "lut": _compare_tree(resources / "DefaultLUTs", materials / "DefaultLUTs"),
    }

    artwork_root = materials / "PresetPacks"
    artwork = json.loads((artwork_root / "index.json").read_text(encoding="utf-8"))
    preset_issues: list[dict[str, str]] = []
    for record in artwork["records"]:
        if not record.get("icon"):
            preset_issues.append({"id": record["id"], "issue": "missing-index-icon"})
            continue
        relative = Path(str(record["icon"]))
        source = resources / "TemplatePacks" / relative
        candidate = artwork_root / relative
        if not source.is_file() or not candidate.is_file() or _sha256(source) != _sha256(candidate):
            preset_issues.append({"id": record["id"], "issue": "icon-mismatch"})
    for category, record in artwork["categories"].items():
        for variant in ("big", "small"):
            relative = Path(str(record.get(variant, "")))
            source = resources / "TemplatePacks" / relative
            candidate = artwork_root / relative
            if not source.is_file() or not candidate.is_file() or _sha256(source) != _sha256(candidate):
                preset_issues.append(
                    {"id": category, "issue": f"{variant}-cover-mismatch"}
                )
    preset_artwork = {
        "configured": artwork["count"],
        "icons": artwork["icon_count"],
        "categories": len(artwork["categories"]),
        "issues": preset_issues,
        "passed": not preset_issues
        and (artwork["source"]["version"], artwork["source"]["build"]) == target,
    }
    passed = actual == target and all(item["passed"] for item in families.values())
    passed = passed and preset_artwork["passed"]
    return {
        "version": "1.0",
        "target": {"version": target[0], "build": target[1]},
        "source": {"application": str(app), "version": actual[0], "build": actual[1]},
        "families": families,
        "preset_artwork": preset_artwork,
        "gate": "passed" if passed else "failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--app", type=Path, default=Path("/Applications/Luminar Neo.app"))
    parser.add_argument("--asset-root", type=Path, default=ROOT / "assets")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    report = run(
        args.app.resolve(),
        args.asset_root.resolve(),
        target_version=profile.version,
        target_build=profile.build,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
