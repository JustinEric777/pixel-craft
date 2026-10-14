"""ONNX Runtime wrapper for converted skin imperfection segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import binary_class_mask


class ImperfectionDetectorI8OnnxInference(OnnxInference):
    model_id = "imperfection_detector_i8_onnx"
    task_type = "imperfection_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return {"mask": binary_class_mask(outputs, (513, 513))}
