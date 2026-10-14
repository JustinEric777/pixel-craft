"""Inference wrapper for ``face_landmarks_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import heatmap_landmarks


class FaceLandmarksI8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``face_landmarks_i8``."""

    model_id = "face_landmarks_i8"
    task_type = "face_analysis"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return heatmap_landmarks(outputs)
