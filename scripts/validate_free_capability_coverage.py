"""Validate that every visible free editor tool has one complete execution contract."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(
    ui_path: Path,
    registry_path: Path,
    schema_path: Path,
    graph_path: Path,
    policy_path: Path,
    cases_path: Path,
) -> dict[str, Any]:
    ui = _load(ui_path)
    registry = _load(registry_path)
    schema = _load(schema_path)
    graphs = _load(graph_path)
    policy = _load(policy_path)
    cases = _load(cases_path)

    visible = [
        str(capability_id)
        for group in ui.get("tool_groups", [])
        for capability_id in group.get("capabilities", [])
    ]
    visible.extend(
        str(item["capability_id"])
        for item in ui.get("catalog_actions", [])
        if item.get("capability_id")
    )
    registry_ids = {str(item["id"]) for item in registry.get("capabilities", [])}
    schema_ids = set(schema.get("capabilities", {}))
    graph_by_id = {
        str(item["capability_id"]): item for item in graphs.get("graphs", [])
    }
    policy_ids = {
        str(capability_id)
        for key in ("image_effect_pipelines", "local_effect_pipelines")
        for capability_id in policy.get(key, [])
    }
    case_counts = Counter(
        str(item.get("capability_id")) for item in cases.get("cases", [])
    )

    duplicate_visible = sorted(
        capability_id
        for capability_id, count in Counter(visible).items()
        if count > 1
    )
    missing_registry = sorted(set(visible) - registry_ids)
    missing_schema = sorted(set(visible) - schema_ids)
    missing_graph = sorted(set(visible) - set(graph_by_id))
    missing_pipeline = sorted(set(visible) - policy_ids)
    missing_cases = sorted(
        capability_id for capability_id in set(visible) if case_counts[capability_id] == 0
    )
    asset_required = set(policy.get("asset_required", [])) & set(visible)
    cases_by_capability: dict[str, list[dict[str, Any]]] = {}
    for item in cases.get("cases", []):
        cases_by_capability.setdefault(str(item.get("capability_id")), []).append(item)
    missing_case_assets = sorted(
        capability_id
        for capability_id in asset_required
        if not any(
            case.get("asset_id") or case.get("parameters", {}).get("asset_id")
            for case in cases_by_capability.get(capability_id, [])
        )
    )
    invalid_graphs = sorted(
        capability_id
        for capability_id in set(visible) & set(graph_by_id)
        if graph_by_id[capability_id].get("implementation")
        not in {"model-backed", "deterministic"}
    )
    issues = {
        "duplicate_visible": duplicate_visible,
        "missing_registry": missing_registry,
        "missing_schema": missing_schema,
        "missing_graph": missing_graph,
        "missing_pipeline": missing_pipeline,
        "missing_cases": missing_cases,
        "missing_case_assets": missing_case_assets,
        "invalid_graphs": invalid_graphs,
    }
    passed = all(not records for records in issues.values())
    return {
        "version": "1.0",
        "visible_tool_count": len(visible),
        "covered_case_count": sum(case_counts[item] > 0 for item in set(visible)),
        "parity_case_count": len(cases.get("cases", [])),
        "issues": issues,
        "gate": "passed" if passed else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--ui", type=Path, default=ROOT / "configs/ui/editor.json")
    parser.add_argument(
        "--registry", type=Path, default=ROOT / "configs/capabilities/registry.json"
    )
    parser.add_argument(
        "--schema", type=Path, default=ROOT / "configs/capabilities/parameter-schema.json"
    )
    parser.add_argument(
        "--graphs", type=Path, default=ROOT / "configs/capabilities/execution-graphs.json"
    )
    parser.add_argument(
        "--policy", type=Path, default=ROOT / "configs/capabilities/policy.json"
    )
    parser.add_argument("--cases", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/diagnostics/free-capability-coverage.json",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    cases_path = (args.cases or profile.cases_path).resolve()
    report = run(
        args.ui.resolve(),
        args.registry.resolve(),
        args.schema.resolve(),
        args.graphs.resolve(),
        args.policy.resolve(),
        cases_path,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
