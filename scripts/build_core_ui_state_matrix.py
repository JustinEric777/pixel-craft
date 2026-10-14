"""Build the frozen required-state matrix for the local free core UI."""

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


def _capabilities(ui: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (str(group["id"]), str(capability))
        for group in ui.get("tool_groups", [])
        for capability in group.get("capabilities", [])
    ]


def _native_tools(
    ui: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, str]:
    groups = {
        str(group.get("id", "")).casefold(): list(group.get("tools", []))
        for group in inventory.get("tool_groups", [])
    }
    result: dict[str, str] = {}
    for group in ui.get("tool_groups", []):
        group_id = str(group["id"])
        capabilities = [str(item) for item in group.get("capabilities", [])]
        tools = groups.get(group_id.casefold(), [])
        if group_id == "common":
            tools = [item for item in tools if item != "MPLayerProperties"]
        if len(tools) != len(capabilities):
            raise ValueError(
                f"native tool count mismatch for {group_id}: "
                f"{len(tools)} != {len(capabilities)}"
            )
        result.update(zip(capabilities, (str(item) for item in tools), strict=True))
    return result


def build(
    *,
    ui: dict[str, Any],
    schema: dict[str, Any],
    workspace_states: dict[str, Any],
    inventory: dict[str, Any],
    reference_id: str,
    source_fingerprints: dict[str, str],
) -> dict[str, Any]:
    capabilities = _capabilities(ui)
    native_tools = _native_tools(ui, inventory)
    records: list[dict[str, Any]] = []
    for state in workspace_states.get("records", []):
        state_id = str(state["id"])
        if not state_id.startswith("workspace:"):
            raise ValueError(f"invalid workspace state id: {state_id}")
        surface_owner = str(state.get("surface_owner", "app"))
        comparison_mode = str(state.get("comparison_mode", "pixel"))
        if surface_owner not in {"app", "os"}:
            raise ValueError(f"invalid surface owner for {state_id}: {surface_owner}")
        if comparison_mode not in {"pixel", "semantic"}:
            raise ValueError(
                f"invalid comparison mode for {state_id}: {comparison_mode}"
            )
        if surface_owner == "os" and comparison_mode != "semantic":
            raise ValueError(f"OS-owned state must use semantic comparison: {state_id}")
        records.append(
            {
                "id": state_id,
                "kind": "workspace-state",
                "workspace": str(state["workspace"]),
                "surface_owner": surface_owner,
                "comparison_mode": comparison_mode,
                "capability_id": None,
                "parameter": None,
                "native_tool": None,
                "required_evidence": [
                    "native-reference",
                    "browser-current-build",
                    f"{comparison_mode}-parity",
                ],
            }
        )
    capability_schemas = schema.get("capabilities", {})
    for group_id, capability_id in capabilities:
        definition = capability_schemas.get(capability_id)
        if not isinstance(definition, dict):
            raise TypeError(f"missing parameter schema for {capability_id}")
        base = {
            "workspace": "edit",
            "surface_owner": "app",
            "comparison_mode": "pixel",
            "group_id": group_id,
            "capability_id": capability_id,
            "native_tool": native_tools[capability_id],
            "required_evidence": [
                "native-reference",
                "browser-current-build",
                "pixel-parity",
            ],
        }
        for state in ("collapsed", "expanded"):
            records.append(
                {
                    **base,
                    "id": f"tool:{capability_id}:{state}",
                    "kind": "tool-panel-state",
                    "state": state,
                    "parameter": None,
                }
            )
        for parameter in definition.get("parameters", []):
            records.append(
                {
                    **base,
                    "id": f"tool:{capability_id}:parameter:{parameter}:modified",
                    "kind": "tool-parameter-state",
                    "state": "modified",
                    "parameter": str(parameter),
                }
            )
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("core UI state ids must be unique")
    return {
        "version": "1.0",
        "matrix_type": "core-ui-required-states",
        "reference_id": reference_id,
        "scope": "local-free-core",
        "source_fingerprints": source_fingerprints,
        "matrix_fingerprint": _fingerprint(records),
        "workspace_state_count": len(workspace_states.get("records", [])),
        "capability_count": len(capabilities),
        "parameter_state_count": sum(
            len(schema["capabilities"][capability_id]["parameters"])
            for _group_id, capability_id in capabilities
        ),
        "state_count": len(records),
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
        "--workspace-states",
        type=Path,
        default=ROOT / "configs/parity/core-workspace-states.json",
    )
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--inventory", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
    )
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
    payload = build(
        ui=json.loads(paths["ui"].read_text(encoding="utf-8")),
        schema=json.loads(paths["schema"].read_text(encoding="utf-8")),
        workspace_states=json.loads(
            paths["workspace_states"].read_text(encoding="utf-8")
        ),
        inventory=json.loads(paths["inventory"].read_text(encoding="utf-8")),
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
                "state_count": payload["state_count"],
                "capability_count": payload["capability_count"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
