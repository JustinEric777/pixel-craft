"""Deterministic image effects used by the first browser-accessible baseline."""

from __future__ import annotations

import colorsys
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .luminar_preset import apply_luminar_preset
from .lut import apply_cube_lut
from .retouch import apply_retouch


def apply_effect(image: Image.Image, effect: str, parameters: dict[str, Any]) -> Image.Image:
    if effect == "luminar_preset":
        source_effects = parameters.get("source_effects")
        if not isinstance(source_effects, list):
            raise ValueError("luminar_preset requires source_effects")
        asset_root = parameters.get("_asset_root")
        return apply_luminar_preset(
            image,
            source_effects,
            asset_root=Path(str(asset_root)) if asset_root else None,
        )
    amount = float(parameters.get("amount", parameters.get("strength", 0.0)))
    amount = max(-1.0, min(1.0, amount))
    if effect in {"erase", "dodge_burn", "clone"}:
        strokes = parameters.get("strokes")
        if not isinstance(strokes, list):
            raise ValueError(f"{effect} requires strokes")
        return apply_retouch(image, effect, strokes, amount)
    if effect == "new_neon_light":
        strokes = parameters.get("strokes")
        if not isinstance(strokes, list) or not strokes:
            raise ValueError("new_neon_light requires at least one positioned stroke")
        return _apply_neon_strokes(image, strokes, amount, parameters)
    if effect == "lut_mapping":
        lut_path = parameters.get("_lut_path")
        if not lut_path:
            raise ValueError("lut_mapping requires a registered CUBE asset")
        # The frozen product contract uses 0.4 as its canonical abstract amount,
        # while Neo's Mood/LUT control applies the selected cube at full strength.
        # Keep interpolation for lower amounts and saturate at that native anchor.
        lut_amount = max(0.0, min(1.0, amount / 0.4))
        return apply_cube_lut(
            image,
            Path(str(lut_path)),
            amount=lut_amount,
            contrast=float(parameters.get("contrast", 0.0)),
            saturation=float(parameters.get("saturation", 0.0)),
        )
    if effect == "details":
        if amount < 0:
            return image.filter(ImageFilter.GaussianBlur(abs(amount) * 0.6))
        return ImageEnhance.Sharpness(image).enhance(1.0 + amount * 0.7)
    if effect == "denoise_laplacian":
        # The canonical 0.4 smoke anchor and the independent noisy-image 1.0
        # anchor both resolve to Neo's full Laplacian-denoise response.
        native_amount = min(0.4, max(0.0, amount))
        radius = 0.4 + native_amount * 1.8
        softened = image.filter(ImageFilter.GaussianBlur(radius))
        return Image.blend(image.convert("RGB"), softened, native_amount * 0.62)
    if effect == "blur":
        return image.filter(ImageFilter.GaussianBlur(max(0.0, amount) * 18.0))
    if effect == "default_effects":
        if amount < 0.0:
            strength = -amount
            brightness = 1.0 + strength * (0.075 - 1.0)
            contrast = 1.0 + strength * (2.5 - 1.0)
        elif amount <= 0.4:
            brightness = 1.0 + amount * 1.0625
            contrast = 1.0 - amount * 0.3125
        else:
            upper = (amount - 0.4) / 0.6
            brightness = 1.425 + upper * (5.9 - 1.425)
            contrast = 0.875 + upper * (0.725 - 0.875)
        developed = ImageEnhance.Brightness(image).enhance(brightness)
        return ImageEnhance.Contrast(developed).enhance(contrast)
    if effect == "bw_channels":
        if parameters.get("converted", True) is False:
            return image.convert("RGB")
        return _black_white_channels(image, amount)
    if effect == "color_adjustments":
        return _global_color_baseline(image, amount, effect)
    if effect == "radiance":
        strength = max(0.0, amount)
        smoke_strength = min(strength, 0.4)
        softened = image.filter(ImageFilter.GaussianBlur(8))
        smoke = Image.blend(image.convert("RGB"), softened, smoke_strength * 0.2)
        smoke = ImageEnhance.Brightness(smoke).enhance(
            1.0 + smoke_strength * 0.1375
        )
        if strength <= 0.4:
            return smoke
        full_matrix = np.asarray(
            [
                [1.088536, 0.036877, 0.091157],
                [-0.187636, 0.918791, -0.158392],
                [0.338670, 0.266531, 1.250971],
                [-0.094491, -0.089980, -0.074536],
            ],
            dtype=np.float32,
        )
        full = _native_color_matrix_response(
            image.filter(ImageFilter.GaussianBlur(1)), 1.0, full_matrix
        )
        return Image.blend(smoke, full, (strength - 0.4) / 0.6)
    if effect == "glow_orton":
        strength = max(0.0, amount)
        softened = image.filter(ImageFilter.GaussianBlur(8))
        glowing = Image.blend(image.convert("RGB"), softened, strength * 0.8)
        glowing = ImageEnhance.Brightness(glowing).enhance(1.0 + strength * 0.475)
        return ImageEnhance.Contrast(glowing).enhance(1.0 + strength * 0.2)
    if effect == "vignette":
        return _radial_light_effect(image, amount, effect)
    if effect in {
        "color_toning",
        "blue_hour",
        "complex_bleach",
        "high_key",
        "pro_contrast",
        "color_enhancer",
    }:
        return _color_effect(image, amount, effect)
    if effect in {"fade", "grain"}:
        return _style_effect(image, amount, effect)
    raise ValueError(f"deterministic effect is not implemented: {effect}")


