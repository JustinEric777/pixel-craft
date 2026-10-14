"""Shared tensor-output interpretation for analysis and edit pipelines."""

import numpy as np


def mask_horizon(mask: np.ndarray) -> float:
    rows = np.where(np.mean(np.asarray(mask) > 0.28, axis=1) > 0.05)[0]
    if not rows.size:
        return 0.58
    return float(np.clip((rows[-1] + 1) / mask.shape[0], 0.22, 0.82))


def is_probability_output(name: str, values: np.ndarray) -> bool:
    """Return true when a model output already contains normalized probabilities."""
    lowered = name.lower()
    if any(token in lowered for token in ("softmax", "sigmoid", "proba", "probability")):
        return True
    array = np.asarray(values, dtype=np.float32)
    if not array.size or not np.isfinite(array).all():
        return False
    if float(array.min()) < 0.0 or float(array.max()) > 1.0:
        return False
    if array.ndim >= 2 and array.shape[-1] == 2:
        sums = np.sum(array, axis=-1)
        return bool(np.allclose(sums, 1.0, atol=0.02, rtol=0.02))
    return False
