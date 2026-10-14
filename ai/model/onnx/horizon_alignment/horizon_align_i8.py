"""ONNX Runtime wrapper for converted ``horizon_align_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference


class HorizonAlignI8OnnxInference(OnnxInference):
    model_id = "horizon_align_i8_onnx"
    task_type = "horizon_alignment"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("size", (224, 224))
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, Any]:
        if not outputs:
            raise ValueError("horizon model returned no outputs")
        return {"angle": float(np.asarray(next(iter(outputs.values()))).mean())}
