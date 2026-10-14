"""Deterministic screenshot stability checks for Luminar preview polling."""

from __future__ import annotations

from collections.abc import Iterable
from itertools import pairwise
from pathlib import Path

import numpy as np
from PIL import Image


def screenshot_mae(left: Path, right: Path) -> float:
    with Image.open(left) as left_image, Image.open(right) as right_image:
        left_rgb = np.asarray(left_image.convert("RGB"), dtype=np.float32) / 255.0
        right_rgb = np.asarray(right_image.convert("RGB"), dtype=np.float32) / 255.0
    if left_rgb.shape != right_rgb.shape:
        return 1.0
    return float(np.abs(left_rgb - right_rgb).mean())


def normalized_image_mae(
    left: Path,
    right: Path,
    *,
    size: int | None = None,
    mode: str = "RGB",
) -> float:
    """Compare rendered image content after normalizing dimensions."""

    with Image.open(left) as left_image, Image.open(right) as right_image:
        left_render = left_image.convert(mode)
        target_size = (size, size) if size is not None else left_render.size
        left_render = left_render.resize(target_size)
        right_render = right_image.convert(mode).resize(target_size)
        left_array = np.asarray(left_render, dtype=np.float32) / 255.0
        right_array = np.asarray(right_render, dtype=np.float32) / 255.0
    return float(np.abs(left_array - right_array).mean())


def normalized_image_change_metrics(
    left: Path,
    right: Path,
    *,
    size: int = 256,
    pixel_delta: float = 0.04,
) -> dict[str, float]:
    """Measure global and localized rendered changes after size normalization."""

    if size <= 0:
        raise ValueError("normalized image comparison size must be positive")
    if not 0.0 < pixel_delta <= 1.0:
        raise ValueError("pixel delta must be in the range (0, 1]")
    target_size = (size, size)
    with Image.open(left) as left_image, Image.open(right) as right_image:
        left_array = (
            np.asarray(left_image.convert("RGB").resize(target_size), dtype=np.float32)
            / 255.0
        )
        right_array = (
            np.asarray(right_image.convert("RGB").resize(target_size), dtype=np.float32)
            / 255.0
        )
    delta = np.abs(left_array - right_array)
    return {
        "mae": float(delta.mean()),
        "strong_changed_pixel_fraction": float(
            np.any(delta >= pixel_delta, axis=2).mean()
        ),
    }


def stable_screenshot_sequence(
    paths: Iterable[Path], *, required: int, mae_max: float
) -> bool:
    if required < 2:
        raise ValueError("stable screenshot sequence requires at least two samples")
    ordered_paths = tuple(paths)
    if len(ordered_paths) < required:
        return False
    recent = ordered_paths[-required:]
    return all(
        screenshot_mae(previous, current) <= mae_max
        for previous, current in pairwise(recent)
    )
