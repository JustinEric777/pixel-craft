"""Runtime-neutral model backend interfaces."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class TensorSpec:
    name: str
    shape: tuple[int | str, ...]
    dtype: str


class ModelBackend(Protocol):
    """Minimal contract shared by ONNX Runtime and native OpenVINO adapters."""

    name: str

    def load(self, model_path: Path, weights_path: Path | None = None) -> None:
        """Load or compile a model."""

    def input_specs(self) -> Sequence[TensorSpec]:
        """Return model input signatures."""

    def output_specs(self) -> Sequence[TensorSpec]:
        """Return model output signatures."""

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run inference and return named outputs."""


class OptionalBackendError(RuntimeError):
    """Raised when an optional inference backend is not installed."""


class ModelFormatError(ValueError):
    """Raised when a production model does not match the selected backend."""
