import numpy as np
import pytest

from ai.model.model_contract import ModelContract
from ai.model.shared import binary_class_mask


def test_binary_class_mask_extracts_foreground_channel() -> None:
    values = np.asarray([[0.8, 0.2], [0.1, 0.9], [0.6, 0.4], [0.3, 0.7]])
    mask = binary_class_mask({"probabilities": values}, (2, 2))
    np.testing.assert_allclose(mask, [[0.2, 0.9], [0.4, 0.7]])


def test_binary_class_mask_rejects_unknown_contract() -> None:
    with pytest.raises(ValueError, match="binary class output"):
        binary_class_mask({"output": np.zeros((1, 1, 1), dtype=np.float32)}, (2, 2))


def test_model_contract_v2_round_trip_exposes_independent_gates() -> None:
    contract = ModelContract(
        model_id="model",
        format="onnx",
        signature_status="validated",
        runtime_status="ort-smoke-passed",
        source_backend_parity="passed",
        luminar_effect_parity="pending-reference",
    )

    restored = ModelContract.from_dict(contract.to_dict())

    assert restored.version == "contract-v2"
    assert restored.signature_status == "validated"
    assert restored.runtime_status == "ort-smoke-passed"
    assert restored.source_backend_parity == "passed"
    assert restored.luminar_effect_parity == "pending-reference"
