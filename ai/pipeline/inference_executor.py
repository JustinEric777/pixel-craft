"""Lease model wrappers for the complete inference call."""

from __future__ import annotations

import numpy as np
from PIL import Image

from ai.model.base_inference import InferenceResult
from ai.model.loader import ModelLoader


class InferenceExecutor:
    def __init__(self, loader: ModelLoader) -> None:
        self.loader = loader

    def run(self, model_id: str, image: Image.Image, **kwargs: object) -> InferenceResult:
        source = np.asarray(image.convert("RGB"), dtype=np.uint8)
        bgr = np.ascontiguousarray(source[..., ::-1])
        with self.loader.lease_model(model_id) as model:
            return model.run(bgr, **kwargs)
