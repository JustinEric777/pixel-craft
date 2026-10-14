"""ONNX Runtime wrapper for three-class skin defect segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import multiclass_segmentation


class SkinDefSeg3ClassExp78OnnxInference(OnnxInference):
    model_id = "skin_def_seg_3class_exp78_onnx"
    task_type = "skin_defect_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return multiclass_segmentation(outputs)
