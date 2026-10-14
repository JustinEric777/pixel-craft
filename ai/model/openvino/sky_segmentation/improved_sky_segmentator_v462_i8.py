"""Inference wrapper for ``improved_sky_segmentator_v462_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import binary_class_mask


class ImprovedSkySegmentatorV462I8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``improved_sky_segmentator_v462_i8``."""

    model_id = "improved_sky_segmentator_v462_i8"
    task_type = "sky_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        size = tuple(kwargs.get("size", (513, 513)))
        return {"mask": binary_class_mask(outputs, size)}
