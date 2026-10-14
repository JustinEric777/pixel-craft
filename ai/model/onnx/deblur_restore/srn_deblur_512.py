"""Inference wrapper for ``srn_deblur_512``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import first_tensor


class SrnDeblur512Inference(OnnxInference):
    """Own the inference lifecycle boundary for ``srn_deblur_512``."""

    model_id = "srn_deblur_512"
    task_type = "deblur_restore"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(512, 512))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        restored = first_tensor(outputs).astype(np.float32, copy=False)
        if restored.shape != (1, 3, 512, 512):
            raise ValueError(f"SRN deblur output is invalid: {restored.shape}")
        return {"restored": np.clip(restored, 0.0, 1.0)}
