"""Inspect local model I/O contracts without downloading or mutating weights."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.model_contract import ModelContract, ModelContractCatalog, TensorContract
from ai.model.registry import ModelRecord, ModelRegistry

VALIDATED = {"validated", "model-specific-validated", "parity-validated"}


def _tensor_contract(name: str, shape: tuple[int | str, ...], dtype: str) -> TensorContract:
    return TensorContract(name=name, shape=shape, dtype=dtype)


def _inspect_onnx(record: ModelRecord) -> ModelContract:
    from ai.model.onnx_backend import OnnxRuntimeBackend

    backend = OnnxRuntimeBackend()
    try:
        backend.load(record.path)
        inputs = tuple(
            _tensor_contract(spec.name, spec.shape, spec.dtype)
            for spec in backend.input_specs()
        )
        outputs = tuple(
            _tensor_contract(spec.name, spec.shape, spec.dtype)
            for spec in backend.output_specs()
        )
    finally:
        backend.close()
    return ModelContract(
        model_id=record.id,
        format=record.format,
        inputs=inputs,
        outputs=outputs,
        postprocess={
            "status": "runtime-signature-only",
            "source": "model registry and ONNX Runtime graph metadata",
        },
        signature_status="validated",
        runtime_status=record.status,
        source_backend_parity=(
            "pending" if record.logical_id != record.id else "not-applicable"
        ),
        version="contract-v2",
    )


def _registry_contract(record: ModelRecord) -> ModelContract:
    """Inspect an IR XML signature without importing OpenVINO.

    Importing an incompatible native OpenVINO extension can terminate the host
    process on some machines. The graph signature is useful evidence, but the
    contract remains pending until a compatible runner performs real inference.
    """

    root = ET.parse(record.path).getroot()
    layers = root.find("layers")
    if layers is None:
        raise ValueError(f"IR graph has no layers: {record.path}")

    def tensor(layer: ET.Element, port_kind: str) -> TensorContract:
        port = layer.find(f"{port_kind}/port")
        if port is None:
            raise ValueError(f"IR {layer.get('name')} has no {port_kind} port")
        dimensions = tuple(int(value.text or "0") for value in port.findall("dim"))
        data = layer.find("data")
        dtype = (
            (data.get("element_type") if data is not None else None)
            or port.get("precision")
            or "unknown"
        )
        return TensorContract(
            name=str(layer.get("name") or layer.get("id") or port_kind),
            shape=dimensions,
            dtype=str(dtype).lower(),
        )

    inputs = tuple(
        tensor(layer, "output") for layer in layers if layer.get("type") == "Parameter"
    )
    outputs = tuple(tensor(layer, "input") for layer in layers if layer.get("type") == "Result")

    return ModelContract(
        model_id=record.id,
        format=record.format,
        inputs=inputs,
        outputs=outputs,
        normalization={"status": "pending-model-specific"},
        postprocess={
            "status": "signature-inspected-runtime-pending",
            "source": "OpenVINO IR XML",
            "path": str(record.path),
            "weights_path": str(record.weights_path) if record.weights_path else None,
        },
        signature_status="validated",
        runtime_status="signature-inspected-runtime-pending",
        source_backend_parity="pending",
        version="contract-v2",
    )


def inspect_record(record: ModelRecord) -> ModelContract:
    if record.format in {"onnx", "ort"}:
        return _inspect_onnx(record)
    if record.format == "openvino_ir":
        return _registry_contract(record)
    return ModelContract(model_id=record.id, format=record.format)


def run(registry_path: Path, output_root: Path, model_id: str | None = None) -> dict[str, Any]:
    registry = ModelRegistry.from_yaml(registry_path)
    records = [registry.require(model_id)] if model_id else list(registry.records.values())
    catalog = ModelContractCatalog(output_root)
    inspected: list[dict[str, Any]] = []
    for record in records:
        try:
            contract = inspect_record(record)
            existing = catalog.get(record.id)
            existing_is_validated = bool(
                existing
                and existing.normalization.get("status") in VALIDATED
                and existing.postprocess.get("status") in VALIDATED
            )
            if existing:
                contract = replace(
                    contract,
                    normalization=existing.normalization or contract.normalization,
                    postprocess=existing.postprocess or contract.postprocess,
                    source_backend_parity=existing.source_backend_parity,
                    luminar_effect_parity=existing.luminar_effect_parity,
                )
            path = catalog.put(contract)
            inspected.append(
                {
                    "model_id": record.id,
                    "status": (
                        "model-specific-validated"
                        if existing_is_validated
                        else contract.postprocess.get("status", "ready")
                    ),
                    "contract": str(path),
                }
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            inspected.append(
                {
                    "model_id": record.id,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    signature_ready = sum(
        item["status"] in {"ready", "runtime-signature-only", "model-specific-validated"}
        for item in inspected
    )
    pending = sum(
        item["status"] in {"pending-native-probe", "signature-inspected-runtime-pending"}
        for item in inspected
    )
    return {
        "version": "0.1.0",
        "registry": str(registry_path),
        "contract_root": str(output_root),
        "count": len(inspected),
        "ready": signature_ready,
        "pending": pending,
        "signature_ready": signature_ready,
        "failed": sum(item["status"] == "failed" for item in inspected),
        "models": inspected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument(
        "--output-root", type=Path, default=ROOT / "models/contracts"
    )
    parser.add_argument("--model-id")
    parser.add_argument("--report", type=Path, default=ROOT / "data/diagnostics/model-probe-report.json")
    args = parser.parse_args()
    report = run(args.registry.resolve(), args.output_root.resolve(), args.model_id)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "ready", "pending", "failed")}, ensure_ascii=False))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
