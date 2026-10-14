"""Inference wrapper for ``horizon_align_i8``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class HorizonAlignI8Inference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``horizon_align_i8``."""

    model_id = "horizon_align_i8"
    task_type = "horizon_alignment"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        if not outputs:
            raise ValueError("horizon model returned no outputs")
        angle = float(np.asarray(next(iter(outputs.values())), dtype=np.float32).mean())
        return {"angle": angle}
