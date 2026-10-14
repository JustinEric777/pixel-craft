"""ONNX Runtime wrapper for converted Luminar sky-reflection segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import binary_class_mask


class SkyinwaterV16I8OnnxInference(OnnxInference):
    model_id = "skyinwater_v16_i8_onnx"
    task_type = "sky_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("size", (513, 513))
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        size = tuple(kwargs.get("size", (513, 513)))
        return {"mask": binary_class_mask(outputs, size)}
