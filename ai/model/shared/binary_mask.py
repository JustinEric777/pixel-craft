"""Validated binary segmentation output conversion."""

from __future__ import annotations

from typing import Any

import numpy as np


def binary_class_mask(outputs: dict[str, Any], size: tuple[int, int]) -> np.ndarray:
    """Take foreground class index 1 and return a two-dimensional mask."""
    if not outputs:
        raise ValueError("segmentation model returned no outputs")
    values = np.asarray(next(iter(outputs.values())), dtype=np.float32)
    if values.ndim == 4 and values.shape[1] == 2 and (
        float(values.min()) < 0.0 or float(values.max()) > 1.0
    ):
        shifted = values - values.max(axis=1, keepdims=True)
        exponential = np.exp(np.clip(shifted, -30.0, 30.0))
        values = exponential / np.maximum(exponential.sum(axis=1, keepdims=True), 1e-8)
    if values.ndim == 2 and values.shape[-1] == 2:
        mask = values[:, 1]
    elif values.ndim == 3 and values.shape[-1] == 2:
        mask = values[..., 1]
    elif values.ndim == 4 and values.shape[1] > 1:
        mask = values[0, 1]
    elif values.ndim == 4 and values.shape[-1] > 1:
        mask = values[0, ..., 1]
    else:
        raise ValueError(f"expected binary class output, got {values.shape}")
    expected = size[0] * size[1]
    if mask.size != expected:
        raise ValueError(f"expected {expected} mask values, got {mask.size}")
    return mask.reshape(size[1], size[0])


def single_channel_mask(outputs: dict[str, Any], size: tuple[int, int]) -> np.ndarray:
    """Return a normalized mask from a one-channel probability or logit output."""
    if not outputs:
        raise ValueError("segmentation model returned no outputs")
    values = np.squeeze(np.asarray(next(iter(outputs.values())), dtype=np.float32))
    expected = size[0] * size[1]
    if values.size != expected:
        raise ValueError(f"expected {expected} mask values, got {values.size}")
    if float(values.min()) < 0.0 or float(values.max()) > 1.0:
        values = 1.0 / (1.0 + np.exp(-np.clip(values, -30.0, 30.0)))
    return np.clip(values.reshape(size[1], size[0]), 0.0, 1.0)