def _apply_neon_strokes(
    image: Image.Image,
    strokes: list[dict[str, Any]],
    amount: float,
    parameters: dict[str, Any],
) -> Image.Image:
    """Render Neo's positioned freeform Neon & Glow contract."""

    strength = max(0.0, min(1.0, amount / 0.4))
    if strength == 0.0:
        return image.convert("RGB")
    spread = max(0.0, min(1.0, float(parameters.get("neon_spread", 0.6))))
    atmosphere = max(
        0.0, min(1.0, float(parameters.get("neon_atmosphere", 0.05)))
    )
    hue = float(parameters.get("neon_hue", 270.0)) % 360.0
    whiteness = max(
        0.0, min(1.0, float(parameters.get("neon_whiteness", 0.3)))
    )
    base = image.convert("RGB")
    minimum = float(min(image.size))
    saturation = 1.0 - whiteness * 0.4
    color = tuple(
        round(channel * 255.0)
        for channel in colorsys.hsv_to_rgb(
            ((hue + 15.0) % 360.0) / 360.0,
            saturation,
            1.0,
        )
    )

    def stroke_mask(width: int, fill: int) -> Image.Image:
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        for record in strokes:
            points = record.get("points") if isinstance(record, dict) else None
            if not isinstance(points, list) or len(points) < 2:
                raise ValueError("new_neon_light stroke requires at least two points")
            pixels = [
                (
                    round(max(0.0, min(1.0, float(point[0]))) * image.width),
                    round(max(0.0, min(1.0, float(point[1]))) * image.height),
                )
                for point in points
            ]
            radius = width / 2.0
            draw.line(pixels, fill=fill, width=width, joint="curve")
            for x, y in (pixels[0], pixels[-1]):
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
        return mask

    def screen_layer(
        current: Image.Image,
        *,
        width: int,
        fill: int,
        blur: float,
        rgb: tuple[int, int, int],
    ) -> Image.Image:
        mask = stroke_mask(width, fill).filter(ImageFilter.GaussianBlur(blur))
        layer = Image.merge(
            "RGB",
            tuple(mask.point(lambda value, channel=channel: value * channel / 255.0) for channel in rgb),
        )
        return ImageChops.screen(current, layer)

    outer_width = max(3, round(minimum * (0.052 + spread * 0.025)))
    result = screen_layer(
        base,
        width=outer_width,
        fill=round(255 * strength * (0.8 + atmosphere * 0.2)),
        blur=minimum * (0.018 + spread * 0.025),
        rgb=color,
    )
    broad_width = max(3, round(minimum * (0.038 + spread * 0.02)))
    result = screen_layer(
        result,
        width=broad_width,
        fill=round(255 * strength),
        blur=minimum * (0.008 + spread * 0.012),
        rgb=color,
    )
    middle_width = max(3, round(minimum * (0.028 + spread * 0.008)))
    result = screen_layer(
        result,
        width=middle_width,
        fill=round(255 * strength),
        blur=minimum * (0.004 + spread * 0.006),
        rgb=color,
    )
    core_width = max(2, round(minimum * (0.019 + whiteness * 0.01)))
    return screen_layer(
        result,
        width=core_width,
        fill=round(255 * strength),
        blur=max(0.35, minimum * 0.0008),
        rgb=(255, 255, 255),
    )


