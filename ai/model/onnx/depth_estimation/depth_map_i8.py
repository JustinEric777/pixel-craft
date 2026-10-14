"""ONNX Runtime wrapper for converted ``depth_map_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import normalized_depth


class DepthMapI8OnnxInference(OnnxInference):
    model_id = "depth_map_i8_onnx"
    task_type = "depth_estimation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return {"depth": normalized_depth(outputs)}
