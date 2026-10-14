from types import SimpleNamespace

import numpy as np
from PIL import Image

from ai.pipeline.image_effect_pipelines import ImageEffectPipelinesMixin


def test_adaptive_enhance_zero_amount_is_noop() -> None:
    source = Image.fromarray(
        np.arange(12 * 10 * 3, dtype=np.uint8).reshape(10, 12, 3), "RGB"
    )

    result = ImageEffectPipelinesMixin._apply_adaptive_enhance(source, 0.0)

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_adaptive_enhance_preserves_size_and_monotonic_tone_order() -> None:
    ramp = np.arange(256, dtype=np.uint8)[None, :, None]
    source = Image.fromarray(np.repeat(ramp, 3, axis=2), "RGB")

    result = ImageEffectPipelinesMixin._apply_adaptive_enhance(source, 0.4)
    values = np.asarray(result, dtype=np.int16)[0]

    assert result.size == source.size
    assert np.all(np.diff(values, axis=0) >= 0)


def test_structure_ai_zero_amount_is_noop() -> None:
    source = Image.fromarray(
        np.arange(12 * 10 * 3, dtype=np.uint8).reshape(10, 12, 3), "RGB"
    )

    result = ImageEffectPipelinesMixin._apply_structure_ai(source, 0.0)

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_structure_ai_curve_is_monotonic() -> None:
    ramp = np.arange(256, dtype=np.uint8)[None, :, None]
    source = Image.fromarray(np.repeat(ramp, 3, axis=2), "RGB")

    result = ImageEffectPipelinesMixin._apply_structure_ai(source, 0.4)

    assert np.all(np.diff(np.asarray(result, dtype=np.int16)[0], axis=0) >= 0)


def test_landscape_enhancer_zero_amount_is_noop() -> None:
    source = Image.fromarray(
        np.arange(12 * 10 * 3, dtype=np.uint8).reshape(10, 12, 3), "RGB"
    )

    result = ImageEffectPipelinesMixin._apply_landscape_enhancer(source, 0.0)

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_landscape_enhancer_curve_is_monotonic() -> None:
    ramp = np.arange(256, dtype=np.uint8)[None, :, None]
    source = Image.fromarray(np.repeat(ramp, 3, axis=2), "RGB")

    result = ImageEffectPipelinesMixin._apply_landscape_enhancer(source, 0.4)

    assert np.all(np.diff(np.asarray(result, dtype=np.int16)[0], axis=0) >= 0)


def test_quantile_color_match_maps_channel_ranges_monotonically() -> None:
    source = np.linspace(0.0, 1.0, 48, dtype=np.float32).reshape(4, 4, 3)
    reference = np.linspace(0.2, 0.8, 75, dtype=np.float32).reshape(5, 5, 3)

    result = ImageEffectPipelinesMixin._quantile_color_match(source, reference)

    assert result.shape == source.shape
    for channel in range(3):
        order = np.argsort(source[..., channel], axis=None)
        assert np.all(np.diff(result[..., channel].ravel()[order]) >= 0)


def test_quantile_color_match_rejects_non_rgb_arrays() -> None:
    source = np.zeros((2, 2), dtype=np.float32)
    reference = np.zeros((2, 2, 3), dtype=np.float32)

    try:
        ImageEffectPipelinesMixin._quantile_color_match(source, reference)
    except ValueError as exc:
        assert "HWC" in str(exc)
    else:
        raise AssertionError("non-RGB source must fail closed")


def test_face_ai_zero_amount_is_noop() -> None:
    source = Image.new("RGB", (32, 24), (90, 100, 110))
    boxes = np.array([[0.2, 0.2, 0.8, 0.8]], dtype=np.float32)

    result = ImageEffectPipelinesMixin._apply_face_ai(source, boxes, 0.0)

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_face_ai_uses_foreground_mask_for_subject_wide_enhancement() -> None:
    source = Image.new("RGB", (64, 64), (80, 80, 80))
    boxes = np.array([[0.2, 0.2, 0.8, 0.8]], dtype=np.float32)
    foreground = np.zeros((64, 64), dtype=np.float32)
    foreground[:, :32] = 1.0

    result = ImageEffectPipelinesMixin._apply_face_ai(
        source,
        boxes,
        0.5,
        foreground=foreground,
    )
    pixels = np.asarray(result, dtype=np.float32)

    assert pixels[:, :24].mean() > 100.0
    assert np.array_equal(pixels[:, 56:], np.asarray(source)[:, 56:])


