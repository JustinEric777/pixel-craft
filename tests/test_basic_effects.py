import numpy as np
from PIL import Image, ImageEnhance

from image_ops.effects import basic
from image_ops.effects.basic import apply_effect


def test_black_white_requires_conversion_and_preserves_signed_channel_response() -> None:
    image = Image.new("RGB", (3, 1))
    image.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255)])

    untouched = apply_effect(image, "bw_channels", {"amount": 0.0, "converted": False})
    neutral = apply_effect(image, "bw_channels", {"amount": 0.0, "converted": True})
    negative = apply_effect(image, "bw_channels", {"amount": -1.0})
    positive = apply_effect(image, "bw_channels", {"amount": 1.0})

    np.testing.assert_array_equal(np.asarray(untouched), np.asarray(image))
    assert np.all(np.asarray(neutral)[..., 0] == np.asarray(neutral)[..., 1])
    assert np.all(np.asarray(neutral)[..., 1] == np.asarray(neutral)[..., 2])
    assert np.asarray(negative)[0, 0, 0] < np.asarray(neutral)[0, 0, 0]
    assert np.asarray(positive)[0, 0, 0] > np.asarray(neutral)[0, 0, 0]


def test_lut_mapping_maps_the_canonical_abstract_amount_to_full_native_strength(
    monkeypatch,
) -> None:
    strengths: list[float] = []

    def fake_apply_cube_lut(image, path, *, amount, contrast, saturation):
        strengths.append(amount)
        return image

    monkeypatch.setattr(basic, "apply_cube_lut", fake_apply_cube_lut)
    source = Image.new("RGB", (2, 2), (60, 120, 180))

    apply_effect(source, "lut_mapping", {"amount": 0.2, "_lut_path": "test.cube"})
    apply_effect(source, "lut_mapping", {"amount": 0.4, "_lut_path": "test.cube"})
    apply_effect(source, "lut_mapping", {"amount": 1.0, "_lut_path": "test.cube"})

    assert strengths == [0.5, 1.0, 1.0]


def _gradient(image: Image.Image) -> float:
    values = np.asarray(image.convert("RGB"), dtype=np.float32)
    return float(np.abs(np.diff(values, axis=1)).mean())


def test_negative_details_suppresses_small_detail_without_global_contrast_shift() -> None:
    pixels = np.indices((32, 32)).sum(axis=0) % 2 * 80 + 80
    source = Image.fromarray(np.repeat(pixels[:, :, None], 3, axis=2).astype(np.uint8))

    result = apply_effect(source, "details", {"amount": -1.0})

    assert _gradient(result) < _gradient(source)
    assert abs(float(np.asarray(result).mean()) - float(np.asarray(source).mean())) < 1.0


def test_denoise_laplacian_maps_smoke_anchor_to_full_native_response() -> None:
    pixels = np.indices((32, 32)).sum(axis=0) % 2 * 80 + 80
    source = Image.fromarray(np.repeat(pixels[:, :, None], 3, axis=2).astype(np.uint8))

    smoke = apply_effect(source, "denoise_laplacian", {"amount": 0.4})
    full = apply_effect(source, "denoise_laplacian", {"amount": 1.0})

    assert np.array_equal(np.asarray(smoke), np.asarray(full))


def test_color_adjustments_uses_luminar_calibrated_color_and_contrast_response() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "color_adjustments", {"amount": 0.4})
    negative = apply_effect(source, "color_adjustments", {"amount": -1.0})
    neutral = apply_effect(source, "color_adjustments", {"amount": 0.0})

    assert not np.array_equal(np.asarray(result), np.asarray(source))
    assert np.array_equal(np.asarray(neutral), np.asarray(source))
    assert np.all(np.asarray(negative)[..., 0] == np.asarray(negative)[..., 1])
    assert np.all(np.asarray(negative)[..., 1] == np.asarray(negative)[..., 2])


def test_high_key_uses_calibrated_monotonic_tone_response() -> None:
    source = Image.new("RGB", (4, 4), (80, 120, 160))

    result = apply_effect(source, "high_key", {"amount": 0.4})
    full = apply_effect(source, "high_key", {"amount": 1.0})
    neutral = apply_effect(source, "high_key", {"amount": 0.0})

    assert np.array_equal(np.asarray(neutral), np.asarray(source))
    assert not np.array_equal(np.asarray(result), np.asarray(source))
    assert not np.array_equal(np.asarray(full), np.asarray(result))


