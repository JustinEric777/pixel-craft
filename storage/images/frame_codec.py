"""Pillow <-> ImageFrame codec kept outside the core/services layers."""

from __future__ import annotations

import numpy as np
from PIL import Image

from core.image_frame import ImageFrame


def frame_from_pillow(image: Image.Image) -> ImageFrame:
    profile = image.info.get("icc_profile")
    mode = image.mode
    if mode == "RGBA":
        pixels = np.asarray(image, dtype=np.uint8)
        order = "RGBA"
        alpha_mode = "straight"
    else:
        pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
        order = "RGB"
        alpha_mode = "none"
    return ImageFrame(
        pixels=np.ascontiguousarray(pixels),
        color_space="sRGB",
        channel_order=order,
        alpha_mode=alpha_mode,
        bit_depth=8,
        icc_profile=profile if isinstance(profile, bytes) else None,
        metadata={"source_mode": mode},
    )


def pillow_from_frame(frame: ImageFrame) -> Image.Image:
    values = frame.rgb8()
    image = Image.fromarray(values, "RGB")
    if frame.icc_profile:
        image.info["icc_profile"] = frame.icc_profile
    return image
