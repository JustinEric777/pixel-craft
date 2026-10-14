"""Generic ONNX Runtime wrapper for the shared inference lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..base_inference import BaseInference
from ..onnx_backend import OnnxRuntimeBackend


class OnnxInference(BaseInference):
    """Run a local ONNX/ORT artifact with a conservative BGR-to-NCHW adapter."""

    def __init__(
        self,
        model_name: str,
        model_path: Path,
        device: str = "cpu",
        backend: OnnxRuntimeBackend | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name, model_path, device, **kwargs)
        self._backend = backend
        self._owns_backend = backend is None
        if backend is not None:
            self._loaded = True

    @property
    def backend(self) -> OnnxRuntimeBackend:
        if self._backend is None or not self.is_loaded:
            raise RuntimeError(f"model session is not loaded: {self.model_name}")
        return self._backend

    def load_model(self) -> None:
        backend = self._backend or OnnxRuntimeBackend()
        if self._backend is None:
            backend.load(self.model_path)
        self._backend = backend
        self._model = backend
        self._loaded = True

    def unload_model(self) -> None:
        if self._backend is not None and self._owns_backend:
            self._backend.close()
        self._backend = None
        self._model = None
        self._loaded = False

    def preprocess(
        self,
        image: np.ndarray,
        *,
        size: tuple[int, int] | None = None,
        mean: tuple[float, float, float] | None = None,
        std: tuple[float, float, float] | None = None,
        channels: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        backend = self.backend
        input_spec = backend.input_specs()[0]
        shape = input_spec.shape
        layout = self._layout(shape)
        expected_channels = channels or self._channel_count(shape, layout)
        target_size = size or self._static_size(shape, layout)
        rgb = image[..., ::-1]
        source = Image.fromarray(rgb)
        if expected_channels == 1:
            source = source.convert("L")
        if target_size:
            source = source.resize(target_size, Image.Resampling.BILINEAR)
        input_dtype = self._dtype(input_spec.dtype)
        values = np.asarray(source, dtype=np.float32)
        if np.issubdtype(input_dtype, np.floating):
            values /= 255.0
        if expected_channels == 1:
            values = values[..., None]
        elif expected_channels == 4 and values.shape[-1] == 3:
            alpha = np.ones((*values.shape[:2], 1), dtype=values.dtype)
            values = np.concatenate((values, alpha), axis=-1)
        elif expected_channels not in {3, 4}:
            raise ValueError(
                f"generic image wrapper does not support {expected_channels} input channels"
            )
        if mean is not None:
            values = values - np.asarray(mean, dtype=np.float32)
        if std is not None:
            values = values / np.asarray(std, dtype=np.float32)
        tensor = values.transpose(2, 0, 1)[None] if layout == "NCHW" else values[None]
        tensor = tensor.astype(input_dtype, copy=False)
        return {input_spec.name: tensor}

    def predict(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return self.backend.run(inputs)

    def postprocess(self, outputs: dict[str, Any], **_: Any) -> dict[str, Any]:
        return outputs

    @staticmethod
    def _layout(shape: tuple[int | str, ...]) -> str:
        if len(shape) == 4 and shape[1] in {1, 3, 4}:
            return "NCHW"
        if len(shape) == 4 and shape[-1] in {1, 3, 4}:
            return "NHWC"
        return "NCHW"

    @staticmethod
    def _channel_count(shape: tuple[int | str, ...], layout: str) -> int:
        if len(shape) != 4:
            return 3
        value = shape[1] if layout == "NCHW" else shape[-1]
        return value if isinstance(value, int) and value > 0 else 3

    @staticmethod
    def _static_size(shape: tuple[int | str, ...], layout: str) -> tuple[int, int] | None:
        if len(shape) != 4:
            return None
        height_index, width_index = (2, 3) if layout == "NCHW" else (1, 2)
        height, width = shape[height_index], shape[width_index]
        if isinstance(height, int) and height > 0 and isinstance(width, int) and width > 0:
            return width, height
        return None

    @staticmethod
    def _dtype(type_name: str) -> np.dtype:
        return {
            "tensor(float16)": np.float16,
            "tensor(float)": np.float32,
            "tensor(double)": np.float64,
            "tensor(uint8)": np.uint8,
            "tensor(int32)": np.int32,
            "tensor(int64)": np.int64,
        }.get(type_name, np.float32)
