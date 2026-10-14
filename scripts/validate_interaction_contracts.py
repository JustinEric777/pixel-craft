"""Validate executable UI interaction contracts without claiming browser execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_IDS = {
    "catalog-photo-context-submenu",
    "catalog-folder-context-scroll",
    "edit-tool-expand-crop",
    "photo-switch-history",
    "preset-import-preview-apply",
    "layer-lifecycle",
    "mask-lifecycle",
    "compare-zoom-pan",
    "multi-image-three-workflows",
    "export-dialog-file",
}
REQUIRED_FIELDS = {
    "initial_fixture",
    "events",
    "visible_assertions",
    "api_assertions",
    "final_screenshot_state",
    "allowed_wait_conditions",
    "failure_artifacts",
}


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if payload.get("version") != "2.0":
        issues.append({"id": "contract-version-mismatch", "expected": "2.0"})
    contracts = payload.get("contracts")
    if not isinstance(contracts, list):
        raise TypeError("interaction contracts must be a list")
    ids = [str(item.get("id")) for item in contracts if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        issues.append({"id": "duplicate-contract-id"})
    missing_ids = sorted(EXPECTED_IDS - set(ids))
    extra_ids = sorted(set(ids) - EXPECTED_IDS)
    if missing_ids:
        issues.append({"id": "missing-contracts", "contracts": missing_ids})
    if extra_ids:
        issues.append({"id": "unexpected-contracts", "contracts": extra_ids})
    for contract in contracts:
        if not isinstance(contract, dict):
            issues.append({"id": "invalid-contract-record"})
            continue
        contract_id = str(contract.get("id"))
        missing = sorted(REQUIRED_FIELDS - set(contract))
        if missing:
            issues.append({"id": "missing-fields", "contract": contract_id, "fields": missing})
            continue
        for field in (
            "events",
            "visible_assertions",
            "api_assertions",
            "allowed_wait_conditions",
            "failure_artifacts",
        ):
            if not isinstance(contract[field], list) or not contract[field]:
                issues.append({"id": "empty-contract-field", "contract": contract_id, "field": field})
        for event in contract["events"]:
            if not isinstance(event, dict) or not event.get("action"):
                issues.append({"id": "invalid-event", "contract": contract_id})
                continue
            if event.get("action") == "sleep" or "milliseconds" in event:
                issues.append({"id": "fixed-sleep-forbidden", "contract": contract_id})
            if event.get("action") == "wait" and event.get("condition") not in contract["allowed_wait_conditions"]:
                issues.append({"id": "undeclared-wait-condition", "contract": contract_id})
    return {
        "version": "2.0",
        "reference_id": payload.get("reference_id"),
        "contract_count": len(contracts),
        "defined": len(contracts) - len({item.get("contract") for item in issues if item.get("contract")}),
        "executed": 0,
        "passed": 0,
        "issue_count": len(issues),
        "definition_gate": "passed" if not issues else "blocked",
        "execution_gate": "pending-browser-execution",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contracts",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "configs/parity/interaction-contracts.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(json.loads(args.contracts.read_text(encoding="utf-8")))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["definition_gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
