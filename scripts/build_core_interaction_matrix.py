"""Build the frozen required-contract matrix for local core interactions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(records: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build(
    *,
    ui: dict[str, Any],
    schema: dict[str, Any],
    contracts: dict[str, Any],
    reference_id: str,
    source_fingerprints: dict[str, str],
) -> dict[str, Any]:
    capabilities = [
        str(capability)
        for group in ui.get("tool_groups", [])
        for capability in group.get("capabilities", [])
    ]
    records: list[dict[str, Any]] = []
    for contract in contracts.get("contracts", []):
        records.append(
            {
                "id": f"workflow:{contract['id']}",
                "kind": "workflow-contract",
                "capability_id": None,
                "parameter": None,
                "initial_fixture": contract.get("initial_fixture", {}),
                "events": contract.get("events", []),
                "visible_assertions": contract.get("visible_assertions", []),
                "api_assertions": contract.get("api_assertions", []),
                "final_screenshot_state": contract.get("final_screenshot_state"),
                "allowed_wait_conditions": contract.get(
                    "allowed_wait_conditions", []
                ),
                "failure_artifacts": contract.get("failure_artifacts", []),
                "required_evidence": [
                    "native-observation",
                    "browser-current-build",
                    "visible-assertions",
                    "state-assertions",
                ],
            }
        )
    for capability_id in capabilities:
        definition = schema.get("capabilities", {}).get(capability_id)
        if not isinstance(definition, dict):
            raise TypeError(f"missing parameter schema for {capability_id}")
        for parameter in definition.get("parameters", []):
            contract_id = f"tool:{capability_id}:parameter:{parameter}"
            records.append(
                {
                    "id": contract_id,
                    "kind": "tool-parameter-contract",
                    "capability_id": capability_id,
                    "parameter": str(parameter),
                    "initial_fixture": {
                        "reset": True,
                        "workspace": "edit",
                        "tool": capability_id,
                    },
                    "events": [
                        {"action": "open-tool", "target": capability_id},
                        {"action": "change-parameter", "target": str(parameter)},
                        {"action": "wait", "condition": "preview-ready"},
                        {"action": "undo", "target": capability_id},
                        {"action": "redo", "target": capability_id},
                        {"action": "reset", "target": str(parameter)},
                        {"action": "export", "target": "current-image"},
                    ],
                    "visible_assertions": [
                        "tool-expanded",
                        "parameter-value-changed",
                        "preview-updated",
                        "undo-restored-preview",
                        "redo-restored-preview",
                        "reset-restored-default",
                        "export-completed",
                    ],
                    "api_assertions": [
                        "parameter-state-changed-once",
                        "undo-restored-state",
                        "redo-restored-state",
                        "reset-restored-default",
                        "export-used-current-state",
                    ],
                    "final_screenshot_state": contract_id,
                    "allowed_wait_conditions": [
                        "preview-ready",
                        "export-ready",
                    ],
                    "failure_artifacts": [
                        "screenshot",
                        "console",
                        "network",
                        "project-state",
                    ],
                    "required_evidence": [
                        "native-observation",
                        "browser-current-build",
                        "visible-assertions",
                        "state-assertions",
                        "preview-export-parity",
                    ],
                }
            )
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("core interaction ids must be unique")
    return {
        "version": "1.0",
        "matrix_type": "core-interaction-required-contracts",
        "reference_id": reference_id,
        "scope": "local-free-core",
        "logical_viewport": contracts.get("logical_viewport"),
        "device_scale_factor": contracts.get("device_scale_factor"),
        "physical_viewport": contracts.get("physical_viewport"),
        "source_fingerprints": source_fingerprints,
        "matrix_fingerprint": _fingerprint(records),
        "workflow_contract_count": len(contracts.get("contracts", [])),
        "capability_count": len(capabilities),
        "parameter_contract_count": sum(
            len(schema["capabilities"][capability_id]["parameters"])
            for capability_id in capabilities
        ),
        "contract_count": len(records),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ui", type=Path, default=ROOT / "configs/ui/editor.json"
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=ROOT / "configs/capabilities/parameter-schema.json",
    )
    parser.add_argument(
        "--contracts",
        type=Path,
        default=ROOT / "configs/parity/interaction-contracts.json",
    )
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "configs/parity/core-interaction-matrix.json",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    paths = {
        "ui": args.ui.resolve(),
        "schema": args.schema.resolve(),
        "contracts": args.contracts.resolve(),
    }
    payload = build(
        ui=json.loads(paths["ui"].read_text(encoding="utf-8")),
        schema=json.loads(paths["schema"].read_text(encoding="utf-8")),
        contracts=json.loads(paths["contracts"].read_text(encoding="utf-8")),
        reference_id=profile.id,
        source_fingerprints={name: _sha256(path) for name, path in paths.items()},
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "contract_count": payload["contract_count"],
                "capability_count": payload["capability_count"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
