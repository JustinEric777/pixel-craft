"""ONNX Runtime wrapper for converted ``hair_exp11_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import single_channel_mask


class HairExp11I8OnnxInference(OnnxInference):
    model_id = "hair_exp11_i8_onnx"
    task_type = "hair_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return {"mask": single_channel_mask(outputs, (513, 513))}
