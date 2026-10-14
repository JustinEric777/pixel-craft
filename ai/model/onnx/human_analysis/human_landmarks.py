"""ONNX Runtime wrapper for converted dense human landmark heatmaps."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import dense_nhwc_heatmaps


class HumanLandmarksOnnxInference(OnnxInference):
    model_id = "HumanLandmarks_onnx"
    task_type = "human_analysis"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return dense_nhwc_heatmaps(outputs, channels=18)
