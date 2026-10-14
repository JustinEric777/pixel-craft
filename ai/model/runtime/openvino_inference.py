"""OpenVINO IR wrapper using the shared image inference adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..openvino_backend import OpenVinoRuntimeBackend
from .onnx_inference import OnnxInference


class OpenVinoInference(OnnxInference):
    """Reuse the explicit image pre/post adapter with native IR execution."""

    def __init__(
        self,
        model_name: str,
        model_path: Path,
        device: str = "CPU",
        weights_path: Path | None = None,
        cache_dir: Path | None = None,
        backend: OpenVinoRuntimeBackend | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name, model_path, device, backend=None, **kwargs)
        self._backend = backend
        self._weights_path = Path(weights_path) if weights_path else None
        self._cache_dir = Path(cache_dir) / self.model_name if cache_dir else None
        self._owns_backend = backend is None
        if backend is not None:
            self._loaded = True

    @property
    def backend(self) -> OpenVinoRuntimeBackend:
        if self._backend is None or not self.is_loaded:
            raise RuntimeError(f"model session is not loaded: {self.model_name}")
        return self._backend

    def load_model(self) -> None:
        backend = self._backend or OpenVinoRuntimeBackend(
            device=self.device, cache_dir=self._cache_dir
        )
        if self._backend is None:
            backend.load(self.model_path, self._weights_path)
        self._backend = backend
        self._model = backend
        self._loaded = True

    def unload_model(self) -> None:
        if self._backend is not None and self._owns_backend:
            self._backend.close()
        self._backend = None
        self._model = None
        self._loaded = False
