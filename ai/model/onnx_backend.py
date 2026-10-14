"""ONNX Runtime production backend."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .backend import ModelFormatError, OptionalBackendError, TensorSpec


class OnnxRuntimeBackend:
    """Small, explicit wrapper around ``onnxruntime.InferenceSession``."""

    name = "onnxruntime"

    def __init__(
        self,
        providers: Sequence[str] | None = None,
        intra_op_num_threads: int = 0,
        inter_op_num_threads: int = 0,
        enable_profiling: bool = False,
    ) -> None:
        self.providers = tuple(providers or ("CPUExecutionProvider",))
        self.intra_op_num_threads = intra_op_num_threads
        self.inter_op_num_threads = inter_op_num_threads
        self.enable_profiling = enable_profiling
        self.session: Any = None
        self.model_path: Path | None = None

    def load(self, model_path: Path) -> None:
        if model_path.suffix.lower() not in {".onnx", ".ort"}:
            raise ModelFormatError(
                f"ONNX Runtime production backend accepts .onnx/.ort only: {model_path}"
            )
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise OptionalBackendError(
                "install the project's onnx dependency with uv sync"
            ) from exc

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if self.intra_op_num_threads > 0:
            options.intra_op_num_threads = self.intra_op_num_threads
        if self.inter_op_num_threads > 0:
            options.inter_op_num_threads = self.inter_op_num_threads
        options.enable_profiling = self.enable_profiling
        available = set(ort.get_available_providers())
        selected = tuple(provider for provider in self.providers if provider in available)
        if not selected:
            selected = ("CPUExecutionProvider",)
        self.session = ort.InferenceSession(str(model_path), options, providers=list(selected))
        self.providers = tuple(self.session.get_providers())
        self.model_path = model_path

    def _require_session(self) -> Any:
        if self.session is None:
            raise RuntimeError("model session is not loaded")
        return self.session

    @staticmethod
    def _spec(value: Any) -> TensorSpec:
        shape = tuple(
            dimension if isinstance(dimension, int) else (dimension or "dynamic")
            for dimension in value.shape
        )
        return TensorSpec(name=value.name, shape=shape, dtype=value.type)

    def input_specs(self) -> Sequence[TensorSpec]:
        return tuple(self._spec(value) for value in self._require_session().get_inputs())

    def output_specs(self) -> Sequence[TensorSpec]:
        return tuple(self._spec(value) for value in self._require_session().get_outputs())

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session()
        names = {item.name for item in session.get_inputs()}
        missing = names - inputs.keys()
        unknown = inputs.keys() - names
        if missing or unknown:
            raise ValueError(
                f"input contract mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        values = session.run(None, inputs)
        return {item.name: value for item, value in zip(session.get_outputs(), values)}

    def close(self) -> None:
        """Release the runtime session so the loader can reclaim its resources."""
        self.session = None
        self.model_path = None

    def health(self) -> dict[str, Any]:
        session = self._require_session()
        return {
            "model": str(self.model_path),
            "providers": list(session.get_providers()),
            "inputs": [self._spec(value).__dict__ for value in session.get_inputs()],
            "outputs": [self._spec(value).__dict__ for value in session.get_outputs()],
        }
