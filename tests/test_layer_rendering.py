import numpy as np
from PIL import Image

from image_ops.effects.basic import composite_image_layer


def test_screen_layer_uses_source_opacity() -> None:
    base = Image.new("RGB", (4, 4), (64, 128, 192))
    layer = Image.new("RGB", (4, 4), (128, 0, 64))
    result = np.asarray(
        composite_image_layer(base, layer, opacity=0.5, mode="screen")
    )
    base_pixel = np.array([64, 128, 192], dtype=np.float32) / 255.0
    layer_pixel = np.array([128, 0, 64], dtype=np.float32) / 255.0
    screen = 1.0 - (1.0 - base_pixel) * (1.0 - layer_pixel)
    expected = np.floor((base_pixel * 0.5 + screen * 0.5) * 255.0 + 0.5).astype(np.uint8)
    assert np.max(np.abs(result[0, 0].astype(int) - expected.astype(int))) <= 1


def test_image_layer_preserves_canvas_size_after_cover_fit() -> None:
    base = Image.new("RGB", (120, 80), (20, 30, 40))
    portrait_layer = Image.new("RGB", (30, 90), (220, 100, 40))
    result = composite_image_layer(
        base,
        portrait_layer,
        opacity=0.75,
        mode="screen",
        scale=1.2,
        rotation=17,
    )
    assert result.size == base.size
    assert np.asarray(result).mean() > np.asarray(base).mean()


def test_library_texture_can_stretch_to_the_canvas() -> None:
    base = Image.new("RGB", (120, 80), (0, 0, 0))
    layer = Image.new("RGB", (20, 60))
    pixels = np.asarray(layer).copy()
    pixels[:, :10] = (255, 0, 0)
    pixels[:, 10:] = (0, 0, 255)

    result = composite_image_layer(
        base,
        Image.fromarray(pixels),
        opacity=1.0,
        mode="normal",
        stretch=True,
    )

    assert result.size == base.size
    np.testing.assert_array_equal(np.asarray(result)[40, 5], [255, 0, 0])
    np.testing.assert_array_equal(np.asarray(result)[40, -5], [0, 0, 255])


def test_image_layer_mask_limits_the_composite_to_the_white_region() -> None:
    base = Image.new("RGB", (8, 4), (20, 30, 40))
    layer = Image.new("RGB", (8, 4), (220, 120, 40))
    mask = Image.new("L", (8, 4), 0)
    mask.paste(255, (0, 0, 4, 4))

    result = np.asarray(
        composite_image_layer(
            base,
            layer,
            opacity=1.0,
            mode="normal",
            stretch=True,
            mask=mask,
        )
    )

    np.testing.assert_array_equal(result[1, 1], [220, 120, 40])
    np.testing.assert_array_equal(result[1, 6], [20, 30, 40])
