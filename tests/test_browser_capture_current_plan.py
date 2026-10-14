from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.build_ui_browser_capture_plan import build_plan

ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _plan() -> dict:
    return build_plan(
        _json("configs/parity/core-ui-state-matrix.json"),
        _json("configs/ui/editor.json"),
        _json("configs/capabilities/parameter-schema.json"),
        _json("configs/capabilities/registry.json"),
    )


def test_ui_browser_plan_exactly_covers_current_matrix() -> None:
    plan = _plan()
    matrix = _json("configs/parity/core-ui-state-matrix.json")

    assert plan["version"] == "3.0"
    assert plan["reference_id"] == matrix["reference_id"]
    assert plan["matrix_fingerprint"] == matrix["matrix_fingerprint"]
    assert {record["matrix_state_id"] for record in plan["records"]} == {
        record["id"] for record in matrix["records"]
    }
    assert len(plan["records"]) == 170
    assert "states" not in plan
    assert all("state" not in record for record in plan["records"])


def test_ui_browser_plan_has_typed_current_parameter_recipes() -> None:
    plan = _plan()
    parameter_steps = [
        step
        for record in plan["records"]
        for step in record["steps"]
        if step["type"] == "change-parameter"
    ]

    assert len(parameter_steps) == 75  # 74 matrix states plus the denoise workspace state.
    assert {step["parameter_type"] for step in parameter_steps} == {
        "float",
        "array",
        "asset",
        "boolean",
        "enum",
    }
    assert all(step["locator"] and "data-parameter-id" in step["locator"] for step in parameter_steps)
    assert all("value" in step for step in parameter_steps)
    by_parameter = {
        (step["capability_id"], step["parameter"]): step
        for step in parameter_steps
    }
    assert by_parameter[("details", "amount")]["value"] == 0.3
    assert by_parameter[("blue_hour", "amount")]["value"] == 0.65


def test_ui_browser_builder_rejects_unknown_parameter_type() -> None:
    schema = _json("configs/capabilities/parameter-schema.json")
    schema["common_parameters"]["amount"]["type"] = "mystery"

    with pytest.raises(ValueError, match="unsupported parameter type"):
        build_plan(
            _json("configs/parity/core-ui-state-matrix.json"),
            _json("configs/ui/editor.json"),
            schema,
            _json("configs/capabilities/registry.json"),
        )


def test_interaction_browser_dry_run_covers_current_matrix() -> None:
    result = subprocess.run(
        [
            "node",
            "frontend/scripts/capture-interaction-dpr2.mjs",
            "--contracts",
            "configs/parity/core-interaction-matrix.json",
            "--fixture",
            "test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-manifest.json",
            "--output-root",
            "test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-dry-run",
            "--raw-output",
            "test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-dry-run.json",
            "--dry-run",
            "true",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["supported"] == 84
    assert payload["workflows"] == 10
    assert payload["parameters"] == 74
    assert payload["parameter_types"] == {
        "float": 58,
        "array": 5,
        "asset": 3,
        "boolean": 4,
        "enum": 4,
    }
