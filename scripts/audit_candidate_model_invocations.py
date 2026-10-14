"""Verify that model-backed candidate effects invoked their required models."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.model_contract import ModelContractCatalog
from ai.model.registry import ModelRegistry
from configs.reference import load_reference_catalog

VALIDATED_CONTRACT_STATES = {
    "validated",
    "model-specific-validated",
    "parity-validated",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _image_content_sha256(path: Path) -> str:
    with Image.open(path) as image:
        return hashlib.sha256(
            image.mode.encode("ascii")
            + str(image.size).encode("ascii")
            + image.tobytes()
        ).hexdigest()


def _is_active(parameters: dict[str, Any]) -> bool:
    if float(parameters.get("opacity", 1.0)) <= 0.0:
        return False
    amount = parameters.get("amount")
    return amount is None or float(amount) != 0.0


def audit_candidate_invocations(
    *,
    cases_path: Path,
    graph_path: Path,
    registry_path: Path,
    contract_root: Path | None = None,
    source_map_path: Path | None = None,
) -> dict[str, object]:
    cases = _load(cases_path).get("cases", [])
    graphs = {
        str(item["capability_id"]): item
        for item in _load(graph_path).get("graphs", [])
    }
    registry = ModelRegistry.from_yaml(registry_path)
    contracts = ModelContractCatalog(contract_root or ROOT / "models/contracts")
    source_consumers: dict[str, list[str]] = {}
    if source_map_path and source_map_path.is_file():
        source_map = _load(source_map_path)
        source_consumers = {
            str(item.get("id", "")): [str(value) for value in item.get("consumers", [])]
            for item in source_map.get("models", [])
        }

    def logical_id(model_id: str) -> str:
        record = registry.records.get(model_id)
        return (record.logical_id or record.id) if record else model_id

    results: list[dict[str, object]] = []
    capability_counts: Counter[str] = Counter()
    invoked_model_ids: set[str] = set()
    invoked_logical_models: set[str] = set()
    for case in cases:
        capability_id = str(case.get("capability_id", ""))
        graph = graphs.get(capability_id)
        if not graph or graph.get("implementation") != "model-backed":
            continue
        parameters = dict(case.get("parameters", {}))
        if not _is_active(parameters):
            continue
        capability_counts[capability_id] += 1
        required = {
            logical_id(str(model_id))
            for model_id in graph.get("required_models", [])
        }
        trace_value = dict(case.get("candidate", {})).get("execution")
        trace_path = Path(str(trace_value)) if trace_value else None
        issues: list[str] = []
        trace: dict[str, Any] = {}
        if trace_path is None or not trace_path.is_file():
            issues.append("execution-trace-missing")
        else:
            try:
                trace = _load(trace_path)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                issues.append("execution-trace-invalid")
        invoked_ids = {
            str(item.get("id", ""))
            for item in trace.get("models", [])
            if item.get("status") == "ready" and item.get("invoked") is True
        }
        invoked = {logical_id(model_id) for model_id in invoked_ids}
        version_mismatches = []
        for item in trace.get("models", []):
            model_id = str(item.get("id", ""))
            if item.get("status") != "ready" or item.get("invoked") is not True:
                continue
            record = registry.records.get(model_id)
            if record is None:
                version_mismatches.append(model_id)
                continue
            actual = (
                item.get("preprocess_version"),
                item.get("postprocess_version"),
            )
            expected = (record.preprocess_version, record.postprocess_version)
            if actual != expected:
                version_mismatches.append(model_id)
        invoked_model_ids.update(invoked_ids)
        invoked_logical_models.update(invoked)
        missing = sorted(required - invoked)
        if missing:
            issues.append("required-model-not-invoked")
        if version_mismatches:
            issues.append("model-contract-version-mismatch")
        if trace and trace.get("status") != "ready":
            issues.append("execution-not-ready")
        if trace and capability_id not in trace.get("capabilities", []):
            issues.append("capability-not-in-trace")
        export_value = dict(case.get("candidate", {})).get("export")
        export_path = Path(str(export_value)) if export_value else None
        if export_path is None or not export_path.is_file():
            issues.append("candidate-export-missing")
        elif trace.get("result_sha256") != _image_content_sha256(export_path):
            issues.append("result-hash-mismatch")
        results.append(
            {
                "case_id": case.get("case_id"),
                "capability_id": capability_id,
                "required_logical_models": sorted(required),
                "invoked_model_ids": sorted(invoked_ids),
                "invoked_logical_models": sorted(invoked),
                "missing_required_models": missing,
                "model_contract_version_mismatches": sorted(set(version_mismatches)),
                "status": "passed" if not issues else "failed",
                "issues": issues,
            }
        )

    covered = set(capability_counts)
    configured_model_backed = {
        capability_id
        for capability_id, graph in graphs.items()
        if graph.get("implementation") == "model-backed"
    }
    configured_logical_models = {
        logical_id(str(model_id))
        for graph in graphs.values()
        if graph.get("implementation") == "model-backed"
        for field in ("required_models", "conditional_models")
        for model_id in graph.get(field, [])
    }

    model_roles = []
    for record in registry.records.values():
        record_logical_id = record.logical_id or record.id
        if record.id in invoked_model_ids:
            role = "active-invoked"
        elif record_logical_id in invoked_logical_models:
            role = "active-alternate"
        elif record_logical_id in configured_logical_models or source_consumers.get(
            record.id
        ):
            role = "configured-not-covered"
        else:
            role = "inventory-unmapped"
        contract = contracts.get(record.id)
        normalization_status = (
            contract.normalization.get("status", "unspecified")
            if contract
            else "missing"
        )
        postprocess_status = (
            contract.postprocess.get("status", "unspecified")
            if contract
            else "missing"
        )
        contract_status = (
            "validated"
            if normalization_status in VALIDATED_CONTRACT_STATES
            and postprocess_status in VALIDATED_CONTRACT_STATES
            else "model-specific-pending"
        )
        model_roles.append(
            {
                "model_id": record.id,
                "logical_id": record_logical_id,
                "format": record.format,
                "backend": record.backend,
                "role": role,
                "consumers": source_consumers.get(record.id, []),
                "contract_status": contract_status,
                "normalization_status": normalization_status,
                "postprocess_status": postprocess_status,
            }
        )

    active_models = [
        item for item in model_roles if item["role"] == "active-invoked"
    ]
    active_contract_pending = [
        item["model_id"]
        for item in active_models
        if item["contract_status"] != "validated"
    ]
    role_counts = Counter(str(item["role"]) for item in model_roles)
    failures = [item for item in results if item["status"] == "failed"]
    return {
        "version": "1.0",
        "cases": str(cases_path),
        "execution_graphs": str(graph_path),
        "model_source_map": str(source_map_path) if source_map_path else None,
        "active_model_backed_case_count": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "covered_capability_count": len(covered),
        "covered_capabilities": sorted(covered),
        "configured_model_backed_capabilities_without_cases": sorted(
            configured_model_backed - covered
        ),
        "invoked_logical_model_count": len(invoked_logical_models),
        "invoked_logical_models": sorted(invoked_logical_models),
        "invoked_model_count": len(invoked_model_ids),
        "invoked_model_ids": sorted(invoked_model_ids),
        "registered_model_count": len(model_roles),
        "model_role_counts": dict(sorted(role_counts.items())),
        "active_contract_validated": len(active_models)
        - len(active_contract_pending),
        "active_contract_pending": len(active_contract_pending),
        "active_contract_pending_models": sorted(active_contract_pending),
        "active_contract_gate": (
            "passed" if active_models and not active_contract_pending else "blocked"
        ),
        "model_roles": model_roles,
        "gate": "passed" if results and not failures else "blocked",
        "capability_case_counts": dict(sorted(capability_counts.items())),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--cases", type=Path)
    parser.add_argument(
        "--execution-graphs",
        type=Path,
        default=ROOT / "configs/capabilities/execution-graphs.json",
    )
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument(
        "--contract-root", type=Path, default=ROOT / "models/contracts"
    )
    parser.add_argument("--model-source-map", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-active-contracts",
        action="store_true",
        help="block when an actually invoked product model lacks a model-specific contract",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    report = audit_candidate_invocations(
        cases_path=(
            args.cases
            or profile.diagnostics_root / "parity-cases-candidates.json"
        ).resolve(),
        graph_path=args.execution_graphs.resolve(),
        registry_path=args.registry.resolve(),
        contract_root=args.contract_root.resolve(),
        source_map_path=(
            args.model_source_map
            or profile.diagnostics_root / "model-source-map.json"
        ).resolve(),
    )
    report["reference_id"] = profile.id
    output = (
        args.output
        or profile.diagnostics_root / "candidate-model-invocations.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "active_model_backed_case_count",
                    "passed",
                    "failed",
                    "covered_capability_count",
                    "invoked_logical_model_count",
                    "invoked_model_count",
                    "active_contract_validated",
                    "active_contract_pending",
                    "active_contract_gate",
                    "gate",
                )
            },
            ensure_ascii=False,
        )
    )
    passed = report["gate"] == "passed" and (
        not args.require_active_contracts
        or report["active_contract_gate"] == "passed"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
