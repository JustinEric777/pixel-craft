import importlib
from pathlib import Path

import pytest
import yaml

from ai.model.registry import ModelRecord, ModelRegistry
from core.project.entities import (
    Artifact,
    ArtifactKind,
    EditNode,
    ImageRef,
    ProjectState,
)


def test_core_state_contract() -> None:
    state = ProjectState(
        source=ImageRef(Path("input.jpg")),
        artifacts={"sky": Artifact(ArtifactKind.MASK, "sky", value=None)},
        edits=[EditNode("e1", "sky_replace", {"amount": 0.5}, "sky")],
    )
    assert state.edits[0].mask_artifact == "sky"


def test_model_registry_requires_explicit_records(tmp_path: Path) -> None:
    registry = ModelRegistry()
    registry.add(ModelRecord("demo", "segmentation", "onnx", tmp_path / "demo.onnx"))
    assert registry.require("demo").task == "segmentation"
    assert registry.validate_paths() == ["demo"]


def test_production_model_records_use_explicit_importable_wrappers() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = ModelRegistry.from_yaml(root / "configs/model.yaml")
    classes: set[type] = set()
    for record in registry.records.values():
        class_path = record.inference_class
        assert class_path
        assert ".runtime." not in class_path
        module_name, class_name = class_path.split(":", 1)
        inference_class = getattr(importlib.import_module(module_name), class_name)
        assert inference_class not in classes
        assert inference_class.model_id == record.id
        assert {"preprocess", "predict", "postprocess"} <= inference_class.__dict__.keys()
        classes.add(inference_class)
    assert len(classes) == len(registry.records)


def test_model_yaml_rejects_reused_wrapper_class(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    payload = yaml.safe_load((root / "configs/model.yaml").read_text(encoding="utf-8"))
    payload["model_root"] = str(root / "models")
    payload["models"][1]["inference_class"] = payload["models"][0]["inference_class"]
    path = tmp_path / "model.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="one wrapper class per artifact"):
        ModelRegistry.from_yaml(path)
