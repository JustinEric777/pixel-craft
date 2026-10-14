"""Inference wrapper for ``SemanticSearchImage``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import first_tensor


class SemanticSearchImageInference(OnnxInference):
    """Own the inference lifecycle boundary for ``SemanticSearchImage``."""

    model_id = "SemanticSearchImage"
    task_type = "image_embedding"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(
            image,
            size=(224, 224),
            mean=(0.48145466, 0.4578275, 0.40821073),
            std=(0.26862954, 0.26130258, 0.27577711),
        )

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        vector = first_tensor(outputs).astype(np.float32, copy=False).reshape(-1)
        vector = vector / max(float(np.linalg.norm(vector)), 1e-8)
        return {"vector": vector}
