import numpy as np
from PIL import Image, ImageEnhance

from image_ops.merge.hdr import render_hdr


def test_hdr_identical_frames_are_a_noop() -> None:
    source = Image.new("RGB", (24, 16), (40, 100, 180))

    result = render_hdr([source, source.copy()])

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_hdr_bracket_is_deterministic_and_preserves_display_range() -> None:
    source = Image.fromarray(
        np.tile(np.arange(0, 256, dtype=np.uint8), (32, 1))[..., None].repeat(3, 2),
        "RGB",
    )
    bracket = [
        ImageEnhance.Brightness(source).enhance(factor)
        for factor in (0.5, 1.0, 1.5)
    ]

    first = render_hdr(bracket)
    second = render_hdr(bracket)

    assert np.array_equal(np.asarray(first), np.asarray(second))
    assert np.asarray(first).min() == 0
    assert np.asarray(first).max() == 255
