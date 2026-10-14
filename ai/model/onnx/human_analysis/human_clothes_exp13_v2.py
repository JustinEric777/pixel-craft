"""ONNX Runtime wrapper for converted human/clothes segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import multiclass_segmentation


class HumanClothesExp13V2OnnxInference(OnnxInference):
    model_id = "human_clothes_exp13_v2_onnx"
    task_type = "human_clothes_segmentation"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(1024, 1024))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return multiclass_segmentation(outputs)
