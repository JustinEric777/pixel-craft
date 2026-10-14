import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.audit_candidate_model_invocations import audit_candidate_invocations


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _image_hash(path: Path) -> str:
    with Image.open(path) as image:
        return hashlib.sha256(
            image.mode.encode("ascii")
            + str(image.size).encode("ascii")
            + image.tobytes()
        ).hexdigest()


def test_audit_requires_real_model_invocation_and_matching_export(tmp_path: Path) -> None:
    model = tmp_path / "models/example.onnx"
    model.parent.mkdir()
    model.write_bytes(b"model")
    registry = tmp_path / "model.yaml"
    registry.write_text(
        f"""version: '1.0'
model_root: models
selection: {{primary: onnxruntime, fallback: openvino}}
models:
  - id: ExampleOnnx
    logical_id: Example
    task: segmentation
    format: onnx
    path: example.onnx
    sha256: {_sha256(model)}
    inference_class: ai.model.onnx.example:ExampleInference
    backend: onnxruntime
""",
        encoding="utf-8",
    )
    graphs = tmp_path / "graphs.json"
    graphs.write_text(
        json.dumps(
            {
                "graphs": [
                    {
                        "capability_id": "effect",
                        "implementation": "model-backed",
                        "required_models": ["Example"],
                        "conditional_models": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    export = tmp_path / "export.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(export)
    trace = tmp_path / "execution.json"
    trace.write_text(
        json.dumps(
            {
                "status": "ready",
                "capabilities": ["effect"],
                    "models": [
                    {
                        "id": "ExampleOnnx",
                        "status": "ready",
                        "invoked": True,
                        "preprocess_version": "unknown",
                        "postprocess_version": "unknown",
                    }
                    ],
                "result_sha256": _image_hash(export),
            }
        ),
        encoding="utf-8",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case",
                        "capability_id": "effect",
                        "parameters": {"amount": 0.5, "opacity": 1.0},
                        "candidate": {
                            "execution": str(trace),
                            "export": str(export),
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = audit_candidate_invocations(
        cases_path=cases,
        graph_path=graphs,
        registry_path=registry,
    )

    assert report["gate"] == "passed"
    assert report["passed"] == 1
    assert report["invoked_logical_models"] == ["Example"]
    assert report["invoked_model_ids"] == ["ExampleOnnx"]
    assert report["model_role_counts"] == {"active-invoked": 1}
    assert report["active_contract_gate"] == "blocked"


def test_audit_fails_when_required_model_is_not_invoked(tmp_path: Path) -> None:
    model = tmp_path / "models/example.onnx"
    model.parent.mkdir()
    model.write_bytes(b"model")
    registry = tmp_path / "model.yaml"
    registry.write_text(
        """version: '1.0'
model_root: models
selection: {primary: onnxruntime, fallback: openvino}
models:
  - id: Example
    logical_id: Example
    task: segmentation
    format: onnx
    path: example.onnx
    inference_class: ai.model.onnx.example:ExampleInference
    backend: onnxruntime
""",
        encoding="utf-8",
    )
    graphs = tmp_path / "graphs.json"
    graphs.write_text(
        json.dumps(
            {
                "graphs": [
                    {
                        "capability_id": "effect",
                        "implementation": "model-backed",
                        "required_models": ["Example"],
                        "conditional_models": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    export = tmp_path / "export.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(export)
    trace = tmp_path / "execution.json"
    trace.write_text(
        json.dumps(
            {
                "status": "ready",
                "capabilities": ["effect"],
                "models": [],
                "result_sha256": _image_hash(export),
            }
        ),
        encoding="utf-8",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case",
                        "capability_id": "effect",
                        "parameters": {"amount": 0.5},
                        "candidate": {
                            "execution": str(trace),
                            "export": str(export),
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = audit_candidate_invocations(
        cases_path=cases,
        graph_path=graphs,
        registry_path=registry,
    )

    assert report["gate"] == "blocked"
    assert report["failed"] == 1
    assert report["results"][0]["issues"] == ["required-model-not-invoked"]


def test_audit_rejects_stale_model_contract_versions(tmp_path: Path) -> None:
    model = tmp_path / "models/example.onnx"
    model.parent.mkdir()
    model.write_bytes(b"model")
    registry = tmp_path / "model.yaml"
    registry.write_text(
        """version: '1.0'
model_root: models
selection: {primary: onnxruntime, fallback: openvino}
models:
  - id: Example
    logical_id: Example
    task: segmentation
    format: onnx
    path: example.onnx
    inference_class: ai.model.onnx.example:ExampleInference
    backend: onnxruntime
    preprocess_version: input-v2
    postprocess_version: output-v2
""",
        encoding="utf-8",
    )
    graphs = tmp_path / "graphs.json"
    graphs.write_text(
        json.dumps(
            {
                "graphs": [
                    {
                        "capability_id": "effect",
                        "implementation": "model-backed",
                        "required_models": ["Example"],
                        "conditional_models": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    export = tmp_path / "export.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(export)
    trace = tmp_path / "execution.json"
    trace.write_text(
        json.dumps(
            {
                "status": "ready",
                "capabilities": ["effect"],
                "models": [
                    {
                        "id": "Example",
                        "status": "ready",
                        "invoked": True,
                        "preprocess_version": "input-v1",
                        "postprocess_version": "output-v2",
                    }
                ],
                "result_sha256": _image_hash(export),
            }
        ),
        encoding="utf-8",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case",
                        "capability_id": "effect",
                        "parameters": {"amount": 0.5},
                        "candidate": {
                            "execution": str(trace),
                            "export": str(export),
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = audit_candidate_invocations(
        cases_path=cases,
        graph_path=graphs,
        registry_path=registry,
    )

    assert report["gate"] == "blocked"
    assert report["results"][0]["issues"] == [
        "model-contract-version-mismatch"
    ]
