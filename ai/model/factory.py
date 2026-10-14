"""Dynamic inference wrapper factory with strict type validation."""

from __future__ import annotations

import importlib
from typing import Any

from .base_inference import BaseInference
from .registry import ModelRecord


def create_inference(
    record: ModelRecord,
    *,
    device: str | None = None,
    **overrides: Any,
) -> BaseInference:
    module_name, class_name = _split_class_path(record.inference_class)
    module = importlib.import_module(module_name)
    inference_class = getattr(module, class_name)
    if not isinstance(inference_class, type) or not issubclass(inference_class, BaseInference):
        raise TypeError(f"inference class must extend BaseInference: {record.inference_class}")
    declared_model_id = getattr(inference_class, "model_id", record.id)
    if declared_model_id != record.id:
        raise ValueError(
            f"inference wrapper/model id mismatch: {record.inference_class} declares "
            f"{declared_model_id!r}, expected {record.id!r}"
        )
    kwargs: dict[str, Any] = dict(record.parameters)
    kwargs.update({
        "model_name": record.model_name or record.id,
        "model_path": record.path,
        "device": device or record.device,
    })
    if record.weights_path is not None:
        kwargs["weights_path"] = record.weights_path
    if record.confidence_threshold is not None:
        kwargs["confidence_threshold"] = record.confidence_threshold
    kwargs.update(overrides)
    return inference_class(**kwargs)


def _split_class_path(class_path: str) -> tuple[str, str]:
    if ":" in class_path:
        module_name, class_name = class_path.rsplit(":", 1)
    else:
        module_name, class_name = class_path.rsplit(".", 1)
    if not module_name or not class_name:
        raise ValueError(f"invalid inference class path: {class_path}")
    return module_name, class_name
