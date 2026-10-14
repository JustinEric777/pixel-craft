"""Build a hashed catalog for effect-dependent image/material assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - conversion/inspection-only environments
    Image = None

CATEGORIES = {
    "SkyTextures": "sky",
    "Atmospheric": "atmosphere",
    "FaceRelightTextures": "face_relight",
    "FaceZonesTextures": "face_zones",
    "makeUpTextures": "makeup",
    "ContactLens": "contact_lens",
    "OverlayTextures": "overlay",
    "LutFiles": "lut",
    "DefaultLUTs": "lut",
    "PresetLUTs": "preset_lut",
    "PresetPacks": "preset_pack",
    "CameraProfiles": "camera_profile",
    "ColorTransfer": "color_transfer",
    "shaders": "shader",
    "RawSpeed": "raw_profile",
}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="assets directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    materials = args.root / "materials"
    for path in sorted(materials.rglob("*")):
        if not path.is_file() or any(
            part.startswith(".") for part in path.relative_to(materials).parts
        ):
            continue
        relative = path.relative_to(materials)
        family = CATEGORIES.get(relative.parts[0], "other")
        record = {
            "id": path.relative_to(args.root).as_posix().replace("/", "__"),
            "path": path.relative_to(args.root).as_posix(),
            "family": family,
            "source_family": relative.parts[0],
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        if Image is not None:
            try:
                with Image.open(path) as image:
                    record.update(
                        {
                            "width": image.width,
                            "height": image.height,
                            "mode": image.mode,
                            "format": image.format,
                            "icc_profile": bool(image.info.get("icc_profile")),
                        }
                    )
            except (OSError, ValueError):
                record["inspection_status"] = "non-raster-or-unreadable"
        records.append(record)
    result = {
        "version": "0.1.0",
        "root": str(args.root),
        "families": sorted({record["family"] for record in records}),
        "count": len(records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
