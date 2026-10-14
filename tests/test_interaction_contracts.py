import json
from pathlib import Path

from scripts.validate_interaction_contracts import validate

ROOT = Path(__file__).resolve().parents[1]


def test_repository_interaction_contracts_are_complete() -> None:
    payload = json.loads(
        (ROOT / "configs/parity/interaction-contracts.json").read_text(encoding="utf-8")
    )

    report = validate(payload)

    assert report["contract_count"] == 10
    assert report["version"] == "2.0"
    assert report["definition_gate"] == "passed"
    assert report["execution_gate"] == "pending-browser-execution"

    by_id = {contract["id"]: contract for contract in payload["contracts"]}
    catalog_targets = [
        event.get("target")
        for event in by_id["catalog-photo-context-submenu"]["events"]
    ]
    assert "设置评分-submenu" in catalog_targets
    assert "向右旋转 90°" in catalog_targets
    assert by_id["edit-tool-expand-crop"]["final_screenshot_state"] == "tool-collapsed"
    assert by_id["export-dialog-file"]["final_screenshot_state"] == "edit"


def test_contract_validator_rejects_fixed_sleep() -> None:
    payload = json.loads(
        (ROOT / "configs/parity/interaction-contracts.json").read_text(encoding="utf-8")
    )
    payload["contracts"][0]["events"].append({"action": "sleep", "milliseconds": 1000})

    report = validate(payload)

    assert any(issue["id"] == "fixed-sleep-forbidden" for issue in report["issues"])


def test_contract_validator_rejects_v1_payload() -> None:
    payload = json.loads(
        (ROOT / "configs/parity/interaction-contracts.json").read_text(encoding="utf-8")
    )
    payload["version"] = "1.0"

    report = validate(payload)

    assert any(issue["id"] == "contract-version-mismatch" for issue in report["issues"])
