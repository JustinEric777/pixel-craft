"""Render imported Luminar preset parameters with deterministic image operators."""

from __future__ import annotations

import colorsys
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from .lut import apply_cube_lut, resolve_lut

SourceEffectCallback = Callable[
    [Image.Image, str, dict[str, dict[str, Any]], Path | None], Image.Image | None
]


def apply_luminar_preset(
    image: Image.Image,
    effects: list[dict[str, Any]],
    *,
    asset_root: Path | None = None,
    source_effect_callback: SourceEffectCallback | None = None,
) -> Image.Image:
    result = image.convert("RGB")
    for effect in effects:
        parameters = _parameters(effect.get("parameters", []))
        if source_effect_callback is not None:
            model_result = source_effect_callback(
                result,
                str(effect.get("id", "")),
                parameters,
                asset_root,
            )
            if model_result is not None:
                result = model_result
                continue
        result = _apply_source_effect(
            result,
            str(effect.get("id", "")),
            parameters,
            asset_root=asset_root,
        )
    return result


def _parameters(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("name", "")): item for item in records if item.get("name")}


def _value(parameters: dict[str, dict[str, Any]], name: str, default: float = 0.0) -> float:
    try:
        return float(parameters.get(name, {}).get("value", default))
    except (TypeError, ValueError):
        return default


def _apply_source_effect(
    image: Image.Image,
    effect_id: str,
    parameters: dict[str, dict[str, Any]],
    *,
    asset_root: Path | None,
) -> Image.Image:
    if effect_id == "MIPLGrainNewEffect":
        return _grain(image, _value(parameters, "Amount") / 100.0, _value(parameters, "Size"))
    if effect_id == "MIPLBWChannels_v1_Effect":
        amount = max(0.0, min(1.0, _value(parameters, "Apply", 100.0) / 100.0))
        return Image.blend(image, image.convert("L").convert("RGB"), amount)
    if effect_id == "MIPLVignetteEffect":
        return _vignette(image, parameters)
    if effect_id == "MIPLAIFogEffect":
        return _fog(image, parameters)
    if effect_id in {"MIPLDetailsEffect", "MIPLSharpenEffect"}:
        amount = _detail_amount(parameters, effect_id)
        return ImageEnhance.Sharpness(image).enhance(max(0.0, 1.0 + amount * 1.2))
    if effect_id == "MIPLAIStructureEffect":
        amount = (_value(parameters, "Amount") + _value(parameters, "Boost") * 0.35) / 100.0
        detailed = image.filter(ImageFilter.UnsharpMask(radius=2.2, percent=115, threshold=3))
        return Image.blend(image, detailed, max(0.0, min(1.0, amount)))
    if effect_id in {"MIPLSmartContrastEffect", "MIPLDynamicContrastEffect"}:
        amount = _contrast_amount(parameters, effect_id)
        return ImageEnhance.Contrast(image).enhance(max(0.1, 1.0 + amount * 0.7))
    if effect_id in {"MIPLSaturationEffect", "MIPLVibranceEffect"}:
        key = "Saturation" if effect_id == "MIPLSaturationEffect" else "Vibrance"
        return ImageEnhance.Color(image).enhance(max(0.0, 1.0 + _value(parameters, key) / 100.0))
    if effect_id == "MIPLCurveEffect":
        return _curve(image, parameters)
    if effect_id in {"MIPLRawDevelopEffect", "MIPLDevelopCommonEffectID"}:
        return _develop(image, parameters, raw=effect_id == "MIPLRawDevelopEffect")
    if effect_id == "MIPLBlackWhiteEffect":
        return _black_white_levels(image, parameters)
    if effect_id == "MIPLDenoiseLaplacianEffect":
        return _denoise(image, parameters)
    if effect_id == "MIPLFaceEnhancer_vn0_Effect":
        return _portrait_light(image, parameters)
    if effect_id == "MIPLSkinSoftenerNNEffect":
        return _skin_soften(image, parameters)
    if effect_id == "MIPLSlimPeople_vn0_Effect":
        return _slim_center(image, _value(parameters, "Shape") / 100.0)
    if effect_id == "MIPLHueShiftEffect":
        return _hue_shift(image, _value(parameters, "Hue") / 360.0)
    if effect_id == "MIPLSplitToningEffect":
        return _split_tone(image, parameters)
    if effect_id in {"MIPLBrillianceWarmthEffect", "MIPLSplitWarmthEffect", "MIPLWarmSkylight_v1_Effect"}:
        warmth = _value(parameters, "Warmth", _value(parameters, "Amount")) / 100.0
        warmth += (_value(parameters, "Warm Colors") - _value(parameters, "Cool Colors")) / 200.0
        return _temperature(image, warmth)
    if effect_id in {"MIPLChannelsEffect", "MIPLColorBalanceEffect"}:
        return _channel_balance(image, parameters)
    if effect_id == "MIPLContrastColorRangeEffect":
        result = ImageEnhance.Contrast(image).enhance(
            max(0.1, 1.0 + _value(parameters, "Contrast") / 100.0)
        )
        return ImageEnhance.Brightness(result).enhance(
            max(0.1, 1.0 + _value(parameters, "Brightness") / 150.0)
        )
    if effect_id in {"MIPLDehazeEffect", "MIPLSkyEnhancerEffect"}:
        amount = _value(parameters, "Amount") / 100.0
        result = ImageEnhance.Contrast(image).enhance(1.0 + amount * 0.45)
        return ImageEnhance.Color(result).enhance(1.0 + amount * 0.2)
    if effect_id == "MIPLFoliageEnhanceEffect":
        return _foliage(image, parameters)
    if effect_id == "MIPLFadeEffect":
        amount = max(_value(parameters, "Amount"), _value(parameters, "Fade")) / 100.0
        faded = Image.blend(image, Image.new("RGB", image.size, (222, 215, 204)), amount * 0.28)
        return ImageEnhance.Contrast(faded).enhance(
            max(0.2, 1.0 + _value(parameters, "Contrast") / 120.0)
        )
    if effect_id == "MIPLComplexBleachEffect":
        amount = max(0.0, min(1.0, _value(parameters, "Amount") / 100.0))
        bleached = ImageEnhance.Contrast(image.convert("L").convert("RGB")).enhance(1.25)
        return Image.blend(image, bleached, amount * 0.72)
    if effect_id == "MIPLHighKeyEffect":
        amount = max(
            _value(parameters, "Amount"),
            _value(parameters, "Dynamic High Key"),
            _value(parameters, "Standard High Key"),
        ) / 100.0
        return ImageEnhance.Brightness(image).enhance(1.0 + amount * 0.48)
    if effect_id == "MIPLOrtonGlowEffect":
        return _orton(image, parameters)
    if effect_id == "MIPLRemoveColorCastEffect":
        return _remove_color_cast(image, _value(parameters, "Amount") / 100.0)
    if effect_id == "MIPLLUTMappingEffect":
        return _lut_look(image, parameters, asset_root)
    if effect_id == "MIPLSkyReplacementEffect":
        return _preset_sky(image, parameters, asset_root)
    return image


