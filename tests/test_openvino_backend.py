from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from ai.model.backend import OptionalBackendError
from ai.model.openvino_backend import OpenVinoRuntimeBackend
from ai.model.registry import ModelRecord
from ai.pipeline.factory import build_model_service
from configs import load_config
from configs.schemas import RuntimeConfig
from configs.store import _running_under_rosetta, resolve_openvino
from core.execution import ExecutionMode


class FakePort:
    def __init__(self, name: str, shape: tuple[int, ...], element_type: str = "f32") -> None:
        self.any_name = name
        self.shape = shape
        self.element_type = element_type


class FakeTensor:
    def __init__(self, value: np.ndarray) -> None:
        self.data = value


class FakeRequest:
    def __init__(self, compiled: FakeCompiled) -> None:
        self.compiled = compiled
        self.inputs = None

    def infer(self, inputs: dict[str, np.ndarray]) -> dict[FakePort, np.ndarray]:
        self.inputs = inputs
        value = next(iter(inputs.values()))
        return {self.compiled.outputs[0]: value + 1}

    def get_tensor(self, port: FakePort) -> FakeTensor:
        return FakeTensor(np.zeros(port.shape, dtype=np.float32))


class FakeCompiled:
    def __init__(self) -> None:
        self.inputs = [FakePort("input", (1, 3, 2, 2))]
        self.outputs = [FakePort("output", (1, 3, 2, 2))]

    def create_infer_request(self) -> FakeRequest:
        return FakeRequest(self)


class FakeCore:
    def read_model(self, *, model: str, weights: str) -> object:
        assert model.endswith(".xml")
        assert weights.endswith(".bin")
        return SimpleNamespace(model=model, weights=weights)

    def compile_model(
        self, model: object, device: str, config: dict[str, str] | None = None
    ) -> FakeCompiled:
        assert device == "CPU"
        return FakeCompiled()


class FakeOpenVino:
    Core = FakeCore


def test_native_ir_backend_loads_and_runs_with_fake_openvino(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    xml = tmp_path / "model.xml"
    weights = tmp_path / "model.bin"
    xml.write_text("<net/>", encoding="utf-8")
    weights.write_bytes(b"weights")
    monkeypatch.setitem(sys.modules, "openvino", FakeOpenVino())

    backend = OpenVinoRuntimeBackend()
    backend.load(xml, weights)
    assert backend.name == "openvino"
    assert backend.input_specs()[0].name == "input"
    output = backend.run({"input": np.zeros((1, 3, 2, 2), dtype=np.float32)})
    assert np.all(output["output"] == 1)
    backend.close()


def test_native_ir_backend_reports_optional_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    xml = tmp_path / "model.xml"
    weights = tmp_path / "model.bin"
    xml.write_text("<net/>", encoding="utf-8")
    weights.write_bytes(b"weights")
    monkeypatch.setitem(sys.modules, "openvino", None)

    with pytest.raises(OptionalBackendError, match="runtime-openvino"):
        OpenVinoRuntimeBackend().load(xml, weights)


def test_ir_registry_record_resolves_xml_and_bin(tmp_path: Path) -> None:
    xml = tmp_path / "model.xml"
    weights = tmp_path / "model.bin"
    record = ModelRecord(
        id="ir-model",
        task="segmentation",
        format="openvino_ir",
        path=xml,
        weights_path=weights,
        inference_class=(
            "ai.model.openvino.semantic_segmentation.segmentator_i8:SegmentatorI8Inference"
        ),
    )
    assert record.path == xml
    assert record.weights_path == weights
    assert record.inference_class.endswith("SegmentatorI8Inference")


def test_model_service_keeps_native_ir_opt_in_on_macos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ZPIXEL_ENABLE_OPENVINO", raising=False)
    monkeypatch.setattr("configs.store.sys.platform", "darwin")
    monkeypatch.setattr("configs.store._running_under_rosetta", lambda: False)
    service = build_model_service(load_config())
    assert service.openvino_enabled is False
    assert service.openvino_reason == "macos-requires-explicit-compatible-runtime"
    assert all(record.format != "openvino_ir" for record in service.registry.records.values())


def test_openvino_is_refused_under_rosetta_even_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("configs.store._running_under_rosetta", lambda: True)
    runtime = RuntimeConfig(
        execution_mode=ExecutionMode.EXACT,
        model_cache_mb=512,
        openvino="enabled",
        log_level="INFO",
    )

    enabled, reason = resolve_openvino(runtime)

    assert enabled is False
    assert reason == "rosetta-openvino-unsupported-use-native-arm64-python"


def test_rosetta_detection_falls_back_when_sysctl_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            SimpleNamespace(returncode=1, stdout=""),
            SimpleNamespace(returncode=0, stdout="arm64\n"),
        ]
    )
    monkeypatch.setattr("configs.store.sys.platform", "darwin")
    monkeypatch.setattr("configs.store.platform.machine", lambda: "x86_64")
    monkeypatch.setattr(
        "configs.store.subprocess.run", lambda *args, **kwargs: next(responses)
    )

    assert _running_under_rosetta() is True
