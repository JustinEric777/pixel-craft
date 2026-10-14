"""Inference wrapper for ``mobilenet_exp78_portrait_BOKEH12_ir``."""

from __future__ import annotations

from typing import Any

import numpy as np

from ai.model.runtime.openvino_inference import OpenVinoInference


class MobilenetExp78PortraitBOKEH12IrInference(OpenVinoInference):
    """Own the inference lifecycle boundary for ``mobilenet_exp78_portrait_BOKEH12_ir``."""

    model_id = "mobilenet_exp78_portrait_BOKEH12_ir"
    task_type = "portrait_bokeh"

    def preprocess(self, image: np.ndarray, **_: Any) -> dict[str, Any]:
        return super().preprocess(image, size=(513, 513))

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return super().predict(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, np.ndarray]:
        probability = next(
            (np.asarray(value) for name, value in outputs.items() if "sigmoid" in name.lower()),
            None,
        )
        if probability is None or probability.shape != (1, 1, 513, 513):
            shapes = {name: list(np.asarray(value).shape) for name, value in outputs.items()}
            raise ValueError(f"portrait bokeh probability output is invalid: {shapes}")
        return {"mask": np.clip(probability[0, 0], 0.0, 1.0).astype(np.float32)}
