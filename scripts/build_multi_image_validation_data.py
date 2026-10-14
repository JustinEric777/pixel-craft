"""Create deterministic HDR, focus-stack, and panorama validation inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from PIL.TiffImagePlugin import IFDRational

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_exif(
    *,
    exposure_time: IFDRational | None = None,
    exposure_bias: IFDRational | None = None,
) -> Image.Exif:
    exposure_time = exposure_time or IFDRational(1, 250)
    exposure_bias = exposure_bias or IFDRational(0, 1)
    exif = Image.Exif()
    exif[0x010F] = "ZPixel"
    exif[0x0110] = "Multi Image Validation Camera"
    exif[0x0132] = "2026:08:20 12:00:00"
    exif[0x829A] = exposure_time
    exif[0x829D] = IFDRational(28, 10)
    exif[0x8822] = 1
    exif[0x8827] = 100
    exif[0x9003] = "2026:08:20 12:00:00"
    exif[0x9004] = "2026:08:20 12:00:00"
    exif[0x9204] = exposure_bias
    exif[0x920A] = IFDRational(35, 1)
    return exif


def _save_jpeg(image: Image.Image, path: Path, *, exif: Image.Exif) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(
        path,
        format="JPEG",
        quality=95,
        subsampling=0,
        exif=exif,
    )


def _hdr(source: Image.Image, root: Path) -> list[Path]:
    records = []
    brackets = (
        (0.5, IFDRational(1, 1000), IFDRational(-2, 1)),
        (1.0, IFDRational(1, 250), IFDRational(0, 1)),
        (1.5, IFDRational(1, 60), IFDRational(2, 1)),
    )
    for index, (factor, exposure_time, exposure_bias) in enumerate(
        brackets, start=1
    ):
        path = root / f"frame-{index}-brightness-{factor:.1f}.jpg"
        _save_jpeg(
            ImageEnhance.Brightness(source).enhance(factor),
            path,
            exif=_capture_exif(
                exposure_time=exposure_time,
                exposure_bias=exposure_bias,
            ),
        )
        records.append(path)
    return records


def _focus(source: Image.Image, root: Path) -> list[Path]:
    sharp = source.convert("RGB")
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=8))
    width, height = sharp.size
    records = []
    for index in range(3):
        left = round(width * index / 3)
        right = round(width * (index + 1) / 3)
        frame = blurred.copy()
        frame.paste(sharp.crop((left, 0, right, height)), (left, 0))
        path = root / f"frame-{index + 1}-focus-zone-{index + 1}.jpg"
        _save_jpeg(frame, path, exif=_capture_exif())
        records.append(path)
    return records


def _panorama(source: Image.Image, root: Path) -> list[Path]:
    image = source.convert("RGB")
    width, height = image.size
    crop_width = max(2, round(width * 0.6))
    offsets = (0, round((width - crop_width) / 2), width - crop_width)
    records = []
    for index, left in enumerate(offsets, start=1):
        path = root / f"frame-{index}-offset-{left}.jpg"
        _save_jpeg(
            image.crop((left, 0, left + crop_width, height)),
            path,
            exif=_capture_exif(),
        )
        records.append(path)
    return records


def build(source_path: Path, output_root: Path) -> dict:
    with Image.open(source_path) as source_image:
        source = source_image.convert("RGB")
        outputs = {
            "hdr_merge": _hdr(source, output_root / "hdr_merge"),
            "focus_stacking": _focus(source, output_root / "focus_stacking"),
            "panorama_stitching": _panorama(
                source, output_root / "panorama_stitching"
            ),
        }
    report = {
        "version": "1.1",
        "generated_by": "scripts/build_multi_image_validation_data.py",
        "source": {"path": str(source_path), "sha256": _sha256(source_path)},
        "workflows": {
            workflow: [
                {"path": str(path), "sha256": _sha256(path)} for path in paths
            ]
            for workflow, paths in outputs.items()
        },
    }
    manifest = output_root / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        help="Source image. Defaults to the first current validation JPEG.",
    )
    parser.add_argument(
        "--output-root", type=Path, default=ROOT / "test_data/multi_image"
    )
    args = parser.parse_args()
    source = args.source
    if source is None:
        candidates = sorted(
            path
            for pattern in ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG")
            for path in (ROOT / "test_data/夏日户外拍照").rglob(pattern)
        )
        if not candidates:
            parser.error("test_data/夏日户外拍照 does not contain a JPEG")
        source = candidates[0]
    report = build(source.resolve(), args.output_root.resolve())
    print(
        json.dumps(
            {
                "source": report["source"]["path"],
                "workflows": {
                    key: len(value) for key, value in report["workflows"].items()
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
