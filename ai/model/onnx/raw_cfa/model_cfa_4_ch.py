"""Inference wrapper for ``model_cfa_4_ch``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference


class ModelCfa4ChInference(OnnxInference):
    """Own the inference lifecycle boundary for ``model_cfa_4_ch``."""

    model_id = "model_cfa_4_ch"
    task_type = "raw_cfa"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
