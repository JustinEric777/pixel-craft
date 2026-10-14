"""Inference wrapper for ``face_detector_retinaface``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import retinaface_detections


class FaceDetectorRetinafaceInference(OnnxInference):
    """Own the inference lifecycle boundary for ``face_detector_retinaface``."""

    model_id = "face_detector_retinaface"
    task_type = "face_detection"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return retinaface_detections(
            outputs,
            confidence_threshold=float(kwargs.get("confidence_threshold", 0.5)),
        )
