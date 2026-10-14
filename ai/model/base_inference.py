"""Framework-neutral inference lifecycle contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any

import numpy as np


@dataclass(frozen=True)
class InferenceResult:
    """Stable result envelope shared by model wrappers."""

    data: Any
    model_name: str
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseInference(ABC):
    """Own one local model instance and expose one guarded inference pipeline."""

    def __init__(self, model_name: str, model_path: Path, device: str = "cpu", **_: Any) -> None:
        self.model_name = model_name
        self.model_path = Path(model_path)
        self.device = device
        self._model: Any = None
        self._loaded = False
        self._run_lock = RLock()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @abstractmethod
    def load_model(self) -> None:
        """Load local weights and set ``_loaded`` only after success."""

    @abstractmethod
    def unload_model(self) -> None:
        """Release model resources and reset ``_loaded``."""

    @abstractmethod
    def preprocess(self, image: np.ndarray, **kwargs: Any) -> dict[str, Any]:
        """Convert a validated source image into model inputs."""

    @abstractmethod
    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run the model forward pass only."""

    @abstractmethod
    def postprocess(self, outputs: dict[str, Any], **kwargs: Any) -> Any:
        """Convert raw outputs into the wrapper's stable result data."""

    def run(self, image: np.ndarray, **kwargs: Any) -> InferenceResult:
        """Validate BGR input, execute all stages under one instance lock."""
        self._validate_image(image)
        with self._run_lock:
            if not self._loaded:
                self.load_model()
            started = perf_counter()
            inputs = self.preprocess(image, **kwargs)
            outputs = self.predict(inputs)
            data = self.postprocess(outputs, **kwargs)
            duration_ms = (perf_counter() - started) * 1000.0
        return InferenceResult(
            data=data,
            model_name=self.model_name,
            duration_ms=duration_ms,
            metadata={
                "input": {
                    "color_space": "bgr",
                    "dtype": "uint8",
                    "source_shape": [image.shape[0], image.shape[1]],
                },
                "device": self.device,
            },
        )

    @staticmethod
    def _validate_image(image: np.ndarray) -> None:
        if not isinstance(image, np.ndarray):
            raise TypeError("inference input must be a numpy.ndarray")
        if image.dtype != np.uint8:
            raise TypeError("inference input must use uint8 dtype")
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("inference input must have shape HxWx3")
