"""ONNX Runtime wrapper for converted Luminar saliency segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import single_channel_mask


class SaliencyMapI8OnnxInference(OnnxInference):
    model_id = "saliency_map_i8_onnx"
    task_type = "saliency_segmentation"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(256, 256))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return {"mask": single_channel_mask(outputs, (256, 256))}
