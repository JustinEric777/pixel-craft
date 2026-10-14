from scripts.build_model_disposition import build_disposition


def _model(
    model_id: str,
    *,
    scope: str,
    selected: bool = False,
    contract: str = "pending-model-specific",
) -> dict:
    return {
        "id": model_id,
        "logical_id": "logical",
        "format": "onnx" if selected else "openvino_ir",
        "product_scope_status": scope,
        "runtime_selected": selected,
        "contract_status": contract,
        "consumers": [],
        "product_capabilities": [],
    }


def test_disposition_retains_validated_primary_and_retires_proven_dead_or_divergent() -> None:
    source_map = {
        "models": [
            _model(
                "primary",
                scope="required-direct",
                selected=True,
                contract="model-specific",
            ),
            _model("fallback", scope="required-direct"),
            _model("unused", scope="inventory-unreachable"),
        ]
    }
    backend = {"results": [{"fallback_model_id": "fallback", "status": "failed"}]}

    report = build_disposition(source_map, backend)

    assert report["gate"] == "passed"
    assert report["counts"] == {"retained": 1, "retired": 2}
    assert report["active_model_ids"] == ["primary"]


def test_disposition_blocks_required_models_without_terminal_evidence() -> None:
    report = build_disposition(
        {"models": [_model("unknown", scope="required-transitive")]},
        {"results": []},
    )

    assert report["gate"] == "blocked"
    assert report["counts"] == {"blocked": 1}
