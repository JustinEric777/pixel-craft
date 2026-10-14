"""Inference wrapper for ``upscale_x2_hggt_exp19_posneg_like13_stronger_aug_continue_exp17_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class UpscaleX2HggtExp19PosnegLike13StrongerAugContinueExp17I8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``upscale_x2_hggt_exp19_posneg_like13_stronger_aug_continue_exp17_i8``."""

    model_id = "upscale_x2_hggt_exp19_posneg_like13_stronger_aug_continue_exp17_i8"
    task_type = "super_resolution"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return super().postprocess(outputs, **kwargs)
