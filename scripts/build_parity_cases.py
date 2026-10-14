"""Build deterministic black-box parity cases from the reference matrix."""

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

import yaml

from configs.reference import load_reference_catalog


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")


def _visible_assignments(
    matrix: dict[str, Any], ui: dict[str, Any], parity: dict[str, Any]
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    fallback_roles = parity.get("scope", {}).get(
        "fallback_sample_roles_by_tool_group", {}
    )
    samples_by_role = {
        str(item.get("role")): str(item["id"])
        for item in matrix.get("samples", [])
        if item.get("role")
    }
    groups = list(ui.get("tool_groups", []))
    catalog_capabilities = [
        str(item["capability_id"])
        for item in ui.get("catalog_actions", [])
        if item.get("capability_id")
    ]
    if catalog_capabilities:
        groups.append({"id": "catalog", "capabilities": catalog_capabilities})
    for group in groups:
        role = fallback_roles.get(group.get("id"))
        if not role:
            continue
        if role not in samples_by_role:
            raise ValueError(f"parity fallback sample role is missing: {role}")
        sample_id = samples_by_role[role]
        for capability_id in group.get("capabilities", []):
            assignments[str(capability_id)] = str(sample_id)
    sample_ids = {str(item["id"]) for item in matrix.get("samples", [])}
    unknown = sorted(set(assignments.values()) - sample_ids)
    if unknown:
        raise ValueError(f"parity fallback samples are missing: {', '.join(unknown)}")
    return assignments


def _default_assets(manifest: dict[str, Any]) -> dict[str, str]:
    defaults: dict[str, str] = {}
    for record in manifest.get("records", []):
        family = str(record.get("family", ""))
        if family and family not in defaults:
            defaults[family] = str(record["id"])
    return defaults


def build_cases(
    matrix: dict[str, Any],
    schema: dict[str, Any],
    *,
    ui: dict[str, Any] | None = None,
    parity: dict[str, Any] | None = None,
    asset_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    definitions = schema.get("common_parameters", {})
    capabilities = {str(item["id"]): item for item in matrix.get("capabilities", [])}
    visible_assignments = _visible_assignments(matrix, ui or {}, parity or {})
    visible_ids = set(visible_assignments)
    explicitly_assigned = {
        str(capability_id)
        for sample in matrix.get("samples", [])
        for capability_id in sample.get("intended_uses", [])
        if str(capability_id) in visible_ids
    }
    for capability_id in visible_assignments:
        current = capabilities.get(capability_id, {"id": capability_id})
        capabilities[capability_id] = {
            **current,
            # The current public schema is authoritative. The reference matrix
            # may describe an older capture and must not drop new parameters.
            "parameters": list(
                schema.get("capabilities", {}).get(capability_id, {}).get("parameters", [])
            ),
        }
    default_assets = _default_assets(asset_manifest or {})
    capture_config = (parity or {}).get("capture", {})
    case_defaults = capture_config.get("case_defaults", {})
    asset_families = capture_config.get("asset_family_by_capability", {})
    cases: list[dict[str, Any]] = []
    for sample in matrix.get("samples", []):
        intended = set(sample.get("intended_uses", [])) & visible_ids
        intended.update(
            capability_id
            for capability_id, sample_id in visible_assignments.items()
            if sample_id == sample["id"] and capability_id not in explicitly_assigned
        )
        for capability_id in sorted(intended):
            capability = capabilities.get(capability_id)
            if capability is None:
                continue
            parameter_names = capability.get("parameters", [])
            parameters = {
                name: definition.get("default")
                for name in parameter_names
                if (definition := definitions.get(name, {})).get("default") is not None
            }
            parameters.update(case_defaults.get(capability_id, {}))
            family = str(asset_families.get(capability_id, ""))
            asset_id = default_assets.get(family)
            if "asset_id" in parameter_names and asset_id:
                parameters = {**parameters, "asset_id": asset_id}
            suffix = hashlib.sha1(
                json.dumps(parameters, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:8]
            case_id = f"{_slug(sample['id'])}__{_slug(capability_id)}__{suffix}"
            cases.append(
                {
                    "case_id": case_id,
                    "sample_id": sample["id"],
                    "capability_id": capability_id,
                    "input": {
                        "path": sample["path"],
                        "sha256": sample.get("sha256"),
                        "width": sample.get("width"),
                        "height": sample.get("height"),
                    },
                    "parameters": parameters,
                    "asset_id": asset_id,
                    "captures": {
                        "luminar_preview": None,
                        "luminar_export": None,
                        "luminar_mask": None,
                        "luminar_ui": None,
                    },
                    "candidate": {"preview": None, "export": None},
                    "status": "pending-reference",
                    "pending_reason": "original Luminar black-box capture is not attached",
                }
            )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--schema", type=Path, default=ROOT / "configs/capabilities/parameter-schema.json")
    parser.add_argument("--ui", type=Path, default=ROOT / "configs/ui/editor.json")
    parser.add_argument("--parity", type=Path, default=ROOT / "configs/parity.yaml")
    parser.add_argument(
        "--assets", type=Path, default=ROOT / "assets/manifests/registry.json"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    matrix_path = (args.matrix or profile.matrix_path).resolve()
    output_path = (args.output or profile.cases_path).resolve()
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    ui = json.loads(args.ui.read_text(encoding="utf-8"))
    parity = yaml.safe_load(args.parity.read_text(encoding="utf-8"))
    asset_manifest = json.loads(args.assets.read_text(encoding="utf-8"))
    cases = build_cases(
        matrix,
        schema,
        ui=ui,
        parity=parity,
        asset_manifest=asset_manifest,
    )
    payload = {
        "version": "1.0.0",
        "generated_by": "scripts/build_parity_cases.py",
        "reference_id": profile.id,
        "dataset_fingerprint": matrix.get("dataset_fingerprint"),
        "status": "pending-reference",
        "case_count": len(cases),
        "cases": cases,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "case_count": len(cases), "status": payload["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
