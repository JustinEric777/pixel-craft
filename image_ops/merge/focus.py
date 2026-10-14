"""Gradient-confidence focus stacking."""

import numpy as np
from PIL import Image, ImageFilter

from .common import same_size


def render_focus_stack(images: list[Image.Image]) -> Image.Image:
    frames = same_size(images)
    scores: list[np.ndarray] = []
    for frame in frames:
        gray = frame[..., 0] * 0.2126 + frame[..., 1] * 0.7152 + frame[..., 2] * 0.0722
        gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
        gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
        score = np.clip(gx + gy, 0, 1)
        score_image = Image.fromarray(np.uint8(score * 255.0), "L").filter(
            ImageFilter.GaussianBlur(1.0)
        )
        scores.append(np.asarray(score_image, dtype=np.float32) / 255.0)
    score_stack = np.stack(scores)
    # Preserve the sharp source sample at every pixel. A soft weighted average
    # re-introduces blur from the out-of-focus frames and cannot reproduce the
    # native focus-stack result even when the source zones are complementary.
    selected = np.argmax(score_stack, axis=0)
    result = np.take_along_axis(
        np.stack(frames), selected[None, ..., None], axis=0
    )[0]
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGB")
