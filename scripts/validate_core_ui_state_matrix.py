"""Validate the frozen core UI matrix against its current source contracts."""

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


def validate(
    payload: dict[str, Any],
    *,
    ui: dict[str, Any],
    schema: dict[str, Any],
    workspace_states: dict[str, Any],
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
        raise TypeError("core UI matrix records must be a list")
    ids = [str(record.get("id")) for record in records if isinstance(record, dict)]
    if len(ids) != len(records) or len(ids) != len(set(ids)):
        issues.append({"id": "invalid-or-duplicate-state-id"})
    expected = {
        str(record["id"]) for record in workspace_states.get("records", [])
    }
    for capability_id in capabilities:
        expected.update(
            {
                f"tool:{capability_id}:collapsed",
                f"tool:{capability_id}:expanded",
            }
        )
        expected.update(
            f"tool:{capability_id}:parameter:{parameter}:modified"
            for parameter in schema["capabilities"][capability_id]["parameters"]
        )
    if missing := sorted(expected - set(ids)):
        issues.append({"id": "missing-required-states", "states": missing})
    if extra := sorted(set(ids) - expected):
        issues.append({"id": "unexpected-states", "states": extra})
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
        if record.get("source_state_id") is not None:
            issues.append(
                {"id": "historical-state-alias-forbidden", "state": record.get("id")}
            )
        surface_owner = record.get("surface_owner")
        comparison_mode = record.get("comparison_mode")
        if surface_owner not in {"app", "os"}:
            issues.append({"id": "invalid-surface-owner", "state": record.get("id")})
        if comparison_mode not in {"pixel", "semantic"}:
            issues.append({"id": "invalid-comparison-mode", "state": record.get("id")})
        if surface_owner == "os" and comparison_mode != "semantic":
            issues.append({"id": "os-surface-must-be-semantic", "state": record.get("id")})
        required = record.get("required_evidence")
        expected_evidence = {
            "native-reference",
            "browser-current-build",
            f"{comparison_mode}-parity",
        }
        if not isinstance(required, list) or not expected_evidence <= set(required):
            issues.append(
                {"id": "incomplete-required-evidence", "state": record.get("id")}
            )
    counts = {
        "capability_count": len(capabilities),
        "state_count": len(expected),
        "workspace_state_count": len(workspace_states.get("records", [])),
        "parameter_state_count": sum(
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
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
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
        "--workspace-states",
        type=Path,
        default=ROOT / "configs/parity/core-workspace-states.json",
    )
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    paths = {
        "ui": args.ui.resolve(),
        "schema": args.schema.resolve(),
        "workspace_states": args.workspace_states.resolve(),
        "inventory": (
            args.inventory or profile.capture_root.parent / "inventory/ui-contract.json"
        ).resolve(),
    }
    report = validate(
        json.loads(args.matrix.read_text(encoding="utf-8")),
        ui=json.loads(paths["ui"].read_text(encoding="utf-8")),
        schema=json.loads(paths["schema"].read_text(encoding="utf-8")),
        workspace_states=json.loads(
            paths["workspace_states"].read_text(encoding="utf-8")
        ),
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
