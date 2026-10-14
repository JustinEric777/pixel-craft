"""Parse and apply Adobe/IRIDAS ``.cube`` 3D lookup tables."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance


@dataclass(frozen=True)
class CubeLut:
    size: int
    domain_min: np.ndarray
    domain_max: np.ndarray
    table: np.ndarray


@lru_cache(maxsize=128)
def load_cube_lut(path: Path) -> CubeLut:
    """Load a 3D LUT and cache it by its resolved filesystem path."""
    source = path.resolve()
    size: int | None = None
    domain_min = np.zeros(3, dtype=np.float32)
    domain_max = np.ones(3, dtype=np.float32)
    values: list[list[float]] = []
    for raw_line in source.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "TITLE")):
            continue
        fields = line.split()
        directive = fields[0].upper()
        if directive == "LUT_3D_SIZE":
            size = int(fields[1])
        elif directive == "LUT_1D_SIZE":
            raise ValueError(f"1D LUT is not supported: {source}")
        elif directive == "DOMAIN_MIN":
            domain_min = np.asarray(fields[1:4], dtype=np.float32)
        elif directive == "DOMAIN_MAX":
            domain_max = np.asarray(fields[1:4], dtype=np.float32)
        else:
            try:
                values.append([float(fields[0]), float(fields[1]), float(fields[2])])
            except (IndexError, ValueError) as exc:
                raise ValueError(f"invalid CUBE row in {source}: {raw_line}") from exc
    if size is None or size < 2:
        raise ValueError(f"missing or invalid LUT_3D_SIZE: {source}")
    expected = size**3
    if len(values) != expected:
        raise ValueError(f"invalid CUBE sample count in {source}: {len(values)} != {expected}")
    if np.any(domain_max <= domain_min):
        raise ValueError(f"invalid CUBE domain: {source}")
    # CUBE files enumerate red fastest, then green, then blue. Reorder the
    # file-major [blue, green, red] dimensions for direct [red, green, blue]
    # indexing during interpolation.
    table = np.asarray(values, dtype=np.float32).reshape(size, size, size, 3).transpose(2, 1, 0, 3)
    table.setflags(write=False)
    domain_min.setflags(write=False)
    domain_max.setflags(write=False)
    return CubeLut(size=size, domain_min=domain_min, domain_max=domain_max, table=table)


def apply_cube_lut(
    image: Image.Image,
    path: Path,
    *,
    amount: float = 1.0,
    contrast: float = 0.0,
    saturation: float = 0.0,
) -> Image.Image:
    """Apply a CUBE LUT with trilinear interpolation and Luminar-style mix controls."""
    lut = load_cube_lut(path)
    source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    normalized = np.clip(
        (source - lut.domain_min) / (lut.domain_max - lut.domain_min),
        0.0,
        1.0,
    )
    position = normalized * (lut.size - 1)
    lower = np.floor(position).astype(np.intp)
    upper = np.minimum(lower + 1, lut.size - 1)
    fraction = position - lower

    r0, g0, b0 = lower[..., 0], lower[..., 1], lower[..., 2]
    r1, g1, b1 = upper[..., 0], upper[..., 1], upper[..., 2]
    fr, fg, fb = fraction[..., 0:1], fraction[..., 1:2], fraction[..., 2:3]
    c000 = lut.table[r0, g0, b0]
    c100 = lut.table[r1, g0, b0]
    c010 = lut.table[r0, g1, b0]
    c110 = lut.table[r1, g1, b0]
    c001 = lut.table[r0, g0, b1]
    c101 = lut.table[r1, g0, b1]
    c011 = lut.table[r0, g1, b1]
    c111 = lut.table[r1, g1, b1]
    c00 = c000 * (1.0 - fr) + c100 * fr
    c10 = c010 * (1.0 - fr) + c110 * fr
    c01 = c001 * (1.0 - fr) + c101 * fr
    c11 = c011 * (1.0 - fr) + c111 * fr
    c0 = c00 * (1.0 - fg) + c10 * fg
    c1 = c01 * (1.0 - fg) + c11 * fg
    graded = c0 * (1.0 - fb) + c1 * fb

    mix = max(0.0, min(1.0, amount))
    output = source * (1.0 - mix) + np.clip(graded, 0.0, 1.0) * mix
    result = Image.fromarray(np.rint(np.clip(output, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")
    if contrast:
        result = ImageEnhance.Contrast(result).enhance(max(0.0, 1.0 + contrast))
    if saturation:
        result = ImageEnhance.Color(result).enhance(max(0.0, 1.0 + saturation))
    return result


def resolve_lut(asset_root: Path, token: str) -> Path:
    """Resolve preset and built-in LUT identifiers inside the managed asset root."""
    root = asset_root.resolve()
    filename = Path(token).name
    candidates = [root / "materials" / "PresetLUTs" / filename]
    prefix = "MIPLResource_DefaultLUTs-"
    if filename.startswith(prefix):
        family_and_name = filename[len(prefix) :]
        family, separator, name = family_and_name.partition("-")
        if separator:
            candidates.append(root / "materials" / "DefaultLUTs" / family / name)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_relative_to(root) and resolved.is_file():
            return resolved
    filename_lower = filename.lower()
    default_root = root / "materials" / "DefaultLUTs"
    if default_root.is_dir():
        for candidate in default_root.rglob("*"):
            if candidate.is_file() and candidate.name.lower() == filename_lower:
                return candidate.resolve()
    raise FileNotFoundError(f"LUT asset is not registered: {token}")