def test_default_effects_uses_develop_lift_and_highlight_compression() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "default_effects", {"amount": 0.4})
    expected = ImageEnhance.Contrast(
        ImageEnhance.Brightness(source).enhance(1.0 + 0.4 * 1.0625)
    ).enhance(1.0 - 0.4 * 0.3125)

    assert np.array_equal(np.asarray(result), np.asarray(expected))


def test_default_effects_zero_amount_is_noop() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "default_effects", {"amount": 0.0})

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_default_effects_signed_endpoints_preserve_native_tonal_order() -> None:
    ramp = np.arange(256, dtype=np.uint8)[None, :, None]
    source = Image.fromarray(np.repeat(ramp, 3, axis=2), "RGB")

    negative = np.asarray(apply_effect(source, "default_effects", {"amount": -1.0}))
    smoke = np.asarray(apply_effect(source, "default_effects", {"amount": 0.4}))
    positive = np.asarray(apply_effect(source, "default_effects", {"amount": 1.0}))

    assert np.any(negative > 0)
    assert np.all(np.diff(negative[0, :, 0].astype(np.int16)) >= 0)
    assert float(negative.mean()) < float(np.asarray(source).mean())
    assert float(positive.mean()) > float(smoke.mean())


def test_pro_contrast_zero_amount_is_noop() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "pro_contrast", {"amount": 0.0})

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_pro_contrast_uses_a_monotonic_content_adaptive_tone_curve() -> None:
    ramp = np.arange(256, dtype=np.uint8)[None, :, None]
    source = Image.fromarray(np.repeat(ramp, 3, axis=2), "RGB")

    result = np.asarray(apply_effect(source, "pro_contrast", {"amount": 0.4}))

    assert np.all(np.diff(result[0, :, 0].astype(np.int16)) >= 0)
    assert float(result.mean()) < float(np.asarray(source).mean())


def test_pro_contrast_continues_native_response_above_smoke_anchor() -> None:
    ramp = np.arange(256, dtype=np.uint8)[None, :, None]
    source = Image.fromarray(np.repeat(ramp, 3, axis=2), "RGB")

    smoke = np.asarray(apply_effect(source, "pro_contrast", {"amount": 0.4}))
    full = np.asarray(apply_effect(source, "pro_contrast", {"amount": 1.0}))

    assert not np.array_equal(full, smoke)
    assert float(full.mean()) < float(smoke.mean())


def test_blue_hour_zero_amount_is_noop() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "blue_hour", {"amount": 0.0})

    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_blue_hour_uses_monotonic_native_calibrated_tone_curves() -> None:
    ramp = np.arange(256, dtype=np.uint8)[None, :, None]
    source = Image.fromarray(np.repeat(ramp, 3, axis=2), "RGB")

    result = np.asarray(apply_effect(source, "blue_hour", {"amount": 0.4}))

    for channel in range(3):
        assert np.all(np.diff(result[0, :, channel].astype(np.int16)) >= 0)
    assert float(result.mean()) < float(np.asarray(source).mean())


def test_positive_vignette_brightens_only_the_feathered_outer_region() -> None:
    source = Image.new("RGB", (101, 101), (100, 100, 100))

    result = np.asarray(apply_effect(source, "vignette", {"amount": 0.4}))

    np.testing.assert_array_equal(result[50, 50], [100, 100, 100])
    assert int(result[0, 0, 0]) > 100
    assert int(result[25, 50, 0]) == 100


def test_negative_vignette_darkens_only_the_feathered_outer_region() -> None:
    source = Image.new("RGB", (101, 101), (100, 100, 100))

    result = np.asarray(apply_effect(source, "vignette", {"amount": -1.0}))

    np.testing.assert_array_equal(result[50, 50], [100, 100, 100])
    assert int(result[0, 0, 0]) < 100
    assert int(result[25, 50, 0]) == 100


def test_radiance_softens_detail_and_raises_luminance() -> None:
    pixels = np.indices((32, 32)).sum(axis=0) % 2 * 80 + 80
    source = Image.fromarray(np.repeat(pixels[:, :, None], 3, axis=2).astype(np.uint8))

    result = apply_effect(source, "radiance", {"amount": 0.4})

    assert _gradient(result) < _gradient(source)
    assert float(np.asarray(result).mean()) > float(np.asarray(source).mean())


def test_fade_uses_warm_lift_and_restores_contrast() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "fade", {"amount": 0.4})
    full = apply_effect(source, "fade", {"amount": 1.0})
    neutral = apply_effect(source, "fade", {"amount": 0.0})

    assert np.array_equal(np.asarray(neutral), np.asarray(source))
    assert not np.array_equal(np.asarray(result), np.asarray(source))
    assert not np.array_equal(np.asarray(full), np.asarray(result))


