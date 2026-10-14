"""ONNX Runtime wrapper for two-class skin defect segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference
from ai.model.shared import single_channel_mask


class SkinDefSeg2ClassExp62OnnxInference(OnnxInference):
    model_id = "skin_def_seg_2class_exp62_no_amp_onnx"
    task_type = "skin_defect_segmentation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return {"mask": single_channel_mask(outputs, (1024, 1024))}
