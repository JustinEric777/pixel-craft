import hashlib
import json
from pathlib import Path

from scripts.build_core_interaction_matrix import build as build_interactions
from scripts.build_core_ui_state_matrix import build as build_ui
from scripts.validate_core_interaction_matrix import validate as validate_interactions
from scripts.validate_core_ui_state_matrix import validate as validate_ui

ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_core_ui_matrix_covers_all_visible_tools_and_parameters() -> None:
    paths = {
        "ui": ROOT / "configs/ui/editor.json",
        "schema": ROOT / "configs/capabilities/parameter-schema.json",
        "workspace_states": ROOT / "configs/parity/core-workspace-states.json",
        "inventory": ROOT
        / "test_data/outputs/luminar-1.28.0-23071/inventory/ui-contract.json",
    }
    ui = _json(paths["ui"])
    schema = _json(paths["schema"])
    workspace_states = _json(paths["workspace_states"])
    payload = build_ui(
        ui=ui,
        schema=schema,
        workspace_states=workspace_states,
        inventory=_json(paths["inventory"]),
        reference_id="luminar-neo-macos-1.28.0-23071",
        source_fingerprints={name: _sha256(path) for name, path in paths.items()},
    )
    report = validate_ui(
        payload,
        ui=ui,
        schema=schema,
        workspace_states=workspace_states,
        source_paths=paths,
    )
    assert payload["state_count"] == 170
    assert payload["capability_count"] == 40
    assert payload["parameter_state_count"] == 74
    assert payload["workspace_state_count"] == 16
    assert all("source_state_id" not in record for record in payload["records"])
    by_id = {record["id"]: record for record in payload["records"]}
    assert by_id["workspace:export-dialog"]["surface_owner"] == "os"
    assert by_id["workspace:export-dialog"]["comparison_mode"] == "semantic"
    assert "semantic-parity" in by_id["workspace:export-dialog"]["required_evidence"]
    assert all(
        record["comparison_mode"] == "pixel"
        for state_id, record in by_id.items()
        if state_id != "workspace:export-dialog"
    )
    assert len(payload["matrix_fingerprint"]) == 64
    assert report["definition_gate"] == "passed"


def test_core_interaction_matrix_covers_all_visible_tool_parameters() -> None:
    paths = {
        "ui": ROOT / "configs/ui/editor.json",
        "schema": ROOT / "configs/capabilities/parameter-schema.json",
        "contracts": ROOT / "configs/parity/interaction-contracts.json",
    }
    ui = _json(paths["ui"])
    schema = _json(paths["schema"])
    contracts = _json(paths["contracts"])
    payload = build_interactions(
        ui=ui,
        schema=schema,
        contracts=contracts,
        reference_id="luminar-neo-macos-1.28.0-23071",
        source_fingerprints={name: _sha256(path) for name, path in paths.items()},
    )
    report = validate_interactions(
        payload,
        ui=ui,
        schema=schema,
        contracts=contracts,
        source_paths=paths,
    )
    assert payload["contract_count"] == 84
    assert payload["workflow_contract_count"] == 10
    assert payload["parameter_contract_count"] == 74
    assert all("source_contract_id" not in record for record in payload["records"])
    assert len(payload["matrix_fingerprint"]) == 64
    assert all("events" in record for record in payload["records"])
    assert report["definition_gate"] == "passed"
