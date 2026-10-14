"""Build a read-only inventory for an external Luminar installation.

The inventory is intentionally diagnostic: it never copies files into the
project and it does not treat a folder name as authoritative version evidence.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog

SUPPORTED_EXTENSIONS = {
    ".cube",
    ".fpmcp",
    ".jpeg",
    ".jpg",
    ".json",
    ".lmps",
    ".msk",
    ".pm",
    ".png",
    ".tif",
    ".tiff",
}
SOURCE_FAMILIES = {
    "SkyTextures": "sky",
    "Atmospheric": "atmosphere",
    "OverlayTextures": "overlay",
    "ColorTransfer": "color_transfer",
    "ContactLens": "contact_lens",
    "makeUpTextures": "makeup",
    "FaceZonesTextures": "face_zones",
    "FaceRelightTextures": "face_relight",
    "LutFiles": "lut",
    "PresetPacks": "preset_pack",
}
UI_ASSEMBLIES = (
    "Common.Styles.dll",
    "Common.UI.dll",
    "Luminar.RightPanel.dll",
    "Luminar.UI.dll",
    "LuminarAI.UI.dll",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _declared_version(source_root: Path) -> dict[str, str | None]:
    appinfo = source_root / "Luminar Neo" / "App" / "AppInfo" / "appinfo.ini"
    if not appinfo.is_file():
        return {"package_version": None, "display_version": None, "evidence": None}
    parser = configparser.ConfigParser()
    parser.read(appinfo, encoding="utf-8-sig")
    return {
        "package_version": parser.get("Version", "PackageVersion", fallback=None),
        "display_version": parser.get("Version", "DisplayVersion", fallback=None),
        "evidence": str(appinfo),
    }


def _existing_hashes(manifest_path: Path) -> dict[str, list[str]]:
    if not manifest_path.is_file():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for record in payload.get("records", []):
        digest = record.get("sha256")
        if isinstance(digest, str):
            result.setdefault(digest, []).append(str(record.get("path", "")))
    return result


def _candidate_status(relative: Path) -> str:
    lowered = "/".join(part.lower() for part in relative.parts)
    if "marketplace" in lowered or "promo" in lowered:
        return "paid-or-promo"
    return "authorization-pending"


def run(source_root: Path, manifest_path: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    app_root = source_root / "Luminar Neo" / "App" / "Luminar Neo"
    if not app_root.is_dir():
        raise FileNotFoundError(f"Luminar application root not found: {app_root}")

    existing = _existing_hashes(manifest_path)
    records: list[dict[str, Any]] = []
    roots = [(app_root / "profiles" / family, family) for family in SOURCE_FAMILIES]
    roots.extend(
        [
            (app_root / "Data" / "LutFiles", "LutFiles"),
            (app_root / "Data" / "PresetPacks", "PresetPacks"),
        ]
    )
    visited: set[Path] = set()
    for candidate_root, source_family in roots:
        if not candidate_root.is_dir():
            continue
        for path in sorted(candidate_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in visited:
                continue
            visited.add(resolved)
            digest = _sha256(path)
            relative = path.relative_to(app_root)
            matching = existing.get(digest, [])
            records.append(
                {
                    "relative_path": relative.as_posix(),
                    "source_family": source_family,
                    "family": SOURCE_FAMILIES[source_family],
                    "filename": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                    "sha256": digest,
                    "candidate_status": _candidate_status(relative),
                    "existing_project_matches": matching,
                    "project_hash_match": bool(matching),
                    "import_status": "already-present" if matching else "not-imported",
                }
            )

    ui_records = []
    for filename in UI_ASSEMBLIES:
        path = app_root / filename
        if path.is_file():
            ui_records.append(
                {
                    "relative_path": path.relative_to(app_root).as_posix(),
                    "filename": filename,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                    "usage": "resource-name-and-visual-reference-only",
                }
            )

    declared = _declared_version(source_root)
    counts = Counter(record["family"] for record in records)
    active = load_reference_catalog(project_root=ROOT).resolve()
    return {
        "version": "1.0",
        "source_root": str(source_root),
        "platform": "windows-x64-portable",
        "declared_version": declared,
        "target_reference": active.id,
        "target_build_match": False,
        "source_policy": "read-only-diagnostic",
        "copy_performed": False,
        "count": len(records),
        "family_counts": dict(sorted(counts.items())),
        "project_hash_match_count": sum(record["project_hash_match"] for record in records),
        "paid_or_promo_count": sum(
            record["candidate_status"] == "paid-or-promo" for record in records
        ),
        "authorization_pending_count": sum(
            record["candidate_status"] == "authorization-pending" for record in records
        ),
        "ui_assemblies": ui_records,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "assets" / "manifests" / "registry.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "diagnostics" / "external-luminar-assets.json",
    )
    args = parser.parse_args()
    report = run(args.source_root, args.manifest.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "declared_version": report["declared_version"],
                "count": report["count"],
                "project_hash_match_count": report["project_hash_match_count"],
                "paid_or_promo_count": report["paid_or_promo_count"],
                "copy_performed": report["copy_performed"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
