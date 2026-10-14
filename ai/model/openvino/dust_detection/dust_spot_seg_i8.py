"""Inference wrapper for ``dust_spot_seg_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class DustSpotSegI8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``dust_spot_seg_i8``."""

    model_id = "dust_spot_seg_i8"
    task_type = "dust_detection"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
