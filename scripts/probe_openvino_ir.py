"""Compile and run every registered OpenVINO IR with deterministic synthetic inputs.

This is a runtime smoke probe only. A successful record proves that the XML/BIN
pair can compile and execute on the current device; it does not prove Luminar
preprocess, postprocess, or pixel parity.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.registry import ModelRegistry


def _shape(input_port: Any) -> tuple[int, ...]:
    partial = input_port.partial_shape
    if partial.rank.is_dynamic:
        rank = 4
    else:
        rank = partial.rank.get_length()
    dimensions: list[int] = []
    for index in range(rank):
        dimension = partial[index]
        if dimension.is_static:
            dimensions.append(max(1, dimension.get_length()))
        elif rank >= 4 and index == 0:
            dimensions.append(1)
        elif rank >= 4 and index == 1:
            dimensions.append(3)
        else:
            dimensions.append(224)
    return tuple(dimensions)


def _dtype(input_port: Any) -> np.dtype[Any]:
    try:
        return np.dtype(input_port.element_type.to_dtype())
    except (AttributeError, TypeError):
        return np.dtype(np.float32)


def _input_value(input_port: Any) -> np.ndarray:
    dtype = _dtype(input_port)
    shape = _shape(input_port)
    if np.issubdtype(dtype, np.integer):
        return np.zeros(shape, dtype=dtype)
    return np.zeros(shape, dtype=dtype)


def _probe_record(core: Any, record: Any, device: str) -> dict[str, Any]:
    xml_path = record.path
    started = time.perf_counter()
    if not xml_path.is_file():
        return {
            "id": record.id,
            "status": "missing",
            "path": str(xml_path),
            "error": "IR XML is missing",
        }
    try:
        model = core.read_model(str(xml_path), str(record.weights_path))
        compiled = core.compile_model(model, device)
        # Compile before materializing inputs or touching binary IPC streams.
        # OpenVINO 2025.4 on macOS arm64 can otherwise fail its first JIT setup.
        inputs = {port.any_name: _input_value(port) for port in model.inputs}
        outputs = compiled(inputs)
        output_records = []
        non_finite_outputs: list[str] = []
        for port in compiled.outputs:
            value = np.asarray(outputs[port])
            finite = (
                bool(np.isfinite(value).all())
                if np.issubdtype(value.dtype, np.number)
                else True
            )
            if not finite:
                non_finite_outputs.append(port.any_name)
            output_records.append(
                {
                    "name": port.any_name,
                    "shape": list(value.shape),
                    "dtype": str(value.dtype),
                    "finite": finite,
                }
            )
        return {
            "id": record.id,
            "status": "failed" if non_finite_outputs else "ready",
            "backend": "openvino",
            "device": device,
            "inputs": [
                {
                    "name": port.any_name,
                    "shape": list(_shape(port)),
                    "dtype": str(_dtype(port)),
                }
                for port in model.inputs
            ],
            "outputs": output_records,
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "preprocess_status": "pending-model-specific",
            "postprocess_status": "pending-model-specific",
            "error": (
                "non-finite outputs: " + ", ".join(non_finite_outputs)
                if non_finite_outputs
                else None
            ),
        }
    except Exception as exc:  # noqa: BLE001 - preserve per-model evidence
        return {
            "id": record.id,
            "status": "failed",
            "backend": "openvino",
            "device": device,
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def run(registry_path: Path, device: str, model_id: str | None = None) -> dict[str, Any]:
    from openvino import Core

    registry = ModelRegistry.from_yaml(registry_path)
    records = [registry.require(model_id)] if model_id else [
        record for record in registry.records.values() if record.format == "openvino_ir"
    ]
    core = Core()
    results = []
    for record in records:
        result = _probe_record(core, record, device)
        if result["status"] == "failed" and record.status == "retired-invalid-source":
            try:
                fallback = registry.resolve(record.logical_id or record.id, allow_openvino=False)
            except KeyError:
                pass
            else:
                result = {
                    **result,
                    "status": "retired",
                    "fallback_model_id": fallback.id,
                }
        results.append(result)
    return {
        "version": "0.1.0",
        "generated_by": "scripts/probe_openvino_ir.py",
        "registry": str(registry_path),
        "device": device,
        "count": len(results),
        "ready": sum(item["status"] == "ready" for item in results),
        "retired": sum(item["status"] == "retired" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "missing": sum(item["status"] == "missing" for item in results),
        "model_specific_contracts": "pending-reference-and-model-specific-prepost",
        "results": results,
    }


def run_isolated(
    registry_path: Path,
    device: str,
    *,
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    """Probe each IR in a fresh process so native JIT state is always released."""
    registry = ModelRegistry.from_yaml(registry_path)
    records = [
        record for record in registry.records.values() if record.format == "openvino_ir"
    ]
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="zpixel-openvino-probe-") as temporary:
        temporary_root = Path(temporary)
        for index, record in enumerate(records):
            output = temporary_root / f"{index:03d}-{record.id}.json"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--registry",
                str(registry_path),
                "--device",
                device,
                "--model-id",
                record.id,
                "--output",
                str(output),
                "--in-process",
            ]
            started = time.perf_counter()
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                if output.is_file():
                    payload = json.loads(output.read_text(encoding="utf-8"))
                    result = payload["results"][0]
                else:
                    message = (completed.stderr or completed.stdout).strip()
                    result = {
                        "id": record.id,
                        "status": "failed",
                        "backend": "openvino",
                        "device": device,
                        "duration_ms": round(
                            (time.perf_counter() - started) * 1000.0, 3
                        ),
                        "error": (
                            f"worker exited {completed.returncode}: {message[-1000:]}"
                        ),
                    }
            except subprocess.TimeoutExpired:
                result = {
                    "id": record.id,
                    "status": "failed",
                    "backend": "openvino",
                    "device": device,
                    "duration_ms": round(
                        (time.perf_counter() - started) * 1000.0, 3
                    ),
                    "error": f"worker timed out after {timeout_seconds:g}s",
                }
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                result = {
                    "id": record.id,
                    "status": "failed",
                    "backend": "openvino",
                    "device": device,
                    "duration_ms": round(
                        (time.perf_counter() - started) * 1000.0, 3
                    ),
                    "error": f"worker result error: {type(exc).__name__}: {exc}",
                }
            results.append(result)
    return {
        "version": "0.2.0",
        "generated_by": "scripts/probe_openvino_ir.py",
        "registry": str(registry_path),
        "device": device,
        "isolation": "one-process-per-model",
        "count": len(results),
        "ready": sum(item["status"] == "ready" for item in results),
        "retired": sum(item["status"] == "retired" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "missing": sum(item["status"] == "missing" for item in results),
        "model_specific_contracts": "pending-reference-and-model-specific-prepost",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument("--device", default="CPU")
    parser.add_argument("--model-id")
    parser.add_argument(
        "--in-process",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/diagnostics/openvino-ir-runtime-probe.json"
    )
    args = parser.parse_args()
    report = (
        run(args.registry.resolve(), args.device, args.model_id)
        if args.model_id or args.in_process
        else run_isolated(
            args.registry.resolve(),
            args.device,
            timeout_seconds=args.timeout_seconds,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: report[key] for key in ("count", "ready", "retired", "failed", "missing")},
            ensure_ascii=False,
        )
    )
    return 0 if not report["failed"] and not report["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
