"""Shared image normalization for multi-image workflows."""

import numpy as np
from PIL import Image


def same_size(images: list[Image.Image]) -> list[np.ndarray]:
    width, height = images[0].size
    return [
        np.asarray(
            image.resize((width, height), Image.Resampling.LANCZOS), dtype=np.float32
        )
        / 255.0
        for image in images
    ]
