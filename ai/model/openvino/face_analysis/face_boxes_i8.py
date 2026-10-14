"""Inference wrapper for ``face_boxes_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import detection_boxes


class FaceBoxesI8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``face_boxes_i8``."""

    model_id = "face_boxes_i8"
    task_type = "face_analysis"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        inputs = super().preprocess(image, **kwargs)
        return {name: values * 255.0 for name, values in inputs.items()}

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return detection_boxes(outputs)
