from pathlib import Path

import numpy as np

from ai.model.registry import ModelRecord, ModelRegistry
from scripts.validate_model_backend_parity import (
    _compare_semantics,
    _compare_sequences,
    _fixture,
    _pairs,
    _tensor_metrics,
)


def _record(model_id: str, logical_id: str, model_format: str) -> ModelRecord:
    suffix = ".xml" if model_format == "openvino_ir" else ".onnx"
    return ModelRecord(
        id=model_id,
        logical_id=logical_id,
        task="segmentation",
        format=model_format,
        path=Path(model_id + suffix),
    )


def test_fixture_is_deterministic_and_covers_boundary_values() -> None:
    first = _fixture("gradient", height=23, width=31)
    second = _fixture("gradient", height=23, width=31)

    np.testing.assert_array_equal(first, second)
    assert first.dtype == np.uint8
    assert int(first.min()) == 0
    assert int(first.max()) == 255


def test_tensor_metrics_enforce_shape_finite_and_numeric_tolerances() -> None:
    passed = _tensor_metrics(
        np.asarray([0.0, 1.0], dtype=np.float32),
        np.asarray([0.0, 1.00001], dtype=np.float32),
    )
    failed = _tensor_metrics(
        np.asarray([0.0, 1.0], dtype=np.float32),
        np.asarray([0.0, 1.1], dtype=np.float32),
    )

    assert passed["status"] == "passed"
    assert failed["status"] == "failed"
    assert _tensor_metrics(np.zeros((1, 2)), np.zeros((2, 1)))["status"] == "shape-mismatch"
    assert _tensor_metrics(np.asarray([np.nan]), np.asarray([0.0]))["status"] == "non-finite"


def test_sequence_and_semantic_comparison_allow_backend_specific_tensor_names() -> None:
    primary = {"onnx-output": np.asarray([[1.0]], dtype=np.float32)}
    fallback = {"ir-output": np.asarray([[1.0]], dtype=np.float32)}

    assert _compare_sequences(primary, fallback)["status"] == "passed"
    assert _compare_semantics({"mask": primary["onnx-output"]}, {"mask": fallback["ir-output"]})[
        "status"
    ] == "passed"
    assert _compare_semantics({"mask": primary["onnx-output"]}, {"labels": fallback["ir-output"]})[
        "status"
    ] == "failed"


def test_pairs_select_only_required_ir_fallbacks_with_onnx_primaries() -> None:
    primary = _record("depth-onnx", "depth", "onnx")
    fallback = _record("depth-ir", "depth", "openvino_ir")
    unused = _record("unused-ir", "unused", "openvino_ir")
    registry = ModelRegistry(records={item.id: item for item in (primary, fallback, unused)})
    source_map = {
        "selected_variants": {"depth": "depth-onnx", "unused": "unused-ir"},
        "models": [
            {"id": "depth-onnx", "product_scope_status": "required-direct"},
            {"id": "depth-ir", "product_scope_status": "required-direct"},
            {"id": "unused-ir", "product_scope_status": "inventory-unreachable"},
        ],
    }

    assert _pairs(registry, source_map) == [(primary, fallback)]
