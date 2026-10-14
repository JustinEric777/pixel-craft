from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
from PIL import Image

from ai.model.base_inference import BaseInference
from ai.model.factory import create_inference
from ai.model.loader import ModelLoader
from ai.model.registry import ModelRecord, ModelRegistry
from ai.pipeline import InferenceExecutor


class FakeInference(BaseInference):
    instances: ClassVar[list["FakeInference"]] = []

    def __init__(
        self, model_name: str, model_path: Path, device: str = "cpu", **kwargs: object
    ) -> None:
        super().__init__(model_name, model_path, device, **kwargs)
        self.unload_count = 0
        self.load_count = 0
        self.__class__.instances.append(self)

    def load_model(self) -> None:
        self.load_count += 1
        self._model = object()
        self._loaded = True

    def unload_model(self) -> None:
        self.unload_count += 1
        self._model = None
        self._loaded = False

    def preprocess(self, image: np.ndarray, **kwargs: object) -> dict[str, np.ndarray]:
        return {"image": image}

    def predict(self, inputs: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        return inputs

    def postprocess(
        self, outputs: dict[str, np.ndarray], **kwargs: object
    ) -> dict[str, np.ndarray]:
        return outputs


def _registry(tmp_path: Path, *, memory: int = 1) -> ModelRegistry:
    registry = ModelRegistry()
    for model_id in ("first", "second"):
        registry.add(
            ModelRecord(
                model_id, "test", "onnx", tmp_path / f"{model_id}.onnx", max_memory_mb=memory
            )
        )
    return registry


def _fake_factory(record: ModelRecord) -> FakeInference:
    return FakeInference(record.id, record.path)


def test_loader_reuses_loaded_model_and_unloads_lru(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    loader = ModelLoader(registry, max_memory_mb=1, factory=_fake_factory)

    first = loader.load_model("first")
    assert loader.load_model("first") is first
    second = loader.load_model("second")

    assert second is not first
    assert first.unload_count == 1
    assert loader.loaded_ids() == ["second"]


def test_loader_lease_protects_active_model(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    loader = ModelLoader(registry, max_memory_mb=1, factory=_fake_factory)

    with loader.lease_model("first") as first:
        with pytest.raises(MemoryError, match="no inactive models"):
            loader.load_model("second")
        assert first.is_loaded
        assert loader.loaded_ids() == ["first"]

    assert loader.unload_model("first")
    assert not first.is_loaded


def test_loader_does_not_cache_failed_load(tmp_path: Path) -> None:
    class FailingInference(FakeInference):
        def load_model(self) -> None:
            raise RuntimeError("synthetic load failure")

    registry = _registry(tmp_path)
    loader = ModelLoader(registry, factory=lambda record: FailingInference(record.id, record.path))
    with pytest.raises(RuntimeError, match="synthetic load failure"):
        loader.load_model("first")
    assert loader.loaded_ids() == []


def test_factory_accepts_colon_and_dotted_class_paths(tmp_path: Path) -> None:
    for class_path in (
        "ai.model.runtime.onnx_inference:OnnxInference",
        "ai.model.runtime.onnx_inference.OnnxInference",
    ):
        record = ModelRecord(
            "fake", "test", "onnx", tmp_path / "fake.onnx", inference_class=class_path
        )
        model = create_inference(record)
        assert model.model_name == "fake"


def test_base_run_exposes_source_image_contract(tmp_path: Path) -> None:
    model = FakeInference("fake", tmp_path / "fake.onnx")
    result = model.run(np.zeros((8, 6, 3), dtype=np.uint8))
    assert result.metadata["input"] == {
        "color_space": "bgr",
        "dtype": "uint8",
        "source_shape": [8, 6],
    }
    with pytest.raises(TypeError, match="uint8"):
        model.run(np.zeros((8, 6, 3), dtype=np.float32))


def test_pipeline_runner_leases_the_full_wrapper_call(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    loader = ModelLoader(registry, factory=_fake_factory)
    result = InferenceExecutor(loader).run("first", Image.new("RGB", (6, 8)))
    assert result.metadata["input"]["color_space"] == "bgr"
    assert loader.health()["active_leases"] == 0


def test_registry_prefers_onnx_and_uses_openvino_as_same_model_secondary(
    tmp_path: Path,
) -> None:
    onnx = tmp_path / "sky.onnx"
    xml = tmp_path / "sky.xml"
    weights = tmp_path / "sky.bin"
    onnx.write_bytes(b"onnx")
    xml.write_text("<net/>", encoding="utf-8")
    weights.write_bytes(b"weights")
    registry = ModelRegistry()
    registry.add(ModelRecord("sky-onnx", "sky", "onnx", onnx, logical_id="sky"))
    registry.add(
        ModelRecord(
            "sky-ir",
            "sky",
            "openvino_ir",
            xml,
            logical_id="sky",
            weights_path=weights,
        )
    )

    assert registry.resolve("sky", allow_openvino=True).id == "sky-onnx"
    onnx.unlink()
    assert registry.resolve("sky", allow_openvino=True).id == "sky-ir"
    with pytest.raises(KeyError, match="no runnable model variant"):
        registry.resolve("sky", allow_openvino=False)
