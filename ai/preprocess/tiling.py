"""Deterministic overlapping tile planning and feathered image stitching."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    width: int
    height: int


def plan_tiles(
    width: int,
    height: int,
    tile_size: tuple[int, int],
    overlap: float = 0.125,
) -> list[Tile]:
    """Cover a frame with stable, edge-aligned tiles."""
    tile_width, tile_height = tile_size
    if width <= 0 or height <= 0 or tile_width <= 0 or tile_height <= 0:
        raise ValueError("image and tile dimensions must be positive")
    overlap = max(0.0, min(0.45, overlap))
    step_x = max(1, round(tile_width * (1.0 - overlap)))
    step_y = max(1, round(tile_height * (1.0 - overlap)))
    xs = sorted({min(max(0, width - tile_width), index * step_x) for index in range(ceil(width / step_x) + 1)})
    ys = sorted({min(max(0, height - tile_height), index * step_y) for index in range(ceil(height / step_y) + 1)})
    return [
        Tile(x, y, min(tile_width, width - x), min(tile_height, height - y))
        for y in ys
        for x in xs
    ]


def feather_window(width: int, height: int, edge: int = 16) -> np.ndarray:
    """Return a non-zero 2D blending weight with softened tile edges."""
    edge = max(0, min(min(width, height) // 2, edge))
    if edge == 0:
        return np.ones((height, width), dtype=np.float32)
    x = np.minimum(np.arange(width) + 1, np.arange(width, 0, -1)).astype(np.float32)
    y = np.minimum(np.arange(height) + 1, np.arange(height, 0, -1)).astype(np.float32)
    return np.clip(np.minimum(y[:, None], x[None, :]) / edge, 0.05, 1.0).astype(np.float32)


def stitch_tiles(
    tiles: list[tuple[Tile, np.ndarray]],
    output_size: tuple[int, int],
    scale: float = 1.0,
    edge: int = 16,
) -> np.ndarray:
    """Feather model outputs back into one RGB float image."""
    if not tiles:
        raise ValueError("at least one tile is required")
    width, height = output_size
    target_width, target_height = round(width * scale), round(height * scale)
    first = np.asarray(tiles[0][1], dtype=np.float32)
    channels = first.shape[2] if first.ndim == 3 else 1
    output = np.zeros((target_height, target_width, channels), dtype=np.float32)
    weights = np.zeros((target_height, target_width, 1), dtype=np.float32)
    for tile, value in tiles:
        value = np.asarray(value, dtype=np.float32)
        if value.ndim == 2:
            value = value[..., None]
        x0, y0 = round(tile.x * scale), round(tile.y * scale)
        expected_width, expected_height = round(tile.width * scale), round(tile.height * scale)
        if value.shape[:2] != (expected_height, expected_width):
            from PIL import Image

            if value.ndim == 3:
                value = np.stack(
                    [
                        np.asarray(
                            Image.fromarray(value[..., channel], "F").resize(
                                (expected_width, expected_height), Image.Resampling.BILINEAR
                            ),
                            dtype=np.float32,
                        )
                        for channel in range(value.shape[2])
                    ],
                    axis=2,
                )
            else:
                value = np.asarray(
                    Image.fromarray(value, "F").resize(
                        (expected_width, expected_height), Image.Resampling.BILINEAR
                    ),
                    dtype=np.float32,
                )
            if value.ndim == 2:
                value = value[..., None]
        window = feather_window(expected_width, expected_height, round(edge * scale))[..., None]
        output[y0 : y0 + expected_height, x0 : x0 + expected_width] += value * window
        weights[y0 : y0 + expected_height, x0 : x0 + expected_width] += window
    return output / np.maximum(weights, 1e-6)