def test_grain_preserves_smoke_anchor_and_calibrates_full_variance() -> None:
    source = Image.new("RGB", (256, 256), (128, 128, 128))

    smoke = np.asarray(apply_effect(source, "grain", {"amount": 0.4}), dtype=np.float32)
    full = np.asarray(apply_effect(source, "grain", {"amount": 1.0}), dtype=np.float32)
    source_array = np.asarray(source, dtype=np.float32)

    smoke_std = float((smoke - source_array).std())
    full_std = float((full - source_array).std())
    assert 1.8 < full_std / smoke_std < 2.2
    assert float((full[..., 0] - source_array[..., 0]).mean()) < 0.0


def test_color_enhancer_increases_color_separation_without_global_lift() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "color_enhancer", {"amount": 0.4})
    neutral = apply_effect(source, "color_enhancer", {"amount": 0.0})

    assert np.array_equal(np.asarray(neutral), np.asarray(source))
    assert not np.array_equal(np.asarray(result), np.asarray(source))
    assert int(np.ptp(np.asarray(result)[0, 0])) > int(np.ptp(np.asarray(source)[0, 0]))


def test_color_toning_uses_calibrated_warm_channel_response() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "color_toning", {"amount": 0.4})
    full = apply_effect(source, "color_toning", {"amount": 1.0})
    neutral = apply_effect(source, "color_toning", {"amount": 0.0})

    assert np.array_equal(np.asarray(neutral), np.asarray(source))
    assert np.array_equal(np.asarray(result), np.asarray(full))
    assert not np.array_equal(np.asarray(result), np.asarray(source))


def test_complex_bleach_desaturates_then_restores_tone() -> None:
    source = Image.new("RGB", (4, 4), (60, 120, 180))

    result = apply_effect(source, "complex_bleach", {"amount": 0.4})
    gray = source.convert("L").convert("RGB")
    expected = ImageEnhance.Brightness(
        ImageEnhance.Contrast(Image.blend(source, gray, 0.4 * 0.8)).enhance(
            1.0 + 0.4 * 0.1
        )
    ).enhance(1.0 + 0.4 * 0.2)

    assert np.array_equal(np.asarray(result), np.asarray(expected))


def test_glow_orton_softens_detail_and_adds_glow() -> None:
    pixels = np.indices((32, 32)).sum(axis=0) % 2 * 80 + 80
    source = Image.fromarray(np.repeat(pixels[:, :, None], 3, axis=2).astype(np.uint8))

    result = apply_effect(source, "glow_orton", {"amount": 0.4})

    assert _gradient(result) < _gradient(source)
    assert float(np.asarray(result).mean()) > float(np.asarray(source).mean())


def test_grain_matches_luminar_noise_scale_without_color_bias() -> None:
    source = Image.new("RGB", (128, 128), (96, 128, 160))

    result = apply_effect(source, "grain", {"amount": 0.4})
    delta = np.asarray(result, dtype=np.float32) - np.asarray(source, dtype=np.float32)

    assert 15.0 < float(delta[..., 0].std()) < 18.0
    assert abs(float(delta.mean())) < 1.0
    np.testing.assert_allclose(delta[..., 0], delta[..., 1], atol=0.0)
    np.testing.assert_allclose(delta[..., 1], delta[..., 2], atol=0.0)


def test_new_neon_light_requires_explicit_positioned_stroke() -> None:
    source = Image.new("RGB", (64, 64), (10, 20, 30))

    try:
        apply_effect(source, "new_neon_light", {"amount": 0.4, "strokes": []})
    except ValueError as exc:
        assert "positioned stroke" in str(exc)
    else:
        raise AssertionError("neon rendering must fail closed without geometry")


def test_new_neon_light_uses_normalized_stroke_and_native_amount_anchor() -> None:
    source = Image.new("RGB", (100, 80), (10, 20, 30))
    parameters = {
        "amount": 0.4,
        "strokes": [{"points": [[0.2, 0.25], [0.8, 0.75]]}],
        "neon_hue": 270.0,
        "neon_spread": 0.6,
        "neon_atmosphere": 0.05,
        "neon_whiteness": 0.3,
    }

    result = np.asarray(apply_effect(source, "new_neon_light", parameters))

    assert result.shape == (80, 100, 3)
    assert result[40, 50].mean() > 180.0
    assert result[0, 99].mean() < 25.0
