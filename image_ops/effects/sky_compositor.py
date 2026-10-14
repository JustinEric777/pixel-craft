"""Sky replacement primitives shared by preview and export.

The original application's private sky pipeline is not distributable.  This
module keeps the observable edit contract useful with the available ONNX
artifacts: a sky mask is supplied by the model service, then the texture is
geometrically fitted, color-matched and blended only inside that mask.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def composite_sky(
    image: Image.Image,
    texture: Image.Image,
    mask: np.ndarray,
    parameters: dict[str, Any],
) -> Image.Image:
    base = image.convert("RGB")
    width, height = base.size
    mask_image = _prepare_mask(mask, (width, height), parameters)
    foreground = parameters.get("_foreground_mask")
    if isinstance(foreground, np.ndarray):
        mask_image = _protect_foreground(mask_image, foreground, (width, height))
    texture_layer = _fit_texture(base, texture, parameters)
    texture_layer = _match_texture(texture_layer, base, parameters)
    sky_blur = max(0.0, min(20.0, _number(parameters, "sky_blur", 0.0)))
    if sky_blur:
        texture_layer = texture_layer.filter(ImageFilter.GaussianBlur(sky_blur / 2.0))
    texture_layer = _add_grain(texture_layer, _number(parameters, "sky_grain", 0.0))

    opacity = _number(parameters, "texture_opacity", parameters.get("opacity", 1.0))
    opacity = max(0.0, min(1.0, opacity))
    alpha = np.asarray(mask_image, dtype=np.float32) / 255.0
    alpha *= opacity

    result_array = (
        np.asarray(base, dtype=np.float32) * (1.0 - alpha[..., None])
        + np.asarray(texture_layer, dtype=np.float32) * alpha[..., None]
    )
    result = Image.fromarray(np.clip(result_array, 0.0, 255.0).astype(np.uint8), "RGB")
    reflection = parameters.get("_reflection_mask")
    if isinstance(reflection, np.ndarray):
        reflection_image = _prepare_mask(reflection, (width, height), parameters)
        reflection_alpha = np.asarray(reflection_image, dtype=np.float32) / 255.0
        reflection_amount = max(
            0.0, min(1.0, _number(parameters, "reflection_amount", 0.0))
        )
        reflected_texture = texture_layer.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        reflection_blur = max(
            0.0, min(20.0, _number(parameters, "reflection_blur", 0.0))
        )
        if reflection_blur:
            reflected_texture = reflected_texture.filter(
                ImageFilter.GaussianBlur(reflection_blur / 2.0)
            )
        reflection_alpha *= opacity * reflection_amount
        result_array = (
            np.asarray(result, dtype=np.float32) * (1.0 - reflection_alpha[..., None])
            + np.asarray(reflected_texture, dtype=np.float32) * reflection_alpha[..., None]
        )
        result = Image.fromarray(np.clip(result_array, 0.0, 255.0).astype(np.uint8), "RGB")
    relight = max(0.0, min(1.0, _number(parameters, "foreground_relight", 0.0)))
    if relight:
        result = _foreground_relight(
            base,
            result,
            mask_image,
            relight,
            parameters,
            foreground=foreground if isinstance(foreground, np.ndarray) else None,
        )
    return result


def _prepare_mask(
    mask: np.ndarray,
    size: tuple[int, int],
    parameters: dict[str, Any],
) -> Image.Image:
    values = np.asarray(mask, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError(f"sky mask must be 2D, got {values.shape}")
    values = np.clip(values, 0.0, 1.0)
    image = Image.fromarray((values * 255.0).astype(np.uint8), "L").resize(
        size, Image.Resampling.BILINEAR
    )
    global_amount = max(0.0, min(1.5, _number(parameters, "sky_global", 1.0)))
    if global_amount != 1.0:
        image = image.point(lambda value: max(0, min(255, round(value * global_amount))))
    fix_gaps = max(0.0, min(1.0, _number(parameters, "fix_gaps", 0.0)))
    if fix_gaps:
        kernel = 1 + 2 * max(1, round(fix_gaps * 5))
        image = image.filter(ImageFilter.MaxFilter(kernel))
    edge = max(0.0, min(20.0, _number(parameters, "edge_refinement", 6.0)))
    if edge:
        image = image.filter(ImageFilter.GaussianBlur(edge / 3.0))
    return image


def _protect_foreground(
    sky_mask: Image.Image,
    foreground: np.ndarray,
    size: tuple[int, int],
) -> Image.Image:
    values = np.asarray(foreground, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError(f"foreground mask must be 2D, got {values.shape}")
    subject = Image.fromarray(
        (np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8), "L"
    ).resize(size, Image.Resampling.BILINEAR)
    subject = subject.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    sky = np.asarray(sky_mask, dtype=np.float32) / 255.0
    protection = np.asarray(subject, dtype=np.float32) / 255.0
    protection = np.clip((protection - 0.25) / 0.5, 0.0, 1.0)
    protection = protection * protection * (3.0 - 2.0 * protection)
    return Image.fromarray(
        np.rint(np.clip(sky * (1.0 - protection), 0.0, 1.0) * 255.0).astype(np.uint8),
        "L",
    )


def _fit_texture(
    base: Image.Image, texture: Image.Image, parameters: dict[str, Any]
) -> Image.Image:
    width, height = base.size
    detected_horizon = parameters.get("_detected_horizon")
    uses_detected_horizon = isinstance(detected_horizon, (float, int)) and not isinstance(
        detected_horizon, bool
    )
    scale = max(0.25, min(4.0, _number(parameters, "sky_scale", 1.0)))
    if uses_detected_horizon:
        scale = min(4.0, scale * 1.3)
    ratio = texture.height / max(texture.width, 1)
    if uses_detected_horizon:
        horizon_control = _number(parameters, "horizon_offset", 0.58)
        horizon = float(detected_horizon) + (horizon_control - 0.58)
    else:
        horizon = _number(parameters, "horizon_offset", 0.58)
    horizon = max(0.05, min(0.95, horizon))
    sky_height = max(1.0, horizon * height)
    cover_scale = max(1.0, sky_height / max(width * ratio, 1.0))
    texture_size = (
        max(1, round(width * scale * cover_scale)),
        max(1, round(width * scale * ratio * cover_scale)),
    )
    fitted = texture.convert("RGB").resize(texture_size, Image.Resampling.LANCZOS)
    if bool(parameters.get("sky_flip", False)):
        fitted = fitted.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    horizontal = _number(parameters, "horizontal_offset", 0.0) * width
    vertical = _number(parameters, "vertical_offset", 0.0) * height
    rotation = max(-30.0, min(30.0, _number(parameters, "rotation", 0.0)))
    if rotation:
        fitted = fitted.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
    x = round((width - fitted.width) / 2 + horizontal)
    # Align the texture bottom with the detected horizon.  Horizon blending is
    # an alpha-transition concern; using it as a positive geometry offset puts
    # the texture top inside the canvas and forces the edge extender to mirror
    # a cloud band across the whole upper sky.
    y = round(horizon * height - fitted.height + vertical)
    return _edge_extended_layer(fitted, (width, height), (x, y))


def _edge_extended_layer(
    fitted: Image.Image,
    size: tuple[int, int],
    offset: tuple[int, int],
) -> Image.Image:
    """Position a texture and extend only a narrow band beyond its boundaries.

    Mirroring the complete texture below its fitted horizon creates a second,
    visibly inverted cloud field wherever a soft segmentation mask extends past
    that horizon. Repeating one boundary row instead creates vertical columns.
    A bounded edge-band extrapolation keeps the boundary continuous without
    introducing either structure into the composited foreground.
    """
    width, height = size
    x, y = offset
    source = np.asarray(fitted.convert("RGB"), dtype=np.uint8)
    source_x = _soft_extended_indices(width, x, fitted.width)
    source_y = _soft_extended_indices(height, y, fitted.height)
    return Image.fromarray(source[source_y[:, None], source_x[None, :]], "RGB")


def _soft_extended_indices(length: int, offset: int, source_length: int) -> np.ndarray:
    if source_length == 1:
        return np.zeros(length, dtype=np.intp)
    relative = np.arange(length, dtype=np.float32) - float(offset)
    indices = np.clip(relative, 0.0, float(source_length - 1))
    band = float(max(1, min(source_length - 1, round(source_length * 0.08))))
    before = relative < 0.0
    if np.any(before):
        distance = -relative[before]
        indices[before] = band * (1.0 - np.exp(-distance / band))
    after = relative > source_length - 1
    if np.any(after):
        distance = relative[after] - float(source_length - 1)
        indices[after] = float(source_length - 1) - band * (
            1.0 - np.exp(-distance / band)
        )
    return np.rint(indices).astype(np.intp)


def _match_texture(
    texture: Image.Image, base: Image.Image, parameters: dict[str, Any]
) -> Image.Image:
    brightness = _number(parameters, "brightness", 1.0)
    contrast = _number(parameters, "contrast", 1.0)
    saturation = _number(parameters, "saturation", 1.0)
    temperature = _number(parameters, "temperature", 0.0)
    result = ImageEnhance.Brightness(texture).enhance(max(0.1, min(3.0, brightness)))
    result = ImageEnhance.Contrast(result).enhance(max(0.1, min(3.0, contrast)))
    result = ImageEnhance.Color(result).enhance(max(0.0, min(3.0, saturation)))
    atmospheric_haze = max(
        0.0, min(1.0, _number(parameters, "atmospheric_haze", 0.0))
    )
    if atmospheric_haze:
        haze = Image.new("RGB", result.size, (215, 224, 232))
        result = Image.blend(result, haze, atmospheric_haze * 0.35)
    if temperature:
        array = np.asarray(result, dtype=np.float32)
        factor = max(-1.0, min(1.0, temperature))
        array[..., 0] *= 1.0 + 0.10 * factor
        array[..., 2] *= 1.0 - 0.10 * factor
        result = Image.fromarray(np.clip(array, 0.0, 255.0).astype(np.uint8), "RGB")
    return result


def _foreground_relight(
    base: Image.Image,
    result: Image.Image,
    mask: Image.Image,
    amount: float,
    parameters: dict[str, Any],
    *,
    foreground: np.ndarray | None = None,
) -> Image.Image:
    base_array = np.asarray(base, dtype=np.float32)
    result_array = np.asarray(result, dtype=np.float32)
    sky = np.asarray(mask, dtype=np.float32) / 255.0
    lower = 1.0 - sky
    height, width = sky.shape
    human = max(0.0, min(1.0, _number(parameters, "relight_human", 0.0)))
    scene_weight = lower * amount
    if foreground is not None:
        values = np.asarray(foreground, dtype=np.float32)
        if values.ndim != 2:
            raise ValueError(f"foreground mask must be 2D, got {values.shape}")
        human_mask = np.asarray(
            Image.fromarray(
                np.rint(np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8),
                "L",
            ).resize((width, height), Image.Resampling.BILINEAR),
            dtype=np.float32,
        ) / 255.0
    else:
        human_mask = np.zeros_like(scene_weight)
    weight = np.clip(scene_weight * 0.45 + human_mask * amount * human * 0.55, 0.0, 1.0)

    sky_total = float(sky.sum())
    if sky_total <= 1e-6:
        return result
    color_shift = (
        ((result_array - base_array) * sky[..., None]).sum(axis=(0, 1)) / sky_total
    )
    relit_array = result_array + color_shift[None, None, :] * weight[..., None]
    relit = Image.fromarray(np.clip(relit_array, 0.0, 255.0).astype(np.uint8), "RGB")
    saturation = max(0.0, min(2.0, _number(parameters, "relight_saturation", 1.0)))
    if saturation != 1.0:
        saturated = ImageEnhance.Color(relit).enhance(saturation)
        relight_mask = Image.fromarray(
            np.clip(weight * 255.0, 0.0, 255.0).astype(np.uint8), "L"
        )
        relit = Image.composite(saturated, relit, relight_mask)
    return relit


def _add_grain(image: Image.Image, amount: float) -> Image.Image:
    amount = max(0.0, min(1.0, amount))
    if not amount:
        return image
    array = np.asarray(image, dtype=np.float32)
    yy, xx = np.indices(array.shape[:2], dtype=np.uint32)
    noise = ((xx * 1973 + yy * 9277 + 89173) % 255).astype(np.float32) / 127.5 - 1.0
    return Image.fromarray(
        np.clip(array + noise[..., None] * (amount * 18.0), 0.0, 255.0).astype(np.uint8),
        "RGB",
    )


def _number(parameters: dict[str, Any], name: str, default: float) -> float:
    value = parameters.get(name, default)
    return (
        float(value) if isinstance(value, (float, int)) and not isinstance(value, bool) else default
    )
