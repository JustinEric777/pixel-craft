"""Deterministic bracket fusion and calibrated display tone mapping."""

import numpy as np
from PIL import Image

from .common import same_size


def render_hdr(images: list[Image.Image]) -> Image.Image:
    frames = same_size(images)
    stack = np.stack(frames)
    merged = np.mean(stack, axis=0)
    exposure_spread = float(np.mean(np.std(stack, axis=0)))
    if exposure_spread < 1e-4:
        tone_mapped = merged
    else:
        # Luminar's default HDR output lifts midtones while keeping the display
        # white point fixed.  Avoid image-dependent peak normalization: one hot
        # pixel must not change the exposure of the complete export.
        tone_mapped = np.power(np.clip(merged, 0.0, 1.0), 0.8) * 1.2
    return Image.fromarray(np.clip(tone_mapped * 255.0, 0, 255).astype(np.uint8), "RGB")
