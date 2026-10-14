"""Composition helpers for configured model pipelines."""

from __future__ import annotations

from pathlib import Path

from configs.schemas import AppConfig
from configs.store import resolve_openvino
from image_ops.effects.sky_compositor import composite_sky

from .model_service import OnnxModelService
from .options import ModelRuntimeOptions


def build_model_service(
    config: AppConfig,
    *,
    model_root: Path | None = None,
    registry_path: Path | None = None,
) -> OnnxModelService:
    openvino_enabled, openvino_reason = resolve_openvino(config.runtime)
    return OnnxModelService(
        model_root or config.paths.model_root,
        runtime=ModelRuntimeOptions(
            execution_mode=config.runtime.execution_mode,
            model_cache_mb=config.runtime.model_cache_mb,
            openvino_enabled=openvino_enabled,
            openvino_reason=openvino_reason,
            openvino_cache_dir=config.runtime.openvino_cache_dir,
        ),
        policy=config.policy,
        execution_graphs=config.execution_graphs,
        registry_path=registry_path or config.paths.model_manifest,
        sky_compositor=composite_sky,
    )
