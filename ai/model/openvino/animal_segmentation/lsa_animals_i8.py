"""Inference wrapper for Luminar Neo's ``lsa_animals_i8`` model."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import single_channel_mask


class LsaAnimalsI8Inference(OpenVinoInference):
    """Return the model's animal foreground probability as a stable mask."""

    model_id = "lsa_animals_i8"
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
