"""Inference wrapper for ``defocus_exp35_SBDD_tile256_CBAN_UNet_7``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.onnx_inference import OnnxInference


class DefocusExp35SBDDTile256CBANUNet7Inference(OnnxInference):
    """Own the inference lifecycle boundary for ``defocus_exp35_SBDD_tile256_CBAN_UNet_7``."""

    model_id = "defocus_exp35_SBDD_tile256_CBAN_UNet_7"
    task_type = "defocus_restore"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
