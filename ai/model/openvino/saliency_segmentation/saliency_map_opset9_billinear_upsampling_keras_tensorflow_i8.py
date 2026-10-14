"""Inference wrapper for ``saliency_map_opset9_billinear_upsampling_keras_tensorflow_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import single_channel_mask


class SaliencyMapOpset9BillinearUpsamplingKerasTensorflowI8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``saliency_map_opset9_billinear_upsampling_keras_tensorflow_i8``."""

    model_id = "saliency_map_opset9_billinear_upsampling_keras_tensorflow_i8"
    task_type = "saliency_segmentation"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(256, 256))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        return {"mask": single_channel_mask(outputs, (256, 256))}
