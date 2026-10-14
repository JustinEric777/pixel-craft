"""Build deterministic inputs for exact-parity capabilities with scene prerequisites."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog

DEFAULT_OUTPUT = ROOT / "test_data/parity/inputs/exact-fixtures"
NOISE_SEED = 0x5A1F
NIGHT_SOURCE = (
    ROOT
    / "test_data/parity/inputs/summer-outdoor/a_7592944921116426792/002_0c88782170.jpg"
)
NOISE_SOURCE = (
    ROOT
    / "test_data/parity/inputs/summer-outdoor/a_7641588658059690559/003_7922c31929.jpg"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0


def _write_rgb(path: Path, rgb: np.ndarray) -> None:
    encoded = np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(encoded, mode="RGB").save(path, format="PNG", compress_level=9)


def _manifest_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _night_lights_fixture(source: Path, output: Path) -> None:
    rgb = _load_rgb(source)
    height, width = rgb.shape[:2]
    night = np.clip(rgb * np.array([0.17, 0.22, 0.34], dtype=np.float32), 0, 1)
    yy, xx = np.mgrid[0:height, 0:width]
    lights = (
        (0.16, 0.43, 0.020),
        (0.27, 0.39, 0.014),
        (0.38, 0.40, 0.012),
        (0.67, 0.43, 0.016),
        (0.79, 0.42, 0.020),
        (0.88, 0.39, 0.013),
    )
    warm = np.array([1.0, 0.62, 0.18], dtype=np.float32)
    for normalized_x, normalized_y, normalized_sigma in lights:
        center_x = normalized_x * width
        center_y = normalized_y * height
        sigma = normalized_sigma * max(width, height)
        distance = (xx - center_x) ** 2 + (yy - center_y) ** 2
        glow = np.exp(-distance / (2.0 * sigma**2)).astype(np.float32)
        core = np.exp(-distance / (2.0 * max(1.0, sigma * 0.16) ** 2)).astype(
            np.float32
        )
        night += glow[..., None] * warm * 0.52
        night += core[..., None] * np.array([1.0, 0.96, 0.80], dtype=np.float32)
    _write_rgb(output, night)


def _noise_fixture(source: Path, output: Path) -> None:
    rgb = _load_rgb(source)
    rng = np.random.default_rng(NOISE_SEED)
    height, width = rgb.shape[:2]
    luma_noise = rng.normal(0.0, 0.085, size=(height, width, 1)).astype(np.float32)
    chroma_noise = rng.normal(0.0, 0.045, size=rgb.shape).astype(np.float32)
    noisy = np.clip(rgb + luma_noise + chroma_noise, 0, 1)
    _write_rgb(output, noisy)


def build_fixtures(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "night-lights": (NIGHT_SOURCE, output_dir / "night-lights.png", _night_lights_fixture),
        "sensor-noise": (NOISE_SOURCE, output_dir / "sensor-noise.png", _noise_fixture),
    }
    records = []
    for fixture_id, (source, output, builder) in fixtures.items():
        builder(source, output)
        with Image.open(output) as image:
            width, height = image.size
        records.append(
            {
                "id": fixture_id,
                "path": _manifest_path(output),
                "sha256": _sha256(output),
                "width": width,
                "height": height,
                "source": {
                    "path": _manifest_path(source),
                    "sha256": _sha256(source),
                },
                "generator": builder.__name__,
            }
        )
    active = load_reference_catalog(project_root=ROOT).resolve()
    manifest = {
        "version": "1.0",
        "reference_build": active.id,
        "deterministic": True,
        "fixtures": records,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_fixtures(args.output_dir.resolve())
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
