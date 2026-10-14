"""ONNX Runtime wrapper for converted ``image_classifier_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import first_tensor


class ImageClassifierI8OnnxInference(OnnxInference):
    model_id = "image_classifier_i8_onnx"
    task_type = "image_classification"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        scores = np.squeeze(first_tensor(outputs)).astype(np.float32, copy=False)
        indices = np.argsort(scores)[::-1][:20].astype(np.int32)
        return {"indices": indices, "scores": scores[indices], "all_scores": scores}
