"""Runtime values required by model orchestration, independent of app configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.execution import ExecutionMode


@dataclass(frozen=True)
class ModelRuntimeOptions:
    execution_mode: ExecutionMode
    model_cache_mb: int
    openvino_enabled: bool
    openvino_reason: str
    openvino_cache_dir: Path | None = None
