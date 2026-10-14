"""ONNX Runtime wrapper for Luminar's magic-lights detector."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import yolo_light_boxes


class MagicLightsExp37OnnxInference(OnnxInference):
    model_id = "magic_lights_exp37_dataset123_1024_onnx"
    task_type = "light_detection"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(1024, 1024))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return yolo_light_boxes(outputs)
