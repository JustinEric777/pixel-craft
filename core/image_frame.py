"""Runtime-neutral image frame contract used by preview, export and AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ImageFrame:
    """A validated image plus the metadata required for deterministic edits."""

    pixels: np.ndarray
    color_space: str = "sRGB"
    channel_order: str = "RGB"
    alpha_mode: str = "none"
    bit_depth: int = 8
    icc_profile: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        pixels = np.asarray(self.pixels)
        if pixels.ndim != 3 or pixels.shape[2] not in {3, 4}:
            raise ValueError("ImageFrame pixels must have shape HxWx3 or HxWx4")
        if self.channel_order not in {"RGB", "RGBA", "BGR", "BGRA"}:
            raise ValueError(f"unsupported channel order: {self.channel_order}")
        if self.bit_depth not in {8, 16, 32}:
            raise ValueError(f"unsupported bit depth: {self.bit_depth}")

    @property
    def size(self) -> tuple[int, int]:
        return self.pixels.shape[1], self.pixels.shape[0]

    def rgb8(self) -> np.ndarray:
        """Return a contiguous RGB uint8 view for existing model adapters."""
        values = np.asarray(self.pixels)
        if values.dtype != np.uint8:
            if np.issubdtype(values.dtype, np.floating):
                values = np.clip(values * (255.0 if float(values.max(initial=0)) <= 1.0 else 1.0), 0, 255)
            elif values.dtype == np.uint16:
                values = values / 257.0
            values = values.astype(np.uint8)
        if self.channel_order in {"BGR", "BGRA"}:
            values = values[..., ::-1]
        return np.ascontiguousarray(values[..., :3])
