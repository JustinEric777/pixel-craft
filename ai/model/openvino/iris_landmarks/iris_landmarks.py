"""Inference wrapper for ``IrisLandmarks``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import dense_nhwc_heatmaps


class IrisLandmarksInference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``IrisLandmarks``."""

    model_id = "IrisLandmarks"
    task_type = "iris_landmarks"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return dense_nhwc_heatmaps(outputs, channels=18)
