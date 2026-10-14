"""Inference wrapper for Luminar Neo's ``Segmentation2`` model."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class Segmentation2Inference(OpenVinoInference):
    """Expose the 151-class map and probabilities used by Mask AI."""

    model_id = "Segmentation2"
    task_type = "semantic_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("size", (513, 513))
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, Any]:
        values = list(outputs.values())
        if len(values) != 2:
            raise ValueError(f"Segmentation2 expected 2 outputs, received {len(values)}")
        class_map = next((value for value in values if np.asarray(value).ndim == 3), None)
        probabilities = next((value for value in values if np.asarray(value).ndim == 4), None)
        if class_map is None or probabilities is None:
            shapes = [list(np.asarray(value).shape) for value in values]
            raise ValueError(f"Segmentation2 output contract mismatch: {shapes}")
        return {
            "class_map": np.asarray(class_map, dtype=np.int32),
            "probabilities": np.asarray(probabilities, dtype=np.float32),
        }
