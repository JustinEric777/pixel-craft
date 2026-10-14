"""ONNX Runtime wrapper for the converted ``convnextv2_multiclass`` model."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import multiclass_segmentation


class ConvnextV2MulticlassOnnxInference(OnnxInference):
    """Expose finite eight-class probabilities and a label map through ORT."""

    model_id = "convnextv2_multiclass_onnx"
    task_type = "semantic_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("size", (512, 512))
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return multiclass_segmentation(outputs)
