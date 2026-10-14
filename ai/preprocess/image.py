"""Image preprocessing shared by model-specific pipelines."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ResizeTransform:
    original_size: tuple[int, int]
    model_size: tuple[int, int]

    def restore_mask(self, mask: np.ndarray) -> np.ndarray:
        image = Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8))
        image = image.resize(self.original_size, Image.Resampling.BILINEAR)
        return np.asarray(image, dtype=np.float32) / 255.0

    def restore_labels(self, labels: np.ndarray) -> np.ndarray:
        """Restore integer segmentation labels without interpolating classes."""
        image = Image.fromarray(np.asarray(labels, dtype=np.uint8), "L")
        image = image.resize(self.original_size, Image.Resampling.NEAREST)
        return np.asarray(image, dtype=np.uint8)


def image_to_nchw(
    image: Image.Image,
    size: tuple[int, int],
    *,
    value_range: tuple[float, float] = (0.0, 1.0),
    mean: tuple[float, float, float] | None = None,
    std: tuple[float, float, float] | None = None,
) -> tuple[np.ndarray, ResizeTransform]:
    rgb = image.convert("RGB")
    resized = rgb.resize(size, Image.Resampling.BILINEAR)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    low, high = value_range
    array = low + array * (high - low)
    if mean is not None:
        array = array - np.asarray(mean, dtype=np.float32)
    if std is not None:
        array = array / np.asarray(std, dtype=np.float32)
    return np.transpose(array, (2, 0, 1))[None, ...].astype(np.float32), ResizeTransform(
        rgb.size, size
    )


def nchw_to_image(output: np.ndarray, value_range: tuple[float, float] = (0.0, 1.0)) -> Image.Image:
    array = np.asarray(output)
    if array.ndim == 4:
        array = array[0]
    if array.shape[0] in {1, 3, 4}:
        array = np.transpose(array, (1, 2, 0))
    low, high = value_range
    array = (array - low) / (high - low)
    array = np.clip(array, 0.0, 1.0)
    if array.shape[-1] == 1:
        array = array[..., 0]
    return Image.fromarray((array * 255.0).astype(np.uint8))


def softmax(values: np.ndarray, axis: int = 1) -> np.ndarray:
    shifted = values - np.max(values, axis=axis, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=axis, keepdims=True)
