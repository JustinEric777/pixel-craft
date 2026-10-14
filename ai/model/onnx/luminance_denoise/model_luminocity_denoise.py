"""Inference wrapper for ``model_luminocity_denoise``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import first_tensor


class ModelLuminocityDenoiseInference(OnnxInference):
    """Own the inference lifecycle boundary for ``model_luminocity_denoise``."""

    model_id = "model_luminocity_denoise"
    task_type = "luminance_denoise"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(256, 256), channels=1)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        luminance = first_tensor(outputs).astype(np.float32, copy=False)
        if luminance.shape != (1, 1, 256, 256):
            raise ValueError(f"luminance denoise output is invalid: {luminance.shape}")
        return {"luminance": np.clip(luminance, 0.0, 1.0)}
