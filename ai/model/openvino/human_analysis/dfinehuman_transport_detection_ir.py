"""Inference wrapper for ``DFINEHumanTransportDetection_ir``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class DFINEHumanTransportDetectionIrInference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``DFINEHumanTransportDetection_ir``."""

    model_id = "DFINEHumanTransportDetection_ir"
    task_type = "human_analysis"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
