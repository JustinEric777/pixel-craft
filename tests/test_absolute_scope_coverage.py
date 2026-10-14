from scripts.validate_absolute_scope_coverage import run


def _payloads() -> dict[str, object]:
    return {
        "ui": {"tool_groups": [{"capabilities": ["tool"]}]},
        "schema": {
            "common_parameters": {
                "amount": {"type": "float", "min": 0.0, "max": 1.0}
            },
            "capabilities": {"tool": {"parameters": ["amount"]}},
        },
        "main_cases": {
            "cases": [
                {
                    "capability_id": "tool",
                    "input": {"sha256": "a"},
                    "parameters": {"amount": 0.4},
                }
            ]
        },
        "exact_queue": {
            "records": [
                {
                    "kind": "effect",
                    "capability_id": "tool",
                    "input": {"sha256": "b"},
                    "parameters": {"amount": 0.0},
                },
                {
                    "kind": "effect",
                    "capability_id": "tool",
                    "input": {"sha256": "c"},
                    "parameters": {"amount": 1.0},
                },
            ]
        },
        "ui_matrix": {
            "matrix_fingerprint": "a" * 64,
            "records": [{"id": "workspace:catalog"}]
        },
        "ui_reference": {
            "matrix_fingerprint": "a" * 64,
            "records": [
                {
                    "matrix_state_id": "workspace:catalog",
                    "status": "verified",
                    "issues": [],
                }
            ]
        },
        "ui_execution": {
            "matrix_fingerprint": "a" * 64,
            "records": [{"matrix_state_id": "workspace:catalog"}]
        },
        "interaction_matrix": {
            "matrix_fingerprint": "b" * 64,
            "records": [{"id": "workflow:interaction"}]
        },
        "native_ids": {"workflow:interaction"},
        "browser_execution": {
            "matrix_fingerprint": "b" * 64,
            "records": [{"id": "workflow:interaction", "status": "passed"}],
        },
    }


def test_absolute_scope_passes_complete_minimum_matrix() -> None:
    report = run(**_payloads())

    assert report["gate"] == "passed"
    assert report["issue_count"] == 0


def test_absolute_scope_reports_capability_parameter_overrides() -> None:
    payloads = _payloads()
    payloads["schema"]["capabilities"]["tool"]["parameter_overrides"] = {
        "amount": {
            "min": -5.0,
            "max": 5.0,
            "native_min": -100.0,
            "native_max": 100.0,
            "signed": True,
        }
    }

    report = run(**payloads)

    assert report["capabilities"][0]["parameter_definitions"]["amount"] == {
        "type": "float",
        "min": -5.0,
        "max": 5.0,
        "native_min": -100.0,
        "native_max": 100.0,
        "signed": True,
    }


def test_absolute_scope_reports_holdout_and_interaction_gaps() -> None:
    payloads = _payloads()
    payloads["exact_queue"] = {"records": []}
    payloads["native_ids"] = set()
    payloads["browser_execution"] = {"records": []}

    report = run(**payloads)

    assert report["gate"] == "blocked"
    assert report["issues"]["missing_exact_amount_anchors"] == ["tool"]
    assert report["issues"]["insufficient_holdout_inputs"] == ["tool"]
    assert report["issues"]["missing_native_interactions"] == [
        "workflow:interaction"
    ]
    assert report["issues"]["missing_browser_interactions"] == [
        "workflow:interaction"
    ]


def test_absolute_scope_requires_current_matrix_ids_without_fallback() -> None:
    payloads = _payloads()
    payloads["ui_reference"] = {"records": [{"state": "catalog"}]}
    payloads["ui_execution"] = {"records": [{"state": "catalog"}]}
    payloads["interaction_matrix"] = {
        "records": [{"id": "tool:tool:parameter:amount"}]
    }
    payloads["native_ids"] = {"interaction"}
    payloads["browser_execution"] = {"records": [{"id": "interaction"}]}

    report = run(**payloads)

    assert report["issues"]["missing_ui_reference_states"] == [
        "workspace:catalog"
    ]
    assert report["issues"]["missing_ui_execution_states"] == [
        "workspace:catalog"
    ]
    assert report["issues"]["missing_native_interactions"] == [
        "tool:tool:parameter:amount"
    ]
    assert report["issues"]["missing_browser_interactions"] == [
        "tool:tool:parameter:amount"
    ]
    assert report["issues"]["unexpected_ui_reference_evidence"] == ["catalog"]
    assert report["issues"]["unexpected_ui_execution_evidence"] == ["catalog"]
    assert report["issues"]["unexpected_native_interactions"] == ["interaction"]
    assert report["issues"]["unexpected_browser_interactions"] == ["interaction"]


def test_absolute_scope_rejects_invalid_current_ui_evidence() -> None:
    payloads = _payloads()
    payloads["ui_reference"]["records"][0]["status"] = "invalid-evidence"
    payloads["ui_execution"]["matrix_fingerprint"] = "stale"

    report = run(**payloads)

    assert report["issues"]["missing_ui_reference_states"] == [
        "workspace:catalog"
    ]
    assert report["issues"]["missing_ui_execution_states"] == [
        "workspace:catalog"
    ]
    assert report["issues"]["invalid_ui_reference_evidence"] == [
        "workspace:catalog"
    ]
    assert report["issues"]["invalid_ui_execution_evidence"] == [
        "workspace:catalog"
    ]
