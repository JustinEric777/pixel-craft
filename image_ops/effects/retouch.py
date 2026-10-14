"""Coordinate-driven local retouch effects shared by preview and export."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def apply_retouch(
    image: Image.Image,
    effect: str,
    strokes: list[dict[str, Any]],
    amount: float,
) -> Image.Image:
    if not strokes:
        return image.convert("RGB")
    if effect == "dodge_burn":
        return _dodge_burn(image, strokes, amount)
    if effect == "clone":
        return _clone(image, strokes)
    if effect == "erase":
        return _erase(image, strokes)
    raise ValueError(f"unknown retouch effect: {effect}")


def _stroke_mask(size: tuple[int, int], strokes: list[dict[str, Any]]) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for stroke in strokes:
        points = [
            (float(point[0]) * width, float(point[1]) * height)
            for point in stroke.get("points", [])
        ]
        if not points:
            continue
        radius = max(1, round(float(stroke.get("radius", 0.04)) * min(size)))
        draw.line(points, fill=255, width=radius * 2, joint="curve")
        for x, y in (points[0], points[-1]):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(1.0, min(size) * 0.004)))


def _dodge_burn(
    image: Image.Image,
    strokes: list[dict[str, Any]],
    amount: float,
) -> Image.Image:
    mask = np.asarray(_stroke_mask(image.size, strokes), dtype=np.float32) / 255.0
    strength = max(-1.0, min(1.0, amount))
    source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    if strength >= 0.0:
        adjusted = 1.0 - (1.0 - source) * (1.0 - strength * 0.55)
    else:
        adjusted = source * (1.0 + strength * 0.55)
    output = source * (1.0 - mask[..., None]) + adjusted * mask[..., None]
    return Image.fromarray(np.rint(np.clip(output, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")


def _clone(image: Image.Image, strokes: list[dict[str, Any]]) -> Image.Image:
    result = image.convert("RGB")
    width, height = result.size
    for stroke in strokes:
        source_point = stroke.get("source")
        points = stroke.get("points", [])
        if not source_point or not points:
            continue
        radius = max(2, round(float(stroke.get("radius", 0.04)) * min(result.size)))
        source_x = float(source_point[0]) * width
        source_y = float(source_point[1]) * height
        target_origin_x = float(points[0][0]) * width
        target_origin_y = float(points[0][1]) * height
        for point in points:
            target_x, target_y = float(point[0]) * width, float(point[1]) * height
            sample_x = source_x + target_x - target_origin_x
            sample_y = source_y + target_y - target_origin_y
            box = (
                round(sample_x - radius),
                round(sample_y - radius),
                round(sample_x + radius),
                round(sample_y + radius),
            )
            patch = image.convert("RGB").crop(box)
            if patch.size != (radius * 2, radius * 2):
                continue
            alpha = Image.new("L", patch.size, 0)
            ImageDraw.Draw(alpha).ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=255)
            alpha = alpha.filter(ImageFilter.GaussianBlur(max(1.0, radius * 0.18)))
            result.paste(patch, (round(target_x - radius), round(target_y - radius)), alpha)
    return result


def _erase(image: Image.Image, strokes: list[dict[str, Any]]) -> Image.Image:
    source = image.convert("RGB")
    mask = _stroke_mask(source.size, strokes)
    image_levels = [source]
    mask_levels = [mask]
    while min(image_levels[-1].size) > 24 and len(image_levels) < 7:
        next_size = (
            max(1, image_levels[-1].width // 2),
            max(1, image_levels[-1].height // 2),
        )
        image_levels.append(image_levels[-1].resize(next_size, Image.Resampling.BILINEAR))
        mask_levels.append(mask_levels[-1].resize(next_size, Image.Resampling.BILINEAR))
    smallest = np.asarray(image_levels[-1], dtype=np.float32)
    smallest_mask = np.asarray(mask_levels[-1], dtype=np.float32) / 255.0
    known = smallest_mask < 0.25
    color = smallest[known].mean(axis=0) if np.any(known) else smallest.mean(axis=(0, 1))
    filled = Image.fromarray(
        np.where(known[..., None], smallest, color).astype(np.uint8),
        "RGB",
    )
    for level in range(len(image_levels) - 2, -1, -1):
        filled = filled.resize(image_levels[level].size, Image.Resampling.BILINEAR)
        known_mask = Image.eval(mask_levels[level], lambda value: 255 - value)
        filled = Image.composite(image_levels[level], filled, known_mask)
        filled = filled.filter(ImageFilter.GaussianBlur(0.65))
    feather = mask.filter(ImageFilter.GaussianBlur(max(1.0, min(source.size) * 0.006)))
    return Image.composite(filled, source, feather)
