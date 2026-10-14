"""Inference wrapper for ``LPTN_exp108_wires``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference


class LPTNExp108WiresInference(OnnxInference):
    """Own the inference lifecycle boundary for ``LPTN_exp108_wires``."""

    model_id = "LPTN_exp108_wires"
    task_type = "wire_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
