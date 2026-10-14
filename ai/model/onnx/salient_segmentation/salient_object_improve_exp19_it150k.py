"""Inference wrapper for ``salient_object_improve_exp19_it150k``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import binary_class_mask


class SalientObjectImproveExp19It150KInference(OnnxInference):
    """Own the inference lifecycle boundary for ``salient_object_improve_exp19_it150k``."""

    model_id = "salient_object_improve_exp19_it150k"
    task_type = "salient_segmentation"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(512, 512))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return {"mask": binary_class_mask(outputs, (512, 512))}