def test_slim_people_rejects_mask_that_would_warp_most_of_the_frame() -> None:
    source = Image.fromarray(
        np.arange(64 * 48 * 3, dtype=np.uint8).reshape(48, 64, 3), "RGB"
    )
    leaked_mask = np.ones((48, 64), dtype=np.float32)

    result = ImageEffectPipelinesMixin._horizontal_body_warp(source, leaked_mask, 0.4)

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_magic_lights_zero_amount_is_noop() -> None:
    source = Image.new("RGB", (96, 96), (10, 20, 30))
    boxes = np.array([[0.45, 0.45, 0.55, 0.55]], dtype=np.float32)

    result = ImageEffectPipelinesMixin._apply_detected_lights(
        source, boxes, np.array([1.0], dtype=np.float32), 0.0
    )

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_magic_lights_renders_warm_eight_point_starburst() -> None:
    source = Image.new("RGB", (160, 160), (10, 20, 30))
    boxes = np.array([[0.45, 0.45, 0.55, 0.55]], dtype=np.float32)

    result = np.asarray(
        ImageEffectPipelinesMixin._apply_detected_lights(
            source, boxes, np.array([1.0], dtype=np.float32), 0.4
        )
    )

    assert result[80, 80].mean() > 180.0
    assert result[80, 95, 0] - 10 > result[80, 95, 2] - 30
    assert result[65, 95].mean() > result[25, 25].mean()


def test_denoise_zero_amount_is_a_noop_without_invoking_the_model() -> None:
    source = Image.fromarray(
        np.arange(12 * 10 * 3, dtype=np.uint8).reshape(10, 12, 3), "RGB"
    )
    service = object.__new__(ImageEffectPipelinesMixin)
    service.registry = type("Registry", (), {"records": {"model_luminocity_denoise": object()}})()
    service._run = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("zero denoise must not invoke the model")
    )

    result = service._denoise_luminance(source, 0.0)

    assert result is not None
    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_abstract_denoise_full_amount_uses_native_middle_profile() -> None:
    source = Image.new("RGB", (8, 8), (90, 100, 110))
    service = object.__new__(ImageEffectPipelinesMixin)
    service.registry = type("Registry", (), {"records": {}})()
    service._resolve_model_id = lambda value: value
    observed: list[tuple[float, float, float]] = []
    service._denoise_luminance = (
        lambda image, amount, *, details, sharpness: (
            observed.append((amount, details, sharpness)) or image
        )
    )

    result = service.apply_image_effect(source, "denoise", {"amount": 1.0})

    assert result is source
    assert observed == [(0.6, 0.0, 0.0)]


def test_face_enhancer_zero_amount_is_a_noop_without_invoking_the_model() -> None:
    source = Image.fromarray(
        np.arange(12 * 10 * 3, dtype=np.uint8).reshape(10, 12, 3), "RGB"
    )
    service = object.__new__(ImageEffectPipelinesMixin)
    model_id = "GFPGANv1.3_2023"
    service.registry = type("Registry", (), {"records": {model_id: object()}})()
    service._resolve_model_id = lambda _value: model_id
    service._restore_rgb = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("zero face enhancement must not invoke the model")
    )

    result = service.apply_image_effect(source, "face_enhancer", {"amount": 0.0})

    assert result is not None
    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_depth_volume_zero_amount_is_identity() -> None:
    source = Image.fromarray(
        np.arange(12 * 10 * 3, dtype=np.uint8).reshape(10, 12, 3), "RGB"
    )
    depth = np.linspace(0.0, 1.0, 120, dtype=np.float32).reshape(10, 12)
    service = object.__new__(ImageEffectPipelinesMixin)

    result = service._apply_depth_effect(source, "depth_volume", depth, 0.0)

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_depth_volume_full_strength_keeps_calibrated_depth_response() -> None:
    source = Image.new("RGB", (2, 1), (100, 100, 100))
    depth = np.asarray([[0.0, 1.0]], dtype=np.float32)
    service = object.__new__(ImageEffectPipelinesMixin)

    result = np.asarray(
        service._apply_depth_effect(source, "depth_volume", depth, 1.0)
    )

    assert result[0, 0].tolist() == [85, 85, 85]
    assert result[0, 1].tolist() == [145, 145, 145]


def test_fog_uses_vertical_atmosphere_and_protects_foreground() -> None:
    source = Image.new("RGB", (20, 20), (40, 60, 80))
    depth = np.zeros((20, 20), dtype=np.float32)
    foreground = np.zeros((20, 20), dtype=np.float32)
    foreground[:10, :10] = 1.0
    service = object.__new__(ImageEffectPipelinesMixin)

    result = np.asarray(
        service._apply_depth_effect(
            source,
            "fog",
            depth,
            1.0,
            foreground=foreground,
        )
    )

    assert result[2, 15].mean() > result[15, 15].mean()
    assert result[2, 2].mean() < result[2, 15].mean()


