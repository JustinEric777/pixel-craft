"""Inference wrapper for ``wires_exp14_nestnet_pipline``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class WiresExp14NestnetPiplineInference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``wires_exp14_nestnet_pipline``."""

    model_id = "wires_exp14_nestnet_pipline"
    task_type = "wire_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