def _detail_amount(parameters: dict[str, dict[str, Any]], effect_id: str) -> float:
    if effect_id == "MIPLSharpenEffect":
        return _value(parameters, "Amount") / 100.0
    values = [
        _value(parameters, "Overall_Small_Detail"),
        _value(parameters, "Overall_Medium_Detail"),
        _value(parameters, "Overall_Large_Detail"),
    ]
    return sum(values) / 300.0


def _contrast_amount(parameters: dict[str, dict[str, Any]], effect_id: str) -> float:
    if effect_id == "MIPLDynamicContrastEffect":
        return _value(parameters, "Boost") / 100.0
    middle = sum(
        _value(parameters, key) for key in ("MiddleS", "MiddleM", "MiddleH")
    ) / 300.0
    zones = sum(
        _value(parameters, key) for key in ("Shadows", "Midtones", "Highlights")
    ) / 300.0
    return max(-1.0, min(1.0, middle + zones))


def _curve(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    array = np.asarray(image, dtype=np.float32) / 255.0
    result = array.copy()
    for name, channel in (("RGB", None), ("R", 0), ("G", 1), ("B", 2)):
        record = parameters.get(name)
        if not record:
            continue
        raw_points = record.get("opt_data_value")
        if not isinstance(raw_points, list) or len(raw_points) < 5:
            continue
        try:
            points = np.asarray([float(value) for value in raw_points[1:]], dtype=np.float32)
        except (TypeError, ValueError):
            continue
        if points.size % 2:
            points = points[:-1]
        points = points.reshape(-1, 2)
        order = np.argsort(points[:, 0])
        x = np.clip(points[order, 0], 0.0, 1.0)
        y = np.clip(points[order, 1], 0.0, 1.0)
        x, unique = np.unique(x, return_index=True)
        y = y[unique]
        if x.size < 2:
            continue
        if channel is None:
            result = np.interp(result, x, y).astype(np.float32)
        else:
            result[..., channel] = np.interp(result[..., channel], x, y)
    return Image.fromarray(np.rint(np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")


def _develop(
    image: Image.Image,
    parameters: dict[str, dict[str, Any]],
    *,
    raw: bool,
) -> Image.Image:
    array = np.asarray(image, dtype=np.float32) / 255.0
    exposure = _value(parameters, "Exposure") / 100.0
    if exposure:
        array *= 2.0 ** (exposure * 1.5)
    luminance = array.mean(axis=2, keepdims=True)
    shadows = _value(parameters, "Shadows") / 100.0
    highlights = _value(parameters, "Highlights") / 100.0
    if shadows:
        array += shadows * np.square(1.0 - luminance) * 0.42
    if highlights:
        array += highlights * np.square(luminance) * 0.32
    result = Image.fromarray(np.rint(np.clip(array, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")
    contrast = _value(parameters, "Contrast") / 100.0
    if contrast:
        result = ImageEnhance.Contrast(result).enhance(max(0.1, 1.0 + contrast * 0.72))
    if raw:
        temperature = (_value(parameters, "Temperature", 5000.0) - 5000.0) / 20000.0
        result = _temperature(result, temperature)
        tint = max(-1.0, min(1.0, _value(parameters, "Tint") / 150.0))
        if tint:
            tinted = np.asarray(result, dtype=np.float32)
            tinted[..., 0] *= 1.0 + tint * 0.035
            tinted[..., 1] *= 1.0 - tint * 0.055
            tinted[..., 2] *= 1.0 + tint * 0.035
            result = Image.fromarray(np.clip(tinted, 0, 255).astype(np.uint8), "RGB")
    return result


def _black_white_levels(
    image: Image.Image, parameters: dict[str, dict[str, Any]]
) -> Image.Image:
    array = np.asarray(image, dtype=np.float32) / 255.0
    luminance = array.mean(axis=2, keepdims=True)
    whites = _value(parameters, "Whites") / 100.0
    blacks = _value(parameters, "Blacks") / 100.0
    array += whites * np.square(luminance) * 0.3
    array += blacks * np.square(1.0 - luminance) * 0.3
    return Image.fromarray(np.rint(np.clip(array, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")


def _denoise(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    amount = max(
        _value(parameters, "Luminosity"),
        _value(parameters, "Color"),
    ) / 100.0
    if amount <= 0.0:
        return image
    filtered = image.filter(ImageFilter.MedianFilter(3)).filter(
        ImageFilter.GaussianBlur(0.25 + amount)
    )
    return Image.blend(image, filtered, min(0.72, amount * 0.72))


def _portrait_light(
    image: Image.Image, parameters: dict[str, dict[str, Any]]
) -> Image.Image:
    amount = max(
        _value(parameters, "Face Light"),
        _value(parameters, "Eye Enhancer") * 0.35,
        _value(parameters, "Dark Circles Removal") * 0.3,
    ) / 100.0
    if amount <= 0.0:
        return image
    height, width = image.height, image.width
    yy, xx = np.mgrid[0:height, 0:width]
    radius = ((xx - width * 0.5) / max(width * 0.38, 1)) ** 2
    radius += ((yy - height * 0.4) / max(height * 0.36, 1)) ** 2
    alpha = np.clip(1.0 - radius, 0.0, 1.0) * min(0.35, amount * 0.28)
    source = np.asarray(image, dtype=np.float32)
    light = np.asarray(ImageEnhance.Brightness(image).enhance(1.0 + amount * 0.22), dtype=np.float32)
    result = source * (1.0 - alpha[..., None]) + light * alpha[..., None]
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")


def _skin_soften(
    image: Image.Image, parameters: dict[str, dict[str, Any]]
) -> Image.Image:
    amount = max(0.0, min(1.0, _value(parameters, "Amount") / 100.0))
    if amount <= 0.0:
        return image
    source = np.asarray(image, dtype=np.float32)
    red, green, blue = source[..., 0], source[..., 1], source[..., 2]
    skin = (red > green * 1.03) & (green > blue * 0.9) & (red > 55) & (green > 35)
    mask = Image.fromarray((skin.astype(np.uint8) * 255), "L").filter(
        ImageFilter.GaussianBlur(max(1.0, min(image.size) * 0.008))
    )
    softened = image.filter(ImageFilter.GaussianBlur(0.8 + amount * 2.2))
    alpha = mask.point(lambda value: round(value * amount * 0.62))
    return Image.composite(softened, image, alpha)


def _slim_center(image: Image.Image, amount: float) -> Image.Image:
    amount = max(0.0, min(0.25, amount * 0.22))
    if amount <= 0.0:
        return image
    source = np.asarray(image, dtype=np.uint8)
    height, width = source.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    vertical = np.clip(1.0 - np.abs(yy / max(height - 1, 1) - 0.58) / 0.45, 0.0, 1.0)
    center = (width - 1) * 0.5
    source_x = center + (xx - center) * (1.0 + amount * vertical)
    source_x = np.clip(np.rint(source_x), 0, width - 1).astype(np.intp)
    return Image.fromarray(source[yy, source_x], "RGB")


def _grain(image: Image.Image, amount: float, size: float) -> Image.Image:
    if amount <= 0:
        return image
    array = np.asarray(image, dtype=np.float32)
    seed = int(hashlib.sha256(array[:4, :4].tobytes()).hexdigest()[:8], 16)
    noise = np.random.default_rng(seed).normal(0.0, 3.0 + 20.0 * amount, array.shape[:2])
    radius = max(0.0, min(2.0, size / 60.0))
    noise_image = Image.fromarray(np.clip(noise + 128.0, 0, 255).astype(np.uint8), "L")
    if radius:
        noise_image = noise_image.filter(ImageFilter.GaussianBlur(radius))
    centered = np.asarray(noise_image, dtype=np.float32) - 128.0
    return Image.fromarray(np.clip(array + centered[..., None], 0, 255).astype(np.uint8), "RGB")


def _vignette(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    amount = _value(parameters, "Amount") / 100.0
    width, height = image.size
    x_offset = _value(parameters, "Offset X") / 200.0
    y_offset = _value(parameters, "Offset Y") / 200.0
    yy, xx = np.mgrid[0:height, 0:width]
    cx, cy = width * (0.5 + x_offset), height * (0.5 + y_offset)
    radius = np.sqrt(((xx - cx) / max(width / 2, 1)) ** 2 + ((yy - cy) / max(height / 2, 1)) ** 2)
    size = 0.2 + _value(parameters, "Vignette Size", 50.0) / 125.0
    feather = 0.08 + (_value(parameters, "Feather", 50.0) + 100.0) / 300.0
    edge = np.clip((radius - size) / max(feather, 0.02), 0.0, 1.0)
    factor = 1.0 + edge * amount * 0.68
    array = np.asarray(image, dtype=np.float32) * factor[..., None]
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def _fog(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    amount = max(0.0, min(1.0, _value(parameters, "Amount") / 100.0))
    lightness = _value(parameters, "Lightness", 50.0) / 100.0
    depth = _value(parameters, "Depth", 50.0) / 100.0
    height = image.height
    gradient = np.linspace(1.0, max(0.1, depth), height, dtype=np.float32)[:, None]
    alpha = np.clip(amount * gradient, 0.0, 0.85)
    fog_color = 170.0 + lightness * 75.0
    array = np.asarray(image, dtype=np.float32)
    result = array * (1.0 - alpha[..., None]) + fog_color * alpha[..., None]
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")


def _hue_shift(image: Image.Image, shift: float) -> Image.Image:
    hsv = np.asarray(image.convert("HSV"), dtype=np.uint8).copy()
    hsv[..., 0] = (hsv[..., 0].astype(np.int16) + round(shift * 255.0)) % 256
    return Image.fromarray(hsv, "HSV").convert("RGB")


def _split_tone(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    array = np.asarray(image, dtype=np.float32) / 255.0
    luminance = array.mean(axis=2)
    balance = _value(parameters, "Balance") / 200.0
    amount = max(0.0, min(1.0, _value(parameters, "Amount", 100.0) / 100.0))
    shadow = np.asarray(colorsys.hsv_to_rgb(_value(parameters, "ShadowsHue") / 360.0, 1.0, 1.0))
    highlight = np.asarray(colorsys.hsv_to_rgb(_value(parameters, "HighlightsHue") / 360.0, 1.0, 1.0))
    shadow_strength = _value(parameters, "ShadowsSaturation") / 100.0
    highlight_strength = _value(parameters, "HighlightsSaturation") / 100.0
    highlight_weight = np.clip(luminance - 0.5 + balance, 0.0, 0.5) * 2.0
    shadow_weight = np.clip(0.5 - luminance - balance, 0.0, 0.5) * 2.0
    tint = shadow[None, None] * (shadow_weight * shadow_strength)[..., None]
    tint += highlight[None, None] * (highlight_weight * highlight_strength)[..., None]
    weight = np.clip(shadow_weight * shadow_strength + highlight_weight * highlight_strength, 0, 1)
    result = array * (1.0 - weight[..., None] * amount) + tint * amount
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGB")


def _temperature(image: Image.Image, warmth: float) -> Image.Image:
    array = np.asarray(image, dtype=np.float32)
    warmth = max(-1.0, min(1.0, warmth))
    array[..., 0] *= 1.0 + warmth * 0.12
    array[..., 2] *= 1.0 - warmth * 0.12
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def _channel_balance(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    values = list(parameters.values())
    red = sum(_value(parameters, key) for key in ("SRed", "MRed", "HRed"))
    green = sum(_value(parameters, key) for key in ("SGreen", "MGreen", "HGreen"))
    blue = sum(_value(parameters, key) for key in ("SBlue", "MBlue", "HBlue"))
    if red == green == blue == 0 and values:
        red = sum(_value(parameters, key) for key in parameters if key.endswith("Red"))
        green = sum(_value(parameters, key) for key in parameters if key.endswith("Green"))
        blue = sum(_value(parameters, key) for key in parameters if key.endswith("Blue"))
    array = np.asarray(image, dtype=np.float32)
    for channel, value in enumerate((red, green, blue)):
        array[..., channel] *= 1.0 + max(-0.35, min(0.35, value / 600.0))
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def _foliage(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    array = np.asarray(image, dtype=np.float32)
    green = array[..., 1] > np.maximum(array[..., 0] * 0.9, array[..., 2] * 1.05)
    amount = _value(parameters, "Amount") / 100.0
    array[..., 1][green] *= 1.0 + amount * 0.3
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def _orton(image: Image.Image, parameters: dict[str, dict[str, Any]]) -> Image.Image:
    amount = max(0.0, min(1.0, _value(parameters, "Amount") / 100.0))
    glow = image.filter(ImageFilter.GaussianBlur(7.0 + amount * 9.0))
    result = Image.blend(image, glow, amount * 0.42)
    result = ImageEnhance.Brightness(result).enhance(
        max(0.3, 1.0 + _value(parameters, "Brightness") / 180.0)
    )
    return _temperature(result, _value(parameters, "Warmth") / 100.0)


def _remove_color_cast(image: Image.Image, amount: float) -> Image.Image:
    array = np.asarray(image, dtype=np.float32)
    means = array.mean(axis=(0, 1), keepdims=True)
    target = means.mean()
    corrected = array * (target / np.maximum(means, 1.0))
    return Image.fromarray(
        np.clip(array * (1.0 - amount) + corrected * amount, 0, 255).astype(np.uint8), "RGB"
    )


def _lut_look(
    image: Image.Image,
    parameters: dict[str, dict[str, Any]],
    asset_root: Path | None,
) -> Image.Image:
    record = parameters.get("Texture", {})
    raw_token = record.get("opt_data_value")
    if raw_token in {None, "", "0", 0}:
        return image
    token = json_token(raw_token)
    if asset_root is None:
        raise ValueError(f"preset LUT requires the configured asset root: {token}")
    lut_path = resolve_lut(asset_root, token)
    amount = max(0.0, min(1.0, _value(parameters, "Amount", 100.0) / 100.0))
    return apply_cube_lut(
        image,
        lut_path,
        amount=amount,
        contrast=_value(parameters, "Contrast") / 100.0,
        saturation=_value(parameters, "Saturation") / 100.0,
    )


def _preset_sky(
    image: Image.Image,
    parameters: dict[str, dict[str, Any]],
    asset_root: Path | None,
) -> Image.Image:
    record = parameters.get("Texture", {})
    token = str(record.get("opt_data_value") or "")
    if not token or asset_root is None:
        return image
    texture_name = token.removeprefix("MIPLResource_SkyTextures-")
    sky_root = asset_root.resolve() / "materials" / "SkyTextures"
    sky_path = next(
        (
            candidate
            for candidate in sky_root.rglob("*")
            if candidate.is_file() and candidate.name.casefold() == texture_name.casefold()
        ),
        None,
    )
    if sky_path is None:
        return image
    with Image.open(sky_path) as opened:
        sky = opened.convert("RGB").resize(image.size, Image.Resampling.LANCZOS)
    source = np.asarray(image, dtype=np.float32) / 255.0
    height, width = source.shape[:2]
    yy = np.arange(height, dtype=np.float32)[:, None] / max(height - 1, 1)
    blue_score = np.clip(source[..., 2] - source[..., 0] * 0.72, 0.0, 1.0)
    bright_score = np.clip((source.mean(axis=2) - 0.38) * 2.4, 0.0, 1.0)
    upper = np.clip((0.68 - yy) / 0.2, 0.0, 1.0)
    mask = np.maximum(blue_score, bright_score * 0.55) * upper
    mask_image = Image.fromarray(np.rint(mask * 255.0).astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(max(1.0, min(width, height) * 0.006))
    )
    return Image.composite(sky, image, mask_image)


def json_token(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return repr(value)
    return str(value or "luminar-default-lut")
