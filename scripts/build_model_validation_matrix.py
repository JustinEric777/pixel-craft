"""Build one machine-readable validation matrix for every registered model."""

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

from ai.model.model_contract import ModelContractCatalog
from ai.model.registry import ModelRegistry
from configs.reference import load_reference_catalog

VALIDATED = {"validated", "model-specific-validated", "parity-validated"}
TERMINAL = VALIDATED | {"retired-invalid-source"}


def _load(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_matrix(
    registry_path: Path,
    contract_root: Path,
    *,
    runtime_probe_path: Path | None = None,
    source_map_path: Path | None = None,
    invocation_path: Path | None = None,
) -> dict[str, Any]:
    registry = ModelRegistry.from_yaml(registry_path)
    contracts = ModelContractCatalog(contract_root)
    runtime = {
        str(item.get("id")): item
        for item in _load(runtime_probe_path).get("results", [])
    }
    sources = {
        str(item.get("id")): item
        for item in _load(source_map_path).get("models", [])
    }
    roles = {
        str(item.get("model_id")): item
        for item in _load(invocation_path).get("model_roles", [])
    }
    rows: list[dict[str, Any]] = []
    for record in registry.records.values():
        contract = contracts.get(record.id)
        source = sources.get(record.id, {})
        role = roles.get(record.id, {})
        runtime_record = runtime.get(record.id, {})
        normalization_status = (
            str(contract.normalization.get("status", "unspecified"))
            if contract
            else "missing"
        )
        postprocess_status = (
            str(contract.postprocess.get("status", "unspecified"))
            if contract
            else "missing"
        )
        contract_status = (
            "validated"
            if normalization_status in TERMINAL and postprocess_status in TERMINAL
            else "model-specific-pending"
        )
        if record.format == "openvino_ir":
            runtime_status = str(runtime_record.get("status", "not-probed"))
        else:
            runtime_status = record.status
        rows.append(
            {
                "model_id": record.id,
                "logical_id": record.logical_id or record.id,
                "task": record.task,
                "format": record.format,
                "backend": record.backend,
                "registry_status": record.status,
                "artifact": str(record.path),
                "artifact_exists": record.path.is_file(),
                "weights": str(record.weights_path) if record.weights_path else None,
                "weights_exist": (
                    record.weights_path.is_file() if record.weights_path else True
                ),
                "inference_class": record.inference_class,
                "preprocess_version": record.preprocess_version,
                "postprocess_version": record.postprocess_version,
                "contract_status": contract_status if contract else "missing",
                "normalization_status": normalization_status,
                "postprocess_status": postprocess_status,
                "runtime_status": runtime_status,
                "runtime_error": runtime_record.get("error"),
                "role": role.get(
                    "role", source.get("product_scope_status", "inventory-unmapped")
                ),
                "consumers": role.get("consumers", source.get("consumers", [])),
                "product_capabilities": source.get("product_capabilities", []),
                "source_backend_parity": (
                    contract.source_backend_parity if contract else "missing"
                ),
                "luminar_effect_parity": (
                    contract.luminar_effect_parity if contract else "missing"
                ),
            }
        )
    missing_artifacts = [
        item["model_id"]
        for item in rows
        if not item["artifact_exists"] or not item["weights_exist"]
    ]
    missing_contracts = [
        item["model_id"] for item in rows if item["contract_status"] == "missing"
    ]
    return {
        "version": "1.0",
        "generated_by": "scripts/build_model_validation_matrix.py",
        "registry": str(registry_path),
        "contract_root": str(contract_root),
        "count": len(rows),
        "validated": sum(item["contract_status"] == "validated" for item in rows),
        "pending": sum(
            item["contract_status"] == "model-specific-pending" for item in rows
        ),
        "missing_contracts": missing_contracts,
        "missing_artifacts": missing_artifacts,
        "runtime_status_counts": dict(Counter(item["runtime_status"] for item in rows)),
        "role_counts": dict(Counter(item["role"] for item in rows)),
        "task_counts": dict(Counter(item["task"] for item in rows)),
        "presence_gate": (
            "passed" if not missing_contracts and not missing_artifacts else "blocked"
        ),
        "exact_gate": (
            "passed"
            if not missing_contracts
            and not missing_artifacts
            and all(item["contract_status"] == "validated" for item in rows)
            else "blocked"
        ),
        "models": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument("--contract-root", type=Path, default=ROOT / "models/contracts")
    parser.add_argument(
        "--runtime-probe",
        type=Path,
        default=ROOT / "data/diagnostics/openvino-ir-runtime-probe.json",
    )
    parser.add_argument(
        "--source-map",
        type=Path,
    )
    parser.add_argument(
        "--invocations",
        type=Path,
    )
    parser.add_argument("--require-exact", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    source_map = args.source_map or profile.diagnostics_root / "model-source-map.json"
    invocations = (
        args.invocations
        or profile.diagnostics_root / "candidate-model-invocations.json"
    )
    report = build_matrix(
        args.registry.resolve(),
        args.contract_root.resolve(),
        runtime_probe_path=args.runtime_probe.resolve(),
        source_map_path=source_map.resolve(),
        invocation_path=invocations.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("count", "validated", "pending", "presence_gate", "exact_gate")
            },
            ensure_ascii=False,
        )
    )
    gate = report["exact_gate"] if args.require_exact else report["presence_gate"]
    return 0 if gate == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
