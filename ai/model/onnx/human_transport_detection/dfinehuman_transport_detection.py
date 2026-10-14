"""Inference wrapper for ``DFINEHumanTransportDetection``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference


class DFINEHumanTransportDetectionInference(OnnxInference):
    """Own the inference lifecycle boundary for ``DFINEHumanTransportDetection``."""

    model_id = "DFINEHumanTransportDetection"
    task_type = "human_transport_detection"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
