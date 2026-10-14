"""Validate that every registered model has a diagnosable local contract."""

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

VALIDATED = {"validated", "model-specific-validated", "parity-validated"}
TERMINAL = VALIDATED | {"retired-invalid-source"}


def run(
    registry_path: Path,
    contract_root: Path,
    runtime_probe_path: Path | None = None,
) -> dict[str, Any]:
    registry = ModelRegistry.from_yaml(registry_path)
    catalog = ModelContractCatalog(contract_root)
    runtime_status: dict[str, str] = {}
    if runtime_probe_path and runtime_probe_path.is_file():
        probe = json.loads(runtime_probe_path.read_text(encoding="utf-8"))
        runtime_status = {
            item["id"]: str(item.get("status", "unknown"))
            for item in probe.get("results", [])
        }
    records = []
    for record in registry.records.values():
        contract = catalog.get(record.id)
        if contract is None:
            records.append({"model_id": record.id, "status": "missing"})
            continue
        if contract.format != record.format:
            records.append(
                {
                    "model_id": record.id,
                    "status": "format-mismatch",
                    "registry_format": record.format,
                    "contract_format": contract.format,
                    "runtime_status": runtime_status.get(record.id, "not-probed"),
                }
            )
            continue
        normalization_status = contract.normalization.get("status", "unspecified")
        postprocess_status = contract.postprocess.get("status", "unspecified")
        exact_validated = (
            normalization_status in TERMINAL and postprocess_status in TERMINAL
        )
        records.append(
            {
                "model_id": record.id,
                "status": "validated" if exact_validated else "model-specific-pending",
                "normalization_status": normalization_status,
                "postprocess_status": postprocess_status,
                "runtime_status": (
                    runtime_status.get(record.id, "not-probed")
                    if record.format == "openvino_ir"
                    else "onnx-signature-probed"
                ),
                "signature_status": contract.signature_status,
                "contract_runtime_status": contract.runtime_status,
                "source_backend_parity": contract.source_backend_parity,
                "luminar_effect_parity": contract.luminar_effect_parity,
            }
        )
    failures = [item for item in records if item["status"] in {"missing", "format-mismatch"}]
    pending = [item for item in records if item["status"] == "model-specific-pending"]
    status_counts = Counter(item["status"] for item in records)
    return {
        "version": "0.1.0",
        "registry": str(registry_path),
        "contract_root": str(contract_root),
        "count": len(records),
        "valid": len(records) - len(failures),
        "model_specific_validated": sum(item["status"] == "validated" for item in records),
        "model_specific_pending": len(pending),
        "runtime_ready": sum(item.get("runtime_status") == "ready" for item in records),
        "status_counts": dict(status_counts),
        "signature_status_counts": dict(
            Counter(item.get("signature_status", "missing") for item in records)
        ),
        "contract_runtime_status_counts": dict(
            Counter(item.get("contract_runtime_status", "missing") for item in records)
        ),
        "source_backend_parity_counts": dict(
            Counter(item.get("source_backend_parity", "missing") for item in records)
        ),
        "luminar_effect_parity_counts": dict(
            Counter(item.get("luminar_effect_parity", "missing") for item in records)
        ),
        "failures": failures,
        "models": records,
        "presence_gate": "passed" if not failures else "blocked",
        "exact_gate": "passed" if not failures and not pending else "blocked",
        "gate": "passed" if not failures else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument(
        "--contract-root", type=Path, default=ROOT / "models/contracts"
    )
    parser.add_argument(
        "--runtime-probe",
        type=Path,
        default=ROOT / "data/diagnostics/openvino-ir-runtime-probe.json",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/model-contract-audit.json")
    args = parser.parse_args()
    report = run(
        args.registry.resolve(),
        args.contract_root.resolve(),
        args.runtime_probe.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "count",
                    "valid",
                    "model_specific_validated",
                    "model_specific_pending",
                    "runtime_ready",
                    "presence_gate",
                    "exact_gate",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["exact_gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
