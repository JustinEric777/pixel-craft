import numpy as np
from PIL import Image

from ai.pipeline.model_service import OnnxModelService
from image_ops.effects.sky_compositor import (
    _edge_extended_layer,
    _fit_texture,
    composite_sky,
)


def test_sky_compositor_blends_only_inside_mask() -> None:
    base = Image.new("RGB", (20, 20), (20, 40, 60))
    texture = Image.new("RGB", (20, 20), (220, 80, 30))
    mask = np.zeros((20, 20), dtype=np.float32)
    mask[:10] = 1.0
    result = np.asarray(composite_sky(base, texture, mask, {"texture_opacity": 1.0}))
    assert tuple(result[2, 2]) == (220, 80, 30)
    assert tuple(result[17, 2]) == (20, 40, 60)


def test_sky_compositor_does_not_mix_black_below_fitted_texture() -> None:
    base = Image.new("RGB", (20, 20), (100, 120, 140))
    texture = Image.new("RGB", (20, 10), (180, 200, 220))
    mask = np.zeros((20, 20), dtype=np.float32)
    mask[10] = 0.5

    result = np.asarray(
        composite_sky(
            base,
            texture,
            mask,
            {
                "texture_opacity": 1.0,
                "horizon_offset": 0.5,
                "edge_refinement": 0.0,
            },
        )
    )

    assert tuple(result[10, 10]) == (139, 159, 179)


def test_sky_compositor_protects_model_detected_foreground() -> None:
    base = Image.new("RGB", (20, 20), (20, 40, 60))
    texture = Image.new("RGB", (20, 20), (220, 80, 30))
    sky = np.ones((20, 20), dtype=np.float32)
    foreground = np.zeros((20, 20), dtype=np.float32)
    foreground[6:14, 6:14] = 1.0

    result = np.asarray(
        composite_sky(
            base,
            texture,
            sky,
            {"texture_opacity": 1.0, "_foreground_mask": foreground},
        )
    )

    assert tuple(result[10, 10]) == (20, 40, 60)
    assert tuple(result[1, 1]) == (220, 80, 30)


def test_sky_compositor_relights_foreground_from_replacement_sky() -> None:
    base = Image.new("RGB", (20, 20), (40, 60, 80))
    texture = Image.new("RGB", (20, 20), (200, 120, 40))
    sky = np.zeros((20, 20), dtype=np.float32)
    sky[:10] = 1.0
    human = np.zeros((20, 20), dtype=np.float32)
    human[10:, 6:14] = 1.0

    without_relight = np.asarray(
        composite_sky(base, texture, sky, {"texture_opacity": 1.0})
    )
    with_relight = np.asarray(
        composite_sky(
            base,
            texture,
            sky,
            {
                "texture_opacity": 1.0,
                "foreground_relight": 1.0,
                "relight_human": 1.0,
                "_foreground_mask": human,
            },
        )
    )

    assert tuple(without_relight[15, 10]) == (40, 60, 80)
    assert tuple(with_relight[15, 10]) != (40, 60, 80)
    assert with_relight[15, 10, 0] > with_relight[15, 1, 0]


def test_sky_compositor_uses_model_boundary_instead_of_horizontal_horizon_cut() -> None:
    base = Image.new("RGB", (20, 20), (40, 100, 150))
    texture = Image.new("RGB", (20, 10))
    for x in range(texture.width):
        value = 80 + x * 8
        for y in range(texture.height):
            texture.putpixel((x, y), (value, value, value))
    mask = np.zeros((20, 20), dtype=np.float32)
    mask[:10] = 1.0
    mask[10:16, :8] = 1.0

    result = np.asarray(
        composite_sky(
            base,
            texture,
            mask,
            {
                "texture_opacity": 1.0,
                "horizon_offset": 0.5,
                "edge_refinement": 0.0,
            },
        )
    )

    assert tuple(result[15, 4]) != (40, 100, 150)
    assert tuple(result[15, 15]) == (40, 100, 150)


