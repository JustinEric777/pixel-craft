"""Inference wrapper for ``skin_def_seg_2class_exp62_no_amp``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class SkinDefSeg2ClassExp62NoAmpInference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``skin_def_seg_2class_exp62_no_amp``."""

    model_id = "skin_def_seg_2class_exp62_no_amp"
    task_type = "skin_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