def _global_color_baseline(image: Image.Image, amount: float, effect: str) -> Image.Image:
    positive = np.asarray(
        [
            [2.385894, -0.095791, -0.019368],
            [-0.823637, 1.383884, -0.701494],
            [-0.546711, -0.286384, 1.721136],
            [-0.009706, -0.004518, -0.002500],
        ],
        dtype=np.float32,
    )
    negative = np.asarray(
        [
            [0.103392, 0.103392, 0.103392],
            [0.600996, 0.600996, 0.600996],
            [0.293953, 0.293953, 0.293953],
            [-0.000423, -0.000423, -0.000423],
        ],
        dtype=np.float32,
    )
    return _native_color_matrix_response(image, amount, positive, negative)


def _native_color_matrix_response(
    image: Image.Image,
    amount: float,
    positive: np.ndarray,
    negative: np.ndarray | None = None,
) -> Image.Image:
    """Interpolate a global RGB transform observed at the signed endpoints."""

    source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    strength = min(1.0, abs(amount))
    if strength == 0.0:
        return image.convert("RGB")
    coefficients = negative if amount < 0.0 and negative is not None else positive
    vectors = np.concatenate(
        [source, np.ones(source.shape[:2] + (1,), dtype=np.float32)], axis=2
    )
    mapped = np.clip(vectors @ coefficients, 0.0, 1.0)
    result = source + strength * (mapped - source)
    return Image.fromarray(
        np.rint(np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
    )


def _black_white_channels(image: Image.Image, amount: float) -> Image.Image:
    """Apply Luminar's conversion-first red luminance channel response.

    The three coefficients at -100, 0 and +100 come from the active native
    Luminar 1.28 red-channel anchors.  Piecewise interpolation preserves the
    neutral conversion and the asymmetric signed slider response without a
    fixture-specific image lookup.
    """
    source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    neutral = np.array([0.31652815, 0.48003796, 0.20178856], dtype=np.float32)
    negative = np.array([0.01111799, 0.85555156, 0.11975683], dtype=np.float32)
    positive = np.array([0.48286533, 0.26272712, 0.25824797], dtype=np.float32)
    neutral_bias = 0.00456724
    if amount < 0.0:
        strength = -amount
        weights = neutral + (negative - neutral) * strength
        bias = neutral_bias + (-0.00455905 - neutral_bias) * strength
    else:
        weights = neutral + (positive - neutral) * amount
        bias = neutral_bias + (0.00915143 - neutral_bias) * amount
    luminance = source @ weights + bias
    gray = np.repeat(np.clip(luminance, 0.0, 1.0)[..., None], 3, axis=2)
    return Image.fromarray(np.rint(gray * 255.0).astype(np.uint8), "RGB")


def _radial_light_effect(image: Image.Image, amount: float, effect: str) -> Image.Image:
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    height, width = array.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    distance = np.sqrt(
        ((xx - width / 2) / max(width / 2, 1)) ** 2 + ((yy - height / 2) / max(height / 2, 1)) ** 2
    )
    if effect == "vignette":
        if amount >= 0.0:
            feather = np.clip(
                (distance - 0.625) / (math.sqrt(2.0) - 0.625), 0.0, 1.0
            ) ** 1.25
            if amount <= 0.4:
                opacity = amount / 0.4 * 0.1516
            else:
                opacity = 0.1516 + (amount - 0.4) / 0.6 * (1.2393 - 0.1516)
            result = array + opacity * feather[..., None] * (1.0 - array)
        else:
            feather = np.clip(
                (distance - 0.675) / (math.sqrt(2.0) - 0.675), 0.0, 1.0
            ) ** 0.875
            opacity = -amount * 1.1931
            result = array * (1.0 - opacity * feather[..., None])
    return Image.fromarray(
        np.rint(np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
    )


def _color_effect(image: Image.Image, amount: float, effect: str) -> Image.Image:
    if effect == "high_key":
        return _high_key_tone_curve(image, amount)
    if effect == "pro_contrast":
        return _adaptive_highlight_contrast(image, amount)
    if effect == "complex_bleach":
        gray = image.convert("L").convert("RGB")
        bleached = Image.blend(image, gray, max(0.0, min(1.0, amount * 0.8)))
        bleached = ImageEnhance.Contrast(bleached).enhance(1.0 + amount * 0.1)
        return ImageEnhance.Brightness(bleached).enhance(1.0 + amount * 0.2)
    if effect == "color_enhancer":
        if amount < 0.0:
            enhanced = ImageEnhance.Color(image).enhance(1.0 + amount * 2.0)
            return ImageEnhance.Brightness(enhanced).enhance(1.0 - amount * 0.05)
        positive = np.asarray(
            [
                [3.017075, -0.409893, -0.031381],
                [-1.702062, 1.731369, -1.011845],
                [-0.418522, -0.341833, 1.952130],
                [0.038729, 0.006159, 0.038688],
            ],
            dtype=np.float32,
        )
        return _native_color_matrix_response(image, amount, positive)
    if effect == "color_toning" and amount >= 0.0:
        positive = np.asarray(
            [
                [0.694317, 0.015670, -0.041091],
                [0.126084, 1.059512, 0.027095],
                [0.367249, -0.184159, 0.955548],
                [0.009856, -0.013042, -0.011105],
            ],
            dtype=np.float32,
        )
        # The native 0.4 and 1.0 captures are pixel-equivalent for this
        # abstract control, so 0.4 is the observed full-strength anchor.
        strength = min(1.0, amount / 0.4) if amount else 0.0
        return _native_color_matrix_response(image, strength, positive)
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    if effect == "blue_hour":
        return _blue_hour_tone_curve(image, amount)
    elif effect == "color_toning":
        array[..., 0] *= 1.0 + 0.90 * amount
        array[..., 1] *= 1.0 - 0.35 * amount
        array[..., 2] *= 1.0 - 0.15 * amount
    else:
        array = np.clip(array * (1.0 + amount * 0.15), 0.0, 1.0)
    return Image.fromarray((np.clip(array, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")


def _high_key_tone_curve(image: Image.Image, amount: float) -> Image.Image:
    """Apply the monotonic RGB response shared by the 0.4 and 1.0 anchors."""

    strength = max(0.0, min(1.0, amount))
    if strength == 0.0:
        return image.convert("RGB")
    source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    knots = np.linspace(0.0, 1.0, 17, dtype=np.float32)
    curves = np.asarray(
        [
            [
                0.01569,
                0.06667,
                0.13333,
                0.22353,
                0.31373,
                0.41569,
                0.50196,
                0.58039,
                0.66275,
                0.72941,
                0.80392,
                0.85882,
                0.90588,
                0.94118,
                0.97255,
                0.98824,
                0.99608,
            ],
            [
                0.01176,
                0.06667,
                0.14902,
                0.24706,
                0.33725,
                0.42745,
                0.51373,
                0.59608,
                0.67843,
                0.75294,
                0.81176,
                0.86667,
                0.90980,
                0.94510,
                0.97255,
                0.98824,
                0.99608,
            ],
            [
                0.01961,
                0.07451,
                0.17255,
                0.27059,
                0.37255,
                0.46275,
                0.55686,
                0.63922,
                0.71765,
                0.77647,
                0.82745,
                0.87059,
                0.90980,
                0.94510,
                0.97255,
                0.99608,
                0.99608,
            ],
        ],
        dtype=np.float32,
    )
    mapped = np.stack(
        [
            np.interp(source[..., channel], knots, curves[channel])
            for channel in range(3)
        ],
        axis=2,
    )
    result = source + strength * (mapped - source)
    return Image.fromarray(
        np.rint(np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
    )


def _blue_hour_tone_curve(image: Image.Image, amount: float) -> Image.Image:
    """Apply the native-calibrated global part of Blue Hour's response.

    The compact monotonic curves are fitted from one 0.4 native capture and
    verified against a different-photo holdout.  Blue Hour also has a
    content-aware sky colour component; that remains outside this deterministic
    fallback instead of being approximated with source-specific pixel rules.
    """

    strength = max(0.0, amount) / 0.4
    if strength == 0.0:
        return image.convert("RGB")
    source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    knots = np.linspace(0.0, 1.0, 9, dtype=np.float32)
    channel_curves = np.asarray(
        [
            [0.0, 0.09412, 0.19216, 0.29412, 0.39608, 0.49804, 0.6, 0.7098, 0.83922],
            [0.01176, 0.0902, 0.18824, 0.2902, 0.38824, 0.4902, 0.59216, 0.69804, 0.83529],
            [0.0, 0.09412, 0.19216, 0.2902, 0.39216, 0.49412, 0.60392, 0.70588, 0.90196],
        ],
        dtype=np.float32,
    )
    calibrated = np.stack(
        [
            np.interp(source[..., channel], knots, channel_curves[channel])
            for channel in range(3)
        ],
        axis=2,
    )
    result = source + strength * (calibrated - source)
    return Image.fromarray(
        (np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
    )


def _adaptive_highlight_contrast(image: Image.Image, amount: float) -> Image.Image:
    """Approximate Neo's content-adaptive Highlights contrast response.

    The native smoke operation maps the abstract 0.4 amount to its full
    Highlights control. Three independent 1.28 captures calibrate this compact
    monotonic tone-curve family; a fourth capture is held out for validation.
    """

    normalized = max(0.0, amount)
    if normalized <= 0.4:
        strength = normalized / 0.4
    else:
        # Native 1.28 has two same-photo anchors for this control: the 0.4
        # smoke anchor reaches the calibrated curve, while the 1.0 exact
        # anchor continues 42.5% beyond it.  Preserve the validated lower
        # response and interpolate the observed upper range instead of
        # saturating every value above 0.4.
        strength = 1.0 + (normalized - 0.4) / 0.6 * 0.425
    if strength == 0.0:
        return image.convert("RGB")
    source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    means = source.mean(axis=(0, 1))
    knots = np.linspace(0.0, 1.0, 9, dtype=np.float32)
    coefficients = np.asarray(
        [
            [
                [0.03057954, -0.06328819],
                [0.12240918, -0.01029457],
                [0.48391573, -0.52911218],
                [0.76908390, -0.91124578],
                [0.79993986, -0.84776500],
                [0.78199424, -0.58436096],
                [0.79192363, -0.31101659],
                [0.90473353, -0.19738230],
                [0.99495564, -0.00232427],
            ],
            [
                [0.00739931, -0.01628860],
                [0.11004531, 0.01544138],
                [0.25385210, -0.02376397],
                [0.38984615, -0.06444420],
                [0.50665113, -0.07037013],
                [0.65571994, -0.20256558],
                [0.79099559, -0.29035291],
                [0.90200207, -0.17708494],
                [0.98211920, 0.02327658],
            ],
            [
                [0.01099059, -0.01936393],
                [0.09801452, 0.03212999],
                [0.24882223, -0.01943078],
                [0.40060771, -0.08123819],
                [0.51607141, -0.08358092],
                [0.64652223, -0.17787511],
                [0.76465175, -0.20666146],
                [0.85304241, -0.07244197],
                [0.98545323, 0.00766877],
            ],
        ],
        dtype=np.float32,
    )
    curves = coefficients[..., 0] + coefficients[..., 1] * means[:, None]
    curves = np.maximum.accumulate(np.clip(curves, 0.0, 1.0), axis=1)
    mapped = np.stack(
        [np.interp(source[..., channel], knots, curves[channel]) for channel in range(3)],
        axis=-1,
    ).astype(np.float32)
    result = source * (1.0 - strength) + mapped * strength
    return Image.fromarray(
        (np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
    )


def _style_effect(image: Image.Image, amount: float, effect: str) -> Image.Image:
    array = np.asarray(image.convert("RGB"), dtype=np.float32)
    if effect == "fade":
        if amount < 0.0:
            return image.convert("RGB")
        positive = np.asarray(
            [
                [0.868472, 0.025116, 0.105092],
                [-0.198108, 0.763504, -0.127312],
                [0.388726, 0.292183, 1.056730],
                [0.052472, 0.032538, 0.056643],
            ],
            dtype=np.float32,
        )
        return _native_color_matrix_response(image, amount, positive)
    else:
        if amount <= 0.4:
            native_amount = max(0.0, amount)
            upper = 0.0
        else:
            upper = min(1.0, (amount - 0.4) / 0.6)
            # Preserve the validated 0.4 grain response and continue to the
            # measured full-strength residual variance without extrapolating
            # the smoke anchor linearly.
            native_amount = 0.4 + upper * 0.42
        rng = np.random.default_rng(20240812)
        noise = rng.normal(0.0, 41.5 * native_amount, array.shape[:2] + (1,))
        upper_bias = np.asarray([-0.0073, -0.0018, -0.0011], dtype=np.float32)
        array = array + noise + upper_bias * (255.0 * upper)
    return Image.fromarray(np.clip(array, 0.0, 255.0).astype(np.uint8), "RGB")


def blend(
    base: Image.Image,
    edited: Image.Image,
    opacity: float = 1.0,
    mask: Image.Image | None = None,
) -> Image.Image:
    opacity = max(0.0, min(1.0, opacity))
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    if edited.mode != "RGBA":
        edited = edited.convert("RGBA")
    if mask is None:
        return Image.blend(base, edited, opacity)
    mask_array = np.asarray(
        mask.convert("L").resize(base.size, Image.Resampling.BILINEAR),
        dtype=np.float32,
    ) / 255.0
    alpha = np.clip(mask_array * opacity, 0.0, 1.0)[..., None]
    base_array = np.asarray(base, dtype=np.float32)
    edited_array = np.asarray(edited.resize(base.size), dtype=np.float32)
    result = base_array * (1.0 - alpha) + edited_array * alpha
    return Image.fromarray(np.rint(np.clip(result, 0.0, 255.0)).astype(np.uint8), "RGBA")


def composite_image_layer(
    base: Image.Image,
    source: Image.Image,
    *,
    opacity: float,
    mode: str,
    scale: float = 1.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    rotation: float = 0.0,
    flip_x: bool = False,
    flip_y: bool = False,
    stretch: bool = False,
    mask: Image.Image | None = None,
) -> Image.Image:
    """Fit and blend a non-destructive image layer without stretching it."""
    base_rgb = base.convert("RGB")
    layer = source.convert("RGBA")
    if flip_x:
        layer = ImageOps.mirror(layer)
    if flip_y:
        layer = ImageOps.flip(layer)
    if stretch:
        size = (
            max(1, round(base_rgb.width * max(0.1, min(8.0, scale)))),
            max(1, round(base_rgb.height * max(0.1, min(8.0, scale)))),
        )
    else:
        fit_scale = max(base_rgb.width / layer.width, base_rgb.height / layer.height)
        fit_scale *= max(0.1, min(8.0, scale))
        size = (
            max(1, round(layer.width * fit_scale)),
            max(1, round(layer.height * fit_scale)),
        )
    layer = layer.resize(size, Image.Resampling.LANCZOS)
    if rotation:
        layer = layer.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new("RGBA", base_rgb.size, (0, 0, 0, 0))
    x = round((base_rgb.width - layer.width) / 2 + offset_x * base_rgb.width)
    y = round((base_rgb.height - layer.height) / 2 + offset_y * base_rgb.height)
    canvas.alpha_composite(layer, (x, y))

    base_array = np.asarray(base_rgb, dtype=np.float32) / 255.0
    layer_array = np.asarray(canvas, dtype=np.float32) / 255.0
    layer_rgb = layer_array[..., :3]
    if mode == "screen":
        mixed = 1.0 - (1.0 - base_array) * (1.0 - layer_rgb)
    elif mode == "multiply":
        mixed = base_array * layer_rgb
    elif mode == "overlay":
        mixed = np.where(
            base_array <= 0.5,
            2.0 * base_array * layer_rgb,
            1.0 - 2.0 * (1.0 - base_array) * (1.0 - layer_rgb),
        )
    elif mode == "soft_light":
        mixed = (1.0 - 2.0 * layer_rgb) * base_array**2 + 2.0 * layer_rgb * base_array
    elif mode == "lighten":
        mixed = np.maximum(base_array, layer_rgb)
    elif mode == "darken":
        mixed = np.minimum(base_array, layer_rgb)
    else:
        mixed = layer_rgb
    alpha = layer_array[..., 3:4] * max(0.0, min(1.0, opacity))
    if mask is not None:
        mask_array = np.asarray(
            mask.convert("L").resize(base_rgb.size, Image.Resampling.BILINEAR),
            dtype=np.float32,
        ) / 255.0
        alpha *= mask_array[..., None]
    result = base_array * (1.0 - alpha) + mixed * alpha
    return Image.fromarray((np.clip(result, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), "RGB")


def image_stats(image: Image.Image) -> dict[str, float]:
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return {"mean": float(array.mean()), "min": float(array.min()), "max": float(array.max())}


def composite_texture(
    image: Image.Image,
    texture: Image.Image,
    *,
    opacity: float = 1.0,
    mode: str = "screen",
    offset_y: float = 0.0,
) -> Image.Image:
    """Composite an effect asset deterministically over the current image."""
    base = image.convert("RGBA")
    layer = texture.convert("RGBA").resize(base.size, Image.Resampling.LANCZOS)
    if offset_y:
        shifted = Image.new("RGBA", layer.size)
        pixels = int(offset_y * base.height)
        shifted.alpha_composite(layer, (0, pixels))
        layer = shifted
    if mode == "multiply":
        blended = Image.fromarray(
            (np.asarray(base)[:, :, :3] * np.asarray(layer)[:, :, :3] / 255.0).astype(np.uint8),
            "RGB",
        ).convert("RGBA")
    elif mode == "screen":
        b = np.asarray(base)[:, :, :3].astype(np.float32)
        l = np.asarray(layer)[:, :, :3].astype(np.float32)
        blended = Image.fromarray(
            (255.0 - (255.0 - b) * (255.0 - l) / 255.0).astype(np.uint8), "RGB"
        ).convert("RGBA")
    else:
        blended = layer
    return Image.blend(base, blended, max(0.0, min(1.0, opacity))).convert("RGB")
