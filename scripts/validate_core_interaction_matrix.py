"""Validate the frozen core interaction matrix against current contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(
    payload: dict[str, Any],
    *,
    ui: dict[str, Any],
    schema: dict[str, Any],
    contracts: dict[str, Any],
    source_paths: dict[str, Path],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    capabilities = [
        str(capability)
        for group in ui.get("tool_groups", [])
        for capability in group.get("capabilities", [])
    ]
    records = payload.get("records")
    if not isinstance(records, list):
        raise TypeError("core interaction matrix records must be a list")
    ids = [str(record.get("id")) for record in records if isinstance(record, dict)]
    if len(ids) != len(records) or len(ids) != len(set(ids)):
        issues.append({"id": "invalid-or-duplicate-contract-id"})
    expected = {
        f"workflow:{contract['id']}" for contract in contracts.get("contracts", [])
    }
    for capability_id in capabilities:
        expected.update(
            f"tool:{capability_id}:parameter:{parameter}"
            for parameter in schema["capabilities"][capability_id]["parameters"]
        )
    if missing := sorted(expected - set(ids)):
        issues.append({"id": "missing-required-contracts", "contracts": missing})
    if extra := sorted(set(ids) - expected):
        issues.append({"id": "unexpected-contracts", "contracts": extra})
    fingerprints = payload.get("source_fingerprints")
    if not isinstance(fingerprints, dict):
        issues.append({"id": "missing-source-fingerprints"})
        fingerprints = {}
    for name, path in source_paths.items():
        if fingerprints.get(name) != _sha256(path):
            issues.append({"id": "stale-source-fingerprint", "source": name})
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("source_contract_id") is not None:
            issues.append(
                {
                    "id": "historical-contract-alias-forbidden",
                    "contract": record.get("id"),
                }
            )
        required = record.get("required_evidence")
        if not isinstance(required, list) or not {
            "native-observation",
            "browser-current-build",
            "visible-assertions",
            "state-assertions",
        } <= set(required):
            issues.append(
                {
                    "id": "incomplete-required-evidence",
                    "contract": record.get("id"),
                }
            )
    counts = {
        "capability_count": len(capabilities),
        "contract_count": len(expected),
        "workflow_contract_count": len(contracts.get("contracts", [])),
        "parameter_contract_count": sum(
            len(schema["capabilities"][capability_id]["parameters"])
            for capability_id in capabilities
        ),
    }
    for field, value in counts.items():
        if payload.get(field) != value:
            issues.append(
                {
                    "id": "count-mismatch",
                    "field": field,
                    "expected": value,
                    "actual": payload.get(field),
                }
            )
    return {
        "version": "1.0",
        **counts,
        "issue_count": len(issues),
        "definition_gate": "passed" if not issues else "blocked",
        "execution_gate": "pending-native-and-browser-evidence",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ROOT / "configs/parity/core-interaction-matrix.json",
    )
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = {
        "ui": args.ui.resolve(),
        "schema": args.schema.resolve(),
        "contracts": args.contracts.resolve(),
    }
    report = validate(
        json.loads(args.matrix.read_text(encoding="utf-8")),
        ui=json.loads(paths["ui"].read_text(encoding="utf-8")),
        schema=json.loads(paths["schema"].read_text(encoding="utf-8")),
        contracts=json.loads(paths["contracts"].read_text(encoding="utf-8")),
        source_paths=paths,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["definition_gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
