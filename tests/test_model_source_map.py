import hashlib
import json
from pathlib import Path

from scripts.build_model_source_map import build_model_source_map


def test_model_source_map_separates_file_presence_from_behavior_parity(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "models"
    artifact = model_root / "onnx/example.onnx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"model")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    wrapper = tmp_path / "ai/model/onnx/example.py"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("class Example: pass\n", encoding="utf-8")
    registry = tmp_path / "model.yaml"
    registry.write_text(
        f"""version: '1.0'
model_root: models
selection: {{primary: onnxruntime, fallback: openvino}}
models:
  - id: Example
    logical_id: Example
    task: test
    format: onnx
    path: onnx/example.onnx
    sha256: {digest}
    inference_class: ai.model.onnx.example:Example
    backend: onnxruntime
    preprocess_version: pending-model-specific
    postprocess_version: pending-model-specific
""",
        encoding="utf-8",
    )
    portable = tmp_path / "portable.json"
    project = tmp_path / "project.json"
    inventory = {
        "records": [
            {
                "name": "example.onnx",
                "format": "onnx",
                "sha256": digest,
                "path": str(artifact),
            }
        ]
    }
    portable.write_text(json.dumps(inventory), encoding="utf-8")
    project.write_text(json.dumps(inventory), encoding="utf-8")
    execution_graphs = tmp_path / "execution-graphs.json"
    execution_graphs.write_text(
        json.dumps(
            {
                "graphs": [
                    {
                        "capability_id": "example-effect",
                        "implementation": "model-backed",
                        "required_models": ["Example"],
                        "conditional_models": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ui_config = tmp_path / "editor.json"
    ui_config.write_text(
        json.dumps(
            {"tool_groups": [{"capabilities": ["example-effect"]}]}
        ),
        encoding="utf-8",
    )

    report = build_model_source_map(
        registry_path=registry,
        portable_inventory_path=portable,
        project_inventory_paths=(project,),
        project_root=tmp_path,
        execution_graph_path=execution_graphs,
        ui_config_path=ui_config,
    )

    assert report["source_gate"] == "passed"
    assert report["registry_gate"] == "passed"
    assert report["exact_behavior_gate"] == "blocked"
    assert report["consumer_counts"] == {"unmapped": 1}
    assert report["product_scope_counts"] == {"required-direct": 1}
    assert report["pending_required_models"] == ["Example"]


def test_model_source_map_excludes_unreachable_inventory_from_exact_gate(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "models"
    required_artifact = model_root / "onnx/required.onnx"
    inventory_artifact = model_root / "onnx/inventory.onnx"
    required_artifact.parent.mkdir(parents=True)
    required_artifact.write_bytes(b"required")
    inventory_artifact.write_bytes(b"inventory")
    wrapper_root = tmp_path / "ai/model/onnx"
    wrapper_root.mkdir(parents=True)
    (wrapper_root / "required.py").write_text("class Required: pass\n", encoding="utf-8")
    (wrapper_root / "inventory.py").write_text("class Inventory: pass\n", encoding="utf-8")
    required_digest = hashlib.sha256(required_artifact.read_bytes()).hexdigest()
    inventory_digest = hashlib.sha256(inventory_artifact.read_bytes()).hexdigest()
    registry = tmp_path / "model.yaml"
    registry.write_text(
        f"""version: '1.0'
model_root: models
selection: {{primary: onnxruntime, fallback: openvino}}
models:
  - id: Required
    logical_id: Required
    task: test
    format: onnx
    path: onnx/required.onnx
    sha256: {required_digest}
    inference_class: ai.model.onnx.required:Required
    backend: onnxruntime
    preprocess_version: validated
    postprocess_version: validated
  - id: Inventory
    logical_id: Inventory
    task: test
    format: onnx
    path: onnx/inventory.onnx
    sha256: {inventory_digest}
    inference_class: ai.model.onnx.inventory:Inventory
    backend: onnxruntime
    preprocess_version: pending
    postprocess_version: pending
""",
        encoding="utf-8",
    )
    portable = tmp_path / "portable.json"
    project = tmp_path / "project.json"
    inventory = {
        "records": [
            {"name": "required.onnx", "format": "onnx", "sha256": required_digest},
            {"name": "inventory.onnx", "format": "onnx", "sha256": inventory_digest},
        ]
    }
    portable.write_text(json.dumps(inventory), encoding="utf-8")
    project.write_text(json.dumps(inventory), encoding="utf-8")
    execution_graphs = tmp_path / "execution-graphs.json"
    execution_graphs.write_text(
        json.dumps(
            {
                "graphs": [
                    {
                        "capability_id": "required-effect",
                        "implementation": "model-backed",
                        "required_models": ["Required"],
                        "conditional_models": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ui_config = tmp_path / "editor.json"
    ui_config.write_text(
        json.dumps({"tool_groups": [{"capabilities": ["required-effect"]}]}),
        encoding="utf-8",
    )
    contract_root = model_root / "contracts"
    contract_root.mkdir()
    (contract_root / "Required.json").write_text(
        json.dumps(
            {
                "model_id": "Required",
                "format": "onnx",
                "normalization": {"status": "model-specific-validated"},
                "postprocess": {"status": "model-specific-validated"},
            }
        ),
        encoding="utf-8",
    )

    report = build_model_source_map(
        registry_path=registry,
        portable_inventory_path=portable,
        project_inventory_paths=(project,),
        project_root=tmp_path,
        execution_graph_path=execution_graphs,
        ui_config_path=ui_config,
        contract_root=contract_root,
    )

    assert report["exact_behavior_gate"] == "passed"
    assert report["product_scope_counts"] == {
        "inventory-unreachable": 1,
        "required-direct": 1,
    }
    assert report["pending_required_models"] == []
