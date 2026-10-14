"""Inference wrapper for ``human_clothes_exp13_v2``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import multiclass_segmentation


class HumanClothesExp13V2Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``human_clothes_exp13_v2``."""

    model_id = "human_clothes_exp13_v2"
    task_type = "human_analysis"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(1024, 1024))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return multiclass_segmentation(outputs)
