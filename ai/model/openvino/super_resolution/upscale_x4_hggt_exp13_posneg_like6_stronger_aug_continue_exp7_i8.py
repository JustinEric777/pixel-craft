"""Inference wrapper for ``upscale_x4_hggt_exp13_posneg_like6_stronger_aug_continue_exp7_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class UpscaleX4HggtExp13PosnegLike6StrongerAugContinueExp7I8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``upscale_x4_hggt_exp13_posneg_like6_stronger_aug_continue_exp7_i8``."""

    model_id = "upscale_x4_hggt_exp13_posneg_like6_stronger_aug_continue_exp7_i8"
    task_type = "super_resolution"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
