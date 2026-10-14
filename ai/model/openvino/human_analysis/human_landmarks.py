"""Inference wrapper for ``HumanLandmarks``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import dense_nhwc_heatmaps


class HumanLandmarksInference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``HumanLandmarks``."""

    model_id = "HumanLandmarks"
    task_type = "human_analysis"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return dense_nhwc_heatmaps(outputs, channels=18)
