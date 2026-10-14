"""Strict YAML-backed model registry used by the inference factory and loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from configs.schemas import ModelCatalogConfig, ModelEntryConfig


@dataclass(frozen=True)
class ModelRecord:
    id: str
    task: str
    format: str
    path: Path
    logical_id: str | None = None
    weights_path: Path | None = None
    license: str = "UNKNOWN"
    source: str = "UNKNOWN"
    sha256: str | None = None
    weights_sha256: str | None = None
    status: str = "unvalidated"
    input_specs: dict[str, Any] = field(default_factory=dict)
    output_specs: dict[str, Any] = field(default_factory=dict)
    preprocess_version: str = "unknown"
    postprocess_version: str = "unknown"
    notes: str = ""
    inference_class: str = ""
    device: str = "cpu"
    max_memory_mb: int = 512
    model_name: str | None = None
    confidence_threshold: float | None = None
    backend: str = "auto"
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: ModelEntryConfig, model_root: Path) -> ModelRecord:
        path = config.path if config.path.is_absolute() else model_root / config.path
        weights_path = config.weights_path
        if weights_path is not None and not weights_path.is_absolute():
            weights_path = model_root / weights_path
        return cls(
            id=config.id,
            logical_id=config.logical_id,
            task=config.task,
            format=config.format,
            path=path,
            weights_path=weights_path,
            license=config.license,
            source=config.source,
            sha256=config.sha256,
            weights_sha256=config.weights_sha256,
            status=config.status,
            input_specs=dict(config.input_specs),
            output_specs=dict(config.output_specs),
            preprocess_version=config.preprocess_version,
            postprocess_version=config.postprocess_version,
            notes=config.notes,
            inference_class=config.inference_class,
            device=config.device,
            max_memory_mb=config.max_memory_mb,
            model_name=config.model_name,
            confidence_threshold=config.confidence_threshold,
            backend=config.backend,
            parameters=dict(config.parameters),
        )


@dataclass
class ModelRegistry:
    records: dict[str, ModelRecord] = field(default_factory=dict)
    primary_backend: str = "onnxruntime"
    fallback_backend: str = "openvino"
    model_root: Path | None = None

    def add(self, record: ModelRecord) -> None:
        if record.id in self.records:
            raise ValueError(f"duplicate model id: {record.id}")
        self.records[record.id] = record

    def require(self, model_id: str) -> ModelRecord:
        try:
            return self.records[model_id]
        except KeyError as exc:
            raise KeyError(f"model is not registered: {model_id}") from exc

    def variants(self, logical_id: str) -> list[ModelRecord]:
        return [
            record
            for record in self.records.values()
            if (record.logical_id or record.id) == logical_id
        ]

    def resolve(self, logical_id: str, *, allow_openvino: bool) -> ModelRecord:
        candidates = self.variants(logical_id)
        direct = self.records.get(logical_id)
        if direct is not None and direct not in candidates:
            candidates.append(direct)
        priority = {"onnx": 0, "ort": 0, "openvino_ir": 1}
        candidates.sort(key=lambda item: (priority.get(item.format, 99), item.id))
        for record in candidates:
            if record.format == "openvino_ir" and not allow_openvino:
                continue
            if record.format not in priority:
                continue
            if record.path.is_file() and (
                record.weights_path is None or record.weights_path.is_file()
            ):
                return record
        raise KeyError(f"no runnable model variant is registered: {logical_id}")

    def validate_paths(self) -> list[str]:
        return [
            model_id
            for model_id, record in self.records.items()
            if not record.path.is_file()
            or (record.weights_path is not None and not record.weights_path.is_file())
        ]

    @classmethod
    def from_yaml(cls, path: Path) -> ModelRegistry:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"model configuration is missing: {path}") from exc
        except yaml.YAMLError as exc:
            raise RuntimeError(f"invalid YAML model configuration: {path}: {exc}") from exc
        try:
            catalog = ModelCatalogConfig.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"invalid model configuration: {path}: {exc}") from exc
        model_root = catalog.model_root
        if not model_root.is_absolute():
            model_root = (path.parent / model_root).resolve()
        registry = cls(
            primary_backend=catalog.selection.primary,
            fallback_backend=catalog.selection.fallback,
            model_root=model_root,
        )
        class_paths: set[str] = set()
        for item in catalog.models:
            if ".runtime." in item.inference_class:
                raise RuntimeError(
                    f"model configuration cannot register a generic runtime wrapper: {item.id}"
                )
            if item.inference_class in class_paths:
                raise RuntimeError(
                    f"model configuration requires one wrapper class per artifact: "
                    f"{item.inference_class}"
                )
            class_paths.add(item.inference_class)
            registry.add(ModelRecord.from_config(item, model_root))
        return registry
