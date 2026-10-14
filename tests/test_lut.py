from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from image_ops.effects.lut import apply_cube_lut, load_cube_lut, resolve_lut

IDENTITY_CUBE = """LUT_3D_SIZE 2
DOMAIN_MIN 0 0 0
DOMAIN_MAX 1 1 1
0 0 0
1 0 0
0 1 0
1 1 0
0 0 1
1 0 1
0 1 1
1 1 1
"""


def test_cube_lut_uses_standard_channel_order_and_trilinear_interpolation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "identity.cube"
    path.write_text(IDENTITY_CUBE, encoding="utf-8")
    pixels = np.asarray([[[0, 0, 0], [255, 0, 0], [128, 64, 32]]], dtype=np.uint8)

    output = apply_cube_lut(Image.fromarray(pixels, "RGB"), path)

    np.testing.assert_allclose(np.asarray(output), pixels, atol=1)


def test_all_bundled_luts_parse_and_preset_tokens_resolve() -> None:
    asset_root = Path("assets").resolve()
    paths = sorted(
        path
        for path in (asset_root / "materials").rglob("*")
        if path.is_file() and path.suffix.lower() == ".cube"
    )

    assert len(paths) == 99
    for path in paths:
        load_cube_lut(path)
    assert resolve_lut(
        asset_root,
        "MIPLResource_DefaultLUTs-Creative-1960.cube",
    ).is_file()
    assert resolve_lut(
        asset_root,
        "8B87FC53-7E3D-4181-B4EE-89EDBB60970D.cube",
    ).name == "8B87FC53-7E3D-4181-B4EE-89EDBB60970D.cube"
