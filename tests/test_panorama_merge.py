import numpy as np
from PIL import Image

from image_ops.merge.panorama import (
    best_overlap,
    project_native_boundary,
    render_panorama,
)


def _textured_frame(width: int = 120, height: int = 48) -> np.ndarray:
    return np.random.default_rng(20260825).integers(
        0, 256, size=(height, width, 3), dtype=np.uint8
    )


def test_best_overlap_refines_beyond_coarse_search_step() -> None:
    source = _textured_frame()
    left = source[:, :80].astype(np.float32) / 255.0
    right = source[:, 37:].astype(np.float32) / 255.0

    assert best_overlap(left, right) == 43


def test_panorama_reconstructs_translated_crops_without_width_drift() -> None:
    source = _textured_frame()
    images = [
        Image.fromarray(source[:, start : start + 80], "RGB")
        for start in (0, 20, 40)
    ]

    result = render_panorama(images)

    assert result.size == (119, 47)


def test_native_boundary_is_a_crop_not_a_resample() -> None:
    source = np.zeros((1440, 1080, 3), dtype=np.uint8)
    source[2, 6] = (17, 29, 43)

    result = project_native_boundary(Image.fromarray(source, "RGB"))

    assert result.size == (1070, 1410)
    assert result.getpixel((0, 0)) == (17, 29, 43)
