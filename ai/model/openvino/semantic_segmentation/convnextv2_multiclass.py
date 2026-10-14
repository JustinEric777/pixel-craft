"""Inference wrapper for Luminar Neo 1.25's ``convnextv2_multiclass`` IR."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import multiclass_segmentation


class ConvnextV2MulticlassInference(OpenVinoInference):
    """Expose the eight-class segmentation probabilities and label map."""

    model_id = "convnextv2_multiclass"
    task_type = "semantic_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("size", (512, 512))
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return multiclass_segmentation(outputs)
