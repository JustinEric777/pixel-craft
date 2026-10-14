"""Inference wrapper for ``DepthAnythingV2SmallOpenVino``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference
from ai.model.shared import normalized_depth


class DepthAnythingV2SmallOpenVinoInference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``DepthAnythingV2SmallOpenVino``."""

    model_id = "DepthAnythingV2SmallOpenVino"
    task_type = "depth_estimation"

    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("size", (518, 518))
        kwargs.setdefault("mean", (0.485, 0.456, 0.406))
        kwargs.setdefault("std", (0.229, 0.224, 0.225))
        return super().preprocess(image, **kwargs)

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        if not outputs:
            raise ValueError("depth model returned no outputs")
        depth = np.asarray(next(iter(outputs.values())), dtype=np.float32)
        if depth.shape != (1, 1, 518, 518):
            raise ValueError(f"unexpected depth output shape: {depth.shape}")
        return {"depth": normalized_depth(outputs)}
