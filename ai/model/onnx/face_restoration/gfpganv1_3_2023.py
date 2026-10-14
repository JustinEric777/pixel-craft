"""Inference wrapper for ``GFPGANv1.3_2023``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import first_tensor


class GFPGANv132023Inference(OnnxInference):
    """Own the inference lifecycle boundary for ``GFPGANv1.3_2023``."""

    model_id = "GFPGANv1.3_2023"
    task_type = "face_restoration"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        inputs = super().preprocess(image, size=(512, 512))
        return {name: values * 2.0 - 1.0 for name, values in inputs.items()}

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        restored = first_tensor(outputs).astype(np.float32, copy=False)
        return {"restored": np.clip((restored + 1.0) * 0.5, 0.0, 1.0)}
