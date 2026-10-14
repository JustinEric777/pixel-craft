"""Lazy multi-backend model service and model-specific analysis dispatch."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from ai.model.base_inference import BaseInference, InferenceResult
from ai.model.factory import create_inference
from ai.model.loader import ModelLoader
from ai.model.model_contract import ModelContractCatalog
from ai.model.registry import ModelRegistry
from ai.model.text_tokenizer import WordPieceTokenizer
from core.errors import ModelExecutionError
from core.execution import CapabilityExecutionGraph, ExecutionMode, ExecutionPolicy
from core.image_frame import ImageFrame

from .analysis_pipelines import AnalysisPipelinesMixin
from .image_effect_pipelines import ImageEffectPipelinesMixin
from .options import ModelRuntimeOptions
from .ports import SkyCompositor

logger = logging.getLogger(__name__)


class OnnxModelService(AnalysisPipelinesMixin, ImageEffectPipelinesMixin):
    def __init__(
        self,
        model_root: Path,
        *,
        runtime: ModelRuntimeOptions,
        policy: ExecutionPolicy,
        execution_graphs: dict[str, CapabilityExecutionGraph],
        sky_compositor: SkyCompositor,
        registry_path: Path | None = None,
        parity_status: dict[str, str] | None = None,
    ) -> None:
        """model_root is the project ``models/`` directory."""
        self.model_root = model_root
        model_config = registry_path or model_root.parent / "configs" / "model.yaml"
        catalog = ModelRegistry.from_yaml(model_config)
        self.openvino_enabled = runtime.openvino_enabled
        self.openvino_reason = runtime.openvino_reason
        self.ir_inventory = ModelRegistry(
            records={
                model_id: record
                for model_id, record in catalog.records.items()
                if record.format == "openvino_ir"
            },
            primary_backend=catalog.primary_backend,
            fallback_backend=catalog.fallback_backend,
            model_root=catalog.model_root,
        )
        self.registry = ModelRegistry(
            records={
                model_id: record
                for model_id, record in catalog.records.items()
                if record.format != "openvino_ir" or self.openvino_enabled
            },
            primary_backend=catalog.primary_backend,
            fallback_backend=catalog.fallback_backend,
            model_root=catalog.model_root,
        )
        self.sky_compositor = sky_compositor
        self.loader = ModelLoader(
            self.registry,
            max_memory_mb=runtime.model_cache_mb,
            factory=lambda record: create_inference(
                record, cache_dir=runtime.openvino_cache_dir
            ),
        )
        self.contracts = ModelContractCatalog(model_root / "contracts")
        self.execution_mode = runtime.execution_mode
        self.parity_mode = self.execution_mode.value
        self.policy = policy
        self.execution_graphs = execution_graphs
        self._active_trace: ContextVar[dict[str, Any] | None] = ContextVar(
            "zpixel_execution_trace", default=None
        )
        self._parity_by_capability = parity_status or {}
        tokenizer_path = self.model_root / "metadata/tokenizer.json"
        self._tokenizer = WordPieceTokenizer(tokenizer_path) if tokenizer_path.is_file() else None

    def session(self, model_id: str) -> Any:
        model_id = self._resolve_model_id(model_id)
        inference = self.loader.load_model(model_id)
        if not hasattr(inference, "backend"):
            raise TypeError(f"registered model has no runtime backend: {model_id}")
        return inference.backend

    @contextmanager
    def lease(self, model_id: str) -> Iterator[BaseInference]:
        resolved_id = self._resolve_model_id(model_id)
        with self.loader.lease_model(resolved_id) as inference:
            yield inference

    def _run(
        self,
        image: Image.Image,
        model_id: str,
        *,
        size: tuple[int, int] | None = None,
        mean: tuple[float, float, float] | None = None,
        std: tuple[float, float, float] | None = None,
        channels: int | None = None,
    ) -> InferenceResult:
        frame = ImageFrame(np.asarray(image.convert("RGB"), dtype=np.uint8))
        source = frame.rgb8()
        bgr = np.ascontiguousarray(source[..., ::-1])
        resolved_id = self._resolve_model_id(model_id)
        started = perf_counter()
        try:
            with self.lease(resolved_id) as inference:
                result = inference.run(bgr, size=size, mean=mean, std=std, channels=channels)
        except Exception as exc:
            self._record_model_event(
                resolved_id,
                "failed",
                (perf_counter() - started) * 1000.0,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        self._record_model_event(
            resolved_id,
            "ready",
            (perf_counter() - started) * 1000.0,
            outputs=result.data,
        )
        return result

    @contextmanager
    def execution(
        self, capability_ids: list[str], operation: str
    ) -> Iterator[dict[str, Any]]:
        trace: dict[str, Any] = {
            "execution_id": uuid.uuid4().hex,
            "operation": operation,
            "mode": self.execution_mode.value,
            "capabilities": list(dict.fromkeys(capability_ids)),
            "status": "running",
            "models": [],
        }
        token = self._active_trace.set(trace)
        started = perf_counter()
        try:
            yield trace
        except Exception as exc:
            trace["status"] = "failed"
            trace["error"] = f"{type(exc).__name__}: {exc}"
            raise
        else:
            trace["status"] = "ready"
        finally:
            trace["duration_ms"] = round((perf_counter() - started) * 1000.0, 3)
            self._active_trace.reset(token)

    def assert_effects_ready(self, capability_ids: list[str]) -> None:
        missing_graphs = [
            capability_id
            for capability_id in dict.fromkeys(capability_ids)
            if capability_id not in self.execution_graphs
        ]
        if missing_graphs:
            raise ModelExecutionError(
                "execution graph is not defined for "
                + ", ".join(missing_graphs)
            )
        incomplete = [
            capability_id
            for capability_id in dict.fromkeys(capability_ids)
            if (
                (graph := self.execution_graphs[capability_id]).implementation
                == "model-backed"
                and capability_id not in self.policy.image_effect_pipelines
            )
            or (
                graph.implementation == "deterministic"
                and capability_id not in self.policy.local_effect_pipelines
            )
        ]
        if incomplete:
            raise ModelExecutionError(
                "complete model post-processing pipeline is not implemented for "
                + ", ".join(incomplete)
            )
        unavailable: dict[str, list[str]] = {}
        for capability_id in dict.fromkeys(capability_ids):
            graph = self.execution_graphs.get(capability_id)
            if graph is None:
                continue
            missing = [
                model_id
                for model_id in graph.required_models
                if not (
                    self._model_is_runnable(model_id)
                    if self.execution_mode is ExecutionMode.EXACT
                    else self._model_backend_ready(model_id)
                )
            ]
            if missing:
                unavailable[capability_id] = missing
        if unavailable:
            detail = "; ".join(
                f"{capability_id} requires {', '.join(models)}"
                for capability_id, models in unavailable.items()
            )
            raise ModelExecutionError(
                f"model readiness blocked: {detail}"
            )
        if self.execution_mode is not ExecutionMode.EXACT:
            return
        blocked = [
            capability_id
            for capability_id in dict.fromkeys(capability_ids)
            if self._parity_by_capability.get(capability_id) != "passed"
        ]
        if blocked:
            raise ModelExecutionError(
                "exact mode blocked: Luminar parity has not passed for " + ", ".join(blocked)
            )

    def capability_readiness(self, capability: dict[str, Any]) -> dict[str, Any]:
        capability_id = str(capability.get("id", ""))
        graph = self.execution_graphs.get(capability_id)
        required = list(graph.required_models if graph else capability.get("model_ids", []))
        conditional = list(graph.conditional_models if graph else ())
        runnable = [model_id for model_id in required if self._model_backend_ready(model_id)]
        missing = [model_id for model_id in required if model_id not in runnable]
        parity = self._parity_by_capability.get(capability_id, "pending")
        if graph is None:
            status = "unavailable"
            reason = "完整执行图未定义"
        elif graph.implementation == "model-backed" and capability_id not in self.policy.image_effect_pipelines:
            status = "unavailable"
            reason = "模型已登记，但完整前后处理管线尚未实现"
        elif graph.implementation == "deterministic" and capability_id not in self.policy.local_effect_pipelines:
            status = "unavailable"
            reason = "该工具所需的交互或完整处理管线尚未实现"
        elif self.execution_mode is ExecutionMode.EXACT and parity != "passed":
            status = "unavailable"
            reason = "与活动 Luminar 参考版本的输出校验尚未通过"
        elif parity == "passed" and not missing and all(
            self._model_is_runnable(model_id) for model_id in required
        ):
            status = "parity-passed"
            reason = "运行时与活动 Luminar 参考版本的对照门禁均已通过"
        elif required and not missing:
            status = "runtime-ready"
            reason = "完整模型执行管线可运行"
        elif required:
            status = "unavailable"
            reason = "必需模型在当前运行环境不可用"
        else:
            status = "runtime-ready"
            reason = "本地完整处理管线可运行"
        return {
            "status": status,
            "reason": reason,
            "mode": self.execution_mode.value,
            "implementation": graph.implementation if graph else "undefined",
            "required_models": required,
            "conditional_models": conditional,
            "runnable_models": runnable,
            "missing_or_blocked_models": missing,
            "parity": parity,
        }

    def _model_is_runnable(self, model_id: str) -> bool:
        resolved_id = self._resolve_model_id(model_id)
        if not self._model_backend_ready(resolved_id):
            return False
        contract = self.contracts.get(resolved_id)
        return bool(
            contract
            and contract.normalization.get("status")
            in {"validated", "model-specific-validated", "parity-validated"}
            and contract.postprocess.get("status")
            in {"validated", "model-specific-validated", "parity-validated"}
        )

    def _model_backend_ready(self, model_id: str) -> bool:
        resolved_id = self._resolve_model_id(model_id)
        record = self.registry.records.get(resolved_id)
        if record is None or not record.path.exists():
            return False
        if record.weights_path is not None and not record.weights_path.is_file():
            return False
        if record.format == "openvino_ir":
            runtime_ready = self.openvino_enabled and record.status == "inference-validated"
        else:
            runtime_ready = record.status in {
                "ort-smoke-passed",
                "inference-validated",
            }
        return runtime_ready

    def _record_model_event(
        self,
        model_id: str,
        status: str,
        duration_ms: float,
        *,
        outputs: Any | None = None,
        error: str | None = None,
    ) -> None:
        trace = self._active_trace.get()
        if trace is None:
            return
        record = self.registry.require(model_id)
        contract = self.contracts.get(model_id)
        event: dict[str, Any] = {
            "id": model_id,
            "backend": self._runtime_for(record),
            "model_sha256": record.sha256,
            "preprocess_version": record.preprocess_version,
            "postprocess_version": record.postprocess_version,
            "contract_version": contract.version if contract else None,
            "contract_status": {
                "signature": contract.signature_status if contract else None,
                "runtime": contract.runtime_status if contract else None,
                "normalization": contract.normalization.get("status") if contract else None,
                "postprocess": contract.postprocess.get("status") if contract else None,
                "source_backend_parity": (
                    contract.source_backend_parity if contract else None
                ),
                "luminar_effect_parity": (
                    contract.luminar_effect_parity if contract else None
                ),
            },
            "status": status,
            "invoked": True,
            "duration_ms": round(duration_ms, 3),
        }
        if isinstance(outputs, dict):
            event["outputs"] = {
                name: {
                    "shape": list(np.asarray(value).shape),
                    "dtype": str(np.asarray(value).dtype),
                    "finite": bool(np.isfinite(value).all()),
                }
                for name, value in outputs.items()
            }
        if error:
            event["error"] = error
        trace["models"].append(event)

    def _resolve_model_id(self, model_id: str) -> str:
        """Resolve one canonical model id to ONNX first and OpenVINO IR second."""
        try:
            return self.registry.resolve(
                model_id,
                allow_openvino=self.openvino_enabled,
            ).id
        except KeyError:
            return model_id

    def health(self) -> dict[str, Any]:
        formats = {record.format for record in self.registry.records.values()}
        wrappers = {
            record.inference_class.rsplit(":", 1)[-1].rsplit(".", 1)[-1]
            for record in self.registry.records.values()
        }
        return {
            "model_root": str(self.model_root),
            "registered": len(self.registry.records),
            "missing": self.registry.validate_paths(),
            "loaded": self.loader.loaded_ids(),
            "cache": self.loader.health(),
            "runtime": "+".join(
                name
                for name, present in (
                    ("openvino", "openvino_ir" in formats),
                    ("onnxruntime", bool(formats & {"onnx", "ort"})),
                )
                if present
            ),
            "registered_formats": sorted(formats),
            "registered_wrappers": sorted(wrappers),
            "parity_mode": self.parity_mode,
            "execution_mode": self.execution_mode.value,
            "inventory": {
                "onnx": sum(
                    record.format in {"onnx", "ort"} for record in self.registry.records.values()
                ),
                "openvino_ir": len(self.ir_inventory.records),
            },
            "selection_policy": {
                "primary": "onnxruntime",
                "secondary": "openvino",
                "semantics": "same-logical-model-only",
            },
            "openvino": {
                "enabled": self.openvino_enabled,
                "reason": self.openvino_reason,
                "registry": "configs/model.yaml",
            },
        }
