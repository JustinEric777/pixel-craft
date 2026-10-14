import json
from pathlib import Path

import yaml

from scripts.build_model_validation_matrix import build_matrix


def test_model_validation_matrix_combines_contract_runtime_and_role(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    (model_root / "model.onnx").write_bytes(b"model")
    registry = tmp_path / "model.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "model_root": str(model_root),
                "selection": {"primary": "onnxruntime", "fallback": "openvino"},
                "models": [
                        {
                            "id": "model",
                            "logical_id": "model",
                        "task": "segmentation",
                        "format": "onnx",
                        "path": "model.onnx",
                        "license": "test",
                        "source": "test",
                        "status": "inference-validated",
                        "input_specs": {},
                        "output_specs": {},
                        "preprocess_version": "pre-v1",
                        "postprocess_version": "post-v1",
                        "inference_class": "tests.fake:Inference",
                        "backend": "onnxruntime",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "model.json").write_text(
        json.dumps(
            {
                "model_id": "model",
                "format": "onnx",
                "normalization": {"status": "model-specific-validated"},
                "postprocess": {"status": "model-specific-validated"},
            }
        ),
        encoding="utf-8",
    )
    invocations = tmp_path / "invocations.json"
    invocations.write_text(
        json.dumps(
            {"model_roles": [{"model_id": "model", "role": "active-invoked"}]}
        ),
        encoding="utf-8",
    )

    report = build_matrix(registry, contracts, invocation_path=invocations)

    assert report["count"] == 1
    assert report["validated"] == 1
    assert report["presence_gate"] == "passed"
    assert report["exact_gate"] == "passed"
    assert report["models"][0]["role"] == "active-invoked"


def test_model_validation_matrix_blocks_missing_artifacts(tmp_path: Path) -> None:
    registry = tmp_path / "model.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "model_root": str(tmp_path / "models"),
                "selection": {"primary": "onnxruntime", "fallback": "openvino"},
                "models": [
                        {
                            "id": "missing",
                            "logical_id": "missing",
                        "task": "segmentation",
                        "format": "onnx",
                        "path": "missing.onnx",
                        "license": "test",
                        "source": "test",
                        "status": "unvalidated",
                        "input_specs": {},
                        "output_specs": {},
                        "preprocess_version": "pending-model-specific",
                        "postprocess_version": "pending-model-specific",
                        "inference_class": "tests.fake:Inference",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_matrix(registry, tmp_path / "contracts")

    assert report["presence_gate"] == "blocked"
    assert report["missing_artifacts"] == ["missing"]
    assert report["missing_contracts"] == ["missing"]
