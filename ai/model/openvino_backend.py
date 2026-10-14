"""Optional native OpenVINO IR backend.

This adapter is intentionally separate from the ONNX Runtime adapter.  An
OpenVINO IR is a pair of XML graph and BIN weights, and loading it natively is
the secondary backend for models whose conversion to ONNX is invalid or
loses the original graph contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .backend import ModelFormatError, OptionalBackendError, TensorSpec


class OpenVinoRuntimeBackend:
    """Small, lazy wrapper around ``openvino.Core`` and an infer request."""

    name = "openvino"

    def __init__(self, device: str = "CPU", cache_dir: Path | None = None) -> None:
        self.device = device.upper() or "CPU"
        self.cache_dir = cache_dir
        self.core: Any = None
        self.model: Any = None
        self.compiled_model: Any = None
        self.infer_request: Any = None
        self.model_path: Path | None = None
        self.weights_path: Path | None = None

    def load(self, model_path: Path, weights_path: Path | None = None) -> None:
        xml_path = Path(model_path)
        if xml_path.suffix.lower() != ".xml":
            raise ModelFormatError(f"OpenVINO backend accepts .xml IR graphs only: {xml_path}")
        if not xml_path.is_file():
            raise FileNotFoundError(xml_path)
        bin_path = Path(weights_path) if weights_path else xml_path.with_suffix(".bin")
        if not bin_path.is_file():
            raise FileNotFoundError(bin_path)
        try:
            import openvino as ov
        except ImportError as exc:  # pragma: no cover - depends on optional environment
            raise OptionalBackendError(
                "install the optional OpenVINO runtime with: uv sync --extra runtime-openvino"
            ) from exc

        core = ov.Core()
        model = core.read_model(model=str(xml_path), weights=str(bin_path))
        compile_kwargs: dict[str, Any] = {}
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            compile_kwargs["CACHE_DIR"] = str(self.cache_dir)
        compiled = (
            core.compile_model(model, self.device, compile_kwargs)
            if compile_kwargs
            else core.compile_model(model, self.device)
        )
        self.core = core
        self.model = model
        self.compiled_model = compiled
        self.infer_request = compiled.create_infer_request()
        self.model_path = xml_path
        self.weights_path = bin_path

    def _require_request(self) -> Any:
        if self.infer_request is None or self.compiled_model is None:
            raise RuntimeError("OpenVINO model is not loaded")
        return self.infer_request

    @staticmethod
    def _port_name(port: Any) -> str:
        any_name = getattr(port, "any_name", None)
        if callable(any_name):
            any_name = any_name()
        if any_name:
            return str(any_name)
        get_names = getattr(port, "get_names", None)
        if callable(get_names):
            names = list(get_names())
            if names:
                return str(min(names))
        return str(getattr(port, "name", "output"))

    @staticmethod
    def _shape(port: Any) -> tuple[int | str, ...]:
        shape = getattr(port, "shape", None)
        if shape is None and hasattr(port, "get_partial_shape"):
            shape = port.get_partial_shape()
        values: list[int | str] = []
        for dimension in shape or ():
            if isinstance(dimension, int):
                values.append(dimension if dimension > 0 else "dynamic")
                continue
            is_dynamic = getattr(dimension, "is_dynamic", None)
            if callable(is_dynamic) and is_dynamic():
                values.append("dynamic")
                continue
            get_length = getattr(dimension, "get_length", None)
            if callable(get_length):
                values.append(int(get_length()))
                continue
            try:
                values.append(int(dimension))
            except (TypeError, ValueError):
                values.append(str(dimension) or "dynamic")
        return tuple(values)

    @staticmethod
    def _dtype(port: Any) -> str:
        element_type = getattr(port, "element_type", None)
        if element_type is None and hasattr(port, "get_element_type"):
            element_type = port.get_element_type()
        text = str(element_type or "float32").lower()
        return {
            "f16": "tensor(float16)",
            "f32": "tensor(float)",
            "f64": "tensor(double)",
            "u8": "tensor(uint8)",
            "i32": "tensor(int32)",
            "i64": "tensor(int64)",
            "boolean": "tensor(bool)",
        }.get(text, text)

    def _spec(self, port: Any) -> TensorSpec:
        return TensorSpec(self._port_name(port), self._shape(port), self._dtype(port))

    def input_specs(self) -> Sequence[TensorSpec]:
        self._require_request()
        return tuple(self._spec(port) for port in self.compiled_model.inputs)

    def output_specs(self) -> Sequence[TensorSpec]:
        self._require_request()
        return tuple(self._spec(port) for port in self.compiled_model.outputs)

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        request = self._require_request()
        expected = {spec.name for spec in self.input_specs()}
        missing = expected - inputs.keys()
        unknown = inputs.keys() - expected
        if missing or unknown:
            raise ValueError(
                f"input contract mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        result = request.infer({name: np.asarray(value) for name, value in inputs.items()})
        outputs: dict[str, Any] = {}
        for port in self.compiled_model.outputs:
            name = self._port_name(port)
            value: Any = None
            if isinstance(result, dict):
                if port in result:
                    value = result[port]
                elif name in result:
                    value = result[name]
                else:
                    for key, candidate in result.items():
                        if self._port_name(key) == name:
                            value = candidate
                            break
            if value is None and hasattr(request, "get_tensor"):
                value = request.get_tensor(port).data
            if value is None:
                raise RuntimeError(f"OpenVINO did not return output tensor: {name}")
            outputs[name] = np.asarray(value)
        return outputs

    def close(self) -> None:
        self.infer_request = None
        self.compiled_model = None
        self.model = None
        self.core = None
        self.model_path = None
        self.weights_path = None

    def health(self) -> dict[str, Any]:
        self._require_request()
        return {
            "model": str(self.model_path),
            "weights": str(self.weights_path),
            "device": self.device,
            "inputs": [spec.__dict__ for spec in self.input_specs()],
            "outputs": [spec.__dict__ for spec in self.output_specs()],
        }
