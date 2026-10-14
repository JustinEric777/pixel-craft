"""ONNX Runtime wrapper for converted ``face_boxes_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import detection_boxes


class FaceBoxesI8OnnxInference(OnnxInference):
    model_id = "face_boxes_i8_onnx"
    task_type = "face_detection"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        inputs = super().preprocess(image, **kwargs)
        # This graph contains its own per-channel scale/subtract stage and was
        # trained for raw 8-bit RGB values, unlike the [0,1] segmentation nets.
        return {name: values * 255.0 for name, values in inputs.items()}

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return detection_boxes(outputs)
