"""Inference wrapper for ``skin_seg_30class_exp71``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class SkinSeg30ClassExp71Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``skin_seg_30class_exp71``."""

    model_id = "skin_seg_30class_exp71"
    task_type = "skin_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
