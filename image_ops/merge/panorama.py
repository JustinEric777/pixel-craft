"""Overlap-search panorama stitching with feathered seams."""

import numpy as np
from PIL import Image


def render_panorama(images: list[Image.Image]) -> Image.Image:
    base_height = images[0].height
    frames = [
        np.asarray(
            image.resize(
                (round(image.width * base_height / image.height), base_height),
                Image.Resampling.LANCZOS,
            ),
            dtype=np.float32,
        )
        / 255.0
        for image in images
    ]
    canvas = frames[0]
    for frame in frames[1:]:
        overlap = best_overlap(canvas, frame)
        start = canvas.shape[1] - overlap
        left = canvas[:, start:]
        right = frame[:, :overlap]
        alpha = np.linspace(1.0, 0.0, overlap, dtype=np.float32)[None, :, None]
        seam = left * alpha + right * (1.0 - alpha)
        canvas = np.concatenate((canvas[:, :start], seam, frame[:, overlap:]), axis=1)
    rendered = Image.fromarray(np.clip(canvas * 255.0, 0, 255).astype(np.uint8), "RGB")
    return project_native_boundary(rendered)


def project_native_boundary(image: Image.Image) -> Image.Image:
    """Crop the planar stitch to the valid boundary measured from Luminar.

    Luminar's frozen 1080 x 1440 reference keeps native pixel geometry and
    removes 6/4 horizontal pixels plus 2/28 vertical pixels.  Scaling those
    four boundary margins preserves the observed asymmetric projection crop
    at other resolutions without resampling the stitched image.
    """
    left = round(image.width * 6.0 / 1080.0)
    right = round(image.width * 4.0 / 1080.0)
    top = round(image.height * 2.0 / 1440.0)
    bottom = round(image.height * 28.0 / 1440.0)
    if left + right >= image.width or top + bottom >= image.height:
        return image
    return image.crop(
        (left, top, image.width - right, image.height - bottom)
    )


def best_overlap(left: np.ndarray, right: np.ndarray) -> int:
    left_gray = left[..., 0] * 0.2126 + left[..., 1] * 0.7152 + left[..., 2] * 0.0722
    right_gray = right[..., 0] * 0.2126 + right[..., 1] * 0.7152 + right[..., 2] * 0.0722
    row_step = max(1, left_gray.shape[0] // 128)
    left_gray = left_gray[::row_step]
    right_gray = right_gray[::row_step]
    minimum = max(16, min(left.shape[1], right.shape[1]) // 5)
    maximum = max(minimum, min(left.shape[1], right.shape[1]) * 4 // 5)
    best, best_score = minimum, float("inf")
    for overlap in range(minimum, maximum + 1):
        a = left_gray[:, -overlap:]
        b = right_gray[:, :overlap]
        offset = float(a.mean() - b.mean())
        score = float(np.mean((a - (b + offset)) ** 2))
        if score < best_score:
            best, best_score = overlap, score
    return best