def test_bokeh_zero_is_identity_without_invoking_segmentation() -> None:
    source = Image.new("RGB", (20, 20), (40, 60, 80))
    service = object.__new__(ImageEffectPipelinesMixin)
    model_id = "mobilenet_exp78_portrait_BOKEH12"
    service.registry = type("Registry", (), {"records": {model_id: object()}})()
    service._resolve_model_id = lambda _value: model_id
    service._mask_array = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("zero Bokeh must not invoke segmentation")
    )

    result = service.apply_image_effect(source, "bokeh_ai", {"amount": 0.0})

    assert result is not None
    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_bokeh_saturates_at_native_smoke_anchor() -> None:
    pixels = np.indices((40, 40)).sum(axis=0) % 2 * 120 + 40
    source = Image.fromarray(np.repeat(pixels[:, :, None], 3, axis=2).astype(np.uint8))
    service = object.__new__(ImageEffectPipelinesMixin)
    model_id = "mobilenet_exp78_portrait_BOKEH12"
    service.registry = type("Registry", (), {"records": {model_id: object()}})()
    service._resolve_model_id = lambda _value: model_id
    service._mask_array = lambda *_args, **_kwargs: np.zeros((40, 40), dtype=np.float32)

    smoke = service.apply_image_effect(source, "bokeh_ai", {"amount": 0.4})
    full = service.apply_image_effect(source, "bokeh_ai", {"amount": 1.0})

    assert smoke is not None and full is not None
    assert np.array_equal(np.asarray(smoke), np.asarray(full))


def test_bokeh_shape_changes_the_blur_response() -> None:
    pixels = np.indices((40, 40)).sum(axis=0) % 2 * 120 + 40
    source = Image.fromarray(np.repeat(pixels[:, :, None], 3, axis=2).astype(np.uint8))
    service = object.__new__(ImageEffectPipelinesMixin)
    model_id = "mobilenet_exp78_portrait_BOKEH12"
    service.registry = type("Registry", (), {"records": {model_id: object()}})()
    service._resolve_model_id = lambda _value: model_id
    service._mask_array = lambda *_args, **_kwargs: np.zeros((40, 40), dtype=np.float32)

    circle = service.apply_image_effect(
        source, "bokeh_ai", {"amount": 0.4, "bokeh_shape": "circle"}
    )
    filled = service.apply_image_effect(
        source, "bokeh_ai", {"amount": 0.4, "bokeh_shape": "filled_circle"}
    )

    assert circle is not None and filled is not None
    assert not np.array_equal(np.asarray(circle), np.asarray(filled))


def test_face_enhancer_saturates_at_native_smoke_anchor() -> None:
    source = Image.new("RGB", (20, 20), (40, 60, 80))
    restored = Image.new("RGB", source.size, (100, 120, 140))
    service = object.__new__(ImageEffectPipelinesMixin)
    model_id = "GFPGANv1.3_2023"
    service.registry = type("Registry", (), {"records": {model_id: object()}})()
    service._resolve_model_id = lambda _value: model_id
    service._restore_rgb = lambda *_args, **_kwargs: restored

    smoke = service.apply_image_effect(source, "face_enhancer", {"amount": 0.4})
    full = service.apply_image_effect(source, "face_enhancer", {"amount": 1.0})

    assert smoke is not None and full is not None
    assert np.array_equal(np.asarray(smoke), np.asarray(full))


def test_slim_people_saturates_at_native_smoke_anchor() -> None:
    source = Image.fromarray(
        np.arange(40 * 40 * 3, dtype=np.uint8).reshape(40, 40, 3), "RGB"
    )
    labels = np.zeros((40, 40), dtype=np.int64)
    labels[:, 12:28] = 1
    service = object.__new__(ImageEffectPipelinesMixin)
    model_id = "human_clothes_exp13_v2"
    service.registry = type("Registry", (), {"records": {model_id: object()}})()
    service._resolve_model_id = lambda _value: model_id
    service._run = lambda *_args, **_kwargs: SimpleNamespace(data={"labels": labels})

    smoke = service.apply_image_effect(source, "slim_people", {"amount": 0.4})
    full = service.apply_image_effect(source, "slim_people", {"amount": 1.0})

    assert smoke is not None and full is not None
    assert np.array_equal(np.asarray(smoke), np.asarray(full))


def test_crop_ai_invokes_saliency_model_and_applies_normalized_crop() -> None:
    source = Image.new("RGB", (100, 80), (90, 100, 110))
    service = object.__new__(ImageEffectPipelinesMixin)
    model_id = "saliency_map_opset9_billinear_upsampling_keras_tensorflow_i8"
    service.registry = type("Registry", (), {"records": {model_id: object()}})()
    calls: list[tuple[str, tuple[int, int]]] = []
    service._resolve_model_id = lambda value: value

    def run(_image: Image.Image, selected_model: str, *, size: tuple[int, int]):
        calls.append((selected_model, size))
        return SimpleNamespace(data={"mask": np.ones((256, 256), dtype=np.float32)})

    service._run = run

    result = service.apply_image_effect(
        source,
        "crop_ai",
        {"crop_box": [0.25, 0.25, 0.75, 0.75]},
    )

    assert calls == [(model_id, (256, 256))]
    assert result is not None
    assert result.size == (50, 40)
