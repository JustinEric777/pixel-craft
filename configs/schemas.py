"""Validated configuration values shared by composition roots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.execution import CapabilityExecutionGraph, ExecutionMode, ExecutionPolicy


class PathConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_root: Path = Path("data")
    asset_root: Path = Path("assets")
    model_root: Path = Path("models")
    parameter_schema: Path = Path("configs/capabilities/parameter-schema.json")
    model_manifest: Path = Path("configs/model.yaml")
    capability_manifest: Path = Path("configs/capabilities/registry.json")


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_mode: ExecutionMode = ExecutionMode.DEVELOPMENT
    model_cache_mb: int = Field(default=2048, ge=256)
    openvino: Literal["auto", "enabled", "disabled"] = "auto"
    openvino_cache_dir: Path | None = None
    log_level: str = "INFO"


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    paths: PathConfig
    runtime: RuntimeConfig
    policy: ExecutionPolicy
    execution_graphs: dict[str, CapabilityExecutionGraph]
    presets: tuple[dict[str, Any], ...]
    preset_source: dict[str, str]
    ui: dict[str, Any]


class ModelSelectionConfig(BaseModel):
    """Backend order used when a logical model has multiple local artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary: Literal["onnxruntime"] = "onnxruntime"
    fallback: Literal["openvino"] = "openvino"


class ModelEntryConfig(BaseModel):
    """Strict serializable schema for one model artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    logical_id: str = Field(min_length=1)
    task: str = Field(min_length=1)
    format: Literal["onnx", "ort", "openvino_ir"]
    path: Path
    weights_path: Path | None = None
    license: str = "UNKNOWN"
    source: str = "UNKNOWN"
    sha256: str | None = None
    weights_sha256: str | None = None
    status: str = "unvalidated"
    input_specs: dict[str, Any] = Field(default_factory=dict)
    output_specs: dict[str, Any] = Field(default_factory=dict)
    preprocess_version: str = "unknown"
    postprocess_version: str = "unknown"
    notes: str = ""
    inference_class: str = Field(min_length=3)
    device: str = "cpu"
    max_memory_mb: int = Field(default=512, ge=1)
    model_name: str | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    backend: Literal["auto", "onnxruntime", "openvino"] = "auto"
    parameters: dict[str, Any] = Field(default_factory=dict)


class ModelCatalogConfig(BaseModel):
    """Single configuration source for every model artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1)
    model_root: Path = Path("../models")
    selection: ModelSelectionConfig = Field(default_factory=ModelSelectionConfig)
    models: tuple[ModelEntryConfig, ...]
