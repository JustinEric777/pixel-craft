"""ONNX Runtime wrapper for converted Luminar animal segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import single_channel_mask


class LsaAnimalsI8OnnxInference(OnnxInference):
    model_id = "lsa_animals_i8_onnx"
    task_type = "animal_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("size", (1024, 1024))
        kwargs.setdefault("channels", 4)
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        size = tuple(kwargs.get("size", (1024, 1024)))
        return {"mask": single_channel_mask(outputs, size)}