def test_sky_texture_extends_only_its_boundary_band() -> None:
    texture = Image.new("RGB", (2, 3))
    for y, value in enumerate((20, 80, 160)):
        for x in range(texture.width):
            texture.putpixel((x, y), (value, value, value))

    layer = np.asarray(_edge_extended_layer(texture, (2, 6), (0, 0)))

    assert layer[:, 0, 0].tolist() == [20, 80, 160, 80, 80, 80]


def test_horizon_blending_does_not_move_the_sky_texture() -> None:
    base = Image.new("RGB", (30, 40), (0, 0, 0))
    texture = Image.new("RGB", (30, 20))
    for y in range(texture.height):
        for x in range(texture.width):
            texture.putpixel((x, y), (x * 8, y * 12, 0))

    sharp = np.asarray(
        _fit_texture(base, texture, {"horizon_offset": 0.5, "horizon_blending": 0})
    )
    soft = np.asarray(
        _fit_texture(base, texture, {"horizon_offset": 0.5, "horizon_blending": 1})
    )

    assert np.array_equal(sharp, soft)


def test_native_horizon_control_is_relative_to_model_detection() -> None:
    base = Image.new("RGB", (30, 40), (0, 0, 0))
    texture = Image.new("RGB", (30, 20))
    for y in range(texture.height):
        for x in range(texture.width):
            texture.putpixel((x, y), (x * 8, y * 12, 0))

    native = np.asarray(
        _fit_texture(
            base,
            texture,
            {
                "_detected_horizon": 0.3,
                "horizon_offset": 0.58,
                "sky_scale": 1.0,
            },
        )
    )
    explicit = np.asarray(
        _fit_texture(base, texture, {"horizon_offset": 0.3, "sky_scale": 1.3})
    )

    assert np.array_equal(native, explicit)


def test_sky_softmax_flat_output_becomes_class_one_mask(tmp_path) -> None:
    service = object.__new__(OnnxModelService)
    probabilities = np.zeros((4, 2), dtype=np.float32)
    probabilities[:, 0] = 0.25
    probabilities[:, 1] = 0.75
    service._run = lambda *_args, **_kwargs: type(
        "Result", (), {"data": {"softmax": probabilities}}
    )()

    mask = service._mask_array(Image.new("RGB", (2, 2)), "sky", (2, 2))

    assert mask.shape == (2, 2)
    assert np.allclose(mask, 0.75, atol=1 / 255)


def test_single_mask_analysis_accepts_flat_probability_output() -> None:
    service = object.__new__(OnnxModelService)
    probabilities = np.zeros((4, 2), dtype=np.float32)
    probabilities[:, 0] = 0.1
    probabilities[:, 1] = 0.9
    service._run = lambda *_args, **_kwargs: type(
        "Result", (), {"data": {"softmax": probabilities}}
    )()

    result = service._single_mask(Image.new("RGB", (2, 2)), "sky-water", (2, 2))

    assert result["status"] == "ready"
    assert result["shape"] == [2, 2]
    assert result["mean"] > 0.89


def test_mask_analysis_accepts_wrapper_normalized_2d_mask() -> None:
    service = object.__new__(OnnxModelService)
    mask = np.full((2, 2), 0.65, dtype=np.float32)
    service._run = lambda *_args, **_kwargs: type(
        "Result", (), {"data": {"mask": mask}}
    )()

    result = service._mask(Image.new("RGB", (4, 3)), "salient", (2, 2))

    assert result["status"] == "ready"
    assert result["shape"] == [3, 4]
    assert np.isclose(result["mean"], 0.65, atol=1 / 255)


def test_mask_array_does_not_apply_softmax_twice_to_probability_output() -> None:
    service = object.__new__(OnnxModelService)
    probabilities = np.zeros((1, 2, 2, 2), dtype=np.float32)
    probabilities[:, 0] = 0.8
    probabilities[:, 1] = 0.2
    probabilities[:, 1, 0, 0] = 0.9
    probabilities[:, 0, 0, 0] = 0.1
    service._run = lambda *_args, **_kwargs: type(
        "Result", (), {"data": {"Decoder/softmax": probabilities}}
    )()

    mask = service._mask_array(Image.new("RGB", (2, 2)), "sky", (2, 2))

    assert np.isclose(mask[0, 0], 0.9, atol=1 / 255)
    assert np.isclose(mask[1, 1], 0.2, atol=1 / 255)
