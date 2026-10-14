"""Inspect ONNX/ORT/OpenVINO artifacts without loading private application code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def onnx_signature(path: Path) -> dict[str, Any]:
    try:
        import onnx

        model = onnx.load(str(path), load_external_data=False)
        graph = model.graph
        return {
            "ir_version": model.ir_version,
            "opset_import": [
                {"domain": x.domain, "version": x.version} for x in model.opset_import
            ],
            "inputs": [value_info_to_dict(value) for value in graph.input],
            "outputs": [value_info_to_dict(value) for value in graph.output],
            "node_count": len(graph.node),
            "op_types": sorted({node.op_type for node in graph.node}),
        }
    except Exception as exc:  # noqa: BLE001 - report inspection failures as data
        return {"inspection_error": f"{type(exc).__name__}: {exc}"}


def value_info_to_dict(value: Any) -> dict[str, Any]:
    tensor = value.type.tensor_type
    shape: list[int | str | None] = []
    for dimension in tensor.shape.dim:
        if dimension.HasField("dim_value"):
            shape.append(dimension.dim_value)
        elif dimension.HasField("dim_param"):
            shape.append(dimension.dim_param)
        else:
            shape.append(None)
    return {"name": value.name, "dtype": tensor.elem_type, "shape": shape}


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".onnx":
        return "onnx"
    if suffix == ".ort":
        return "ort"
    if suffix == ".xml" and path.with_suffix(".bin").exists():
        return "openvino_ir"
    if suffix == ".bin" and path.with_suffix(".xml").exists():
        return "openvino_ir_weights"
    return "unknown"


def inspect_file(path: Path, include_hash: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": path.name,
        "path": str(path),
        "format": classify(path),
        "size_bytes": path.stat().st_size,
    }
    if include_hash:
        record["sha256"] = sha256(path)
    if record["format"] == "onnx":
        record["signature"] = onnx_signature(path)
    elif record["format"] == "openvino_ir":
        record["weights"] = str(path.with_suffix(".bin"))
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="directory containing model files")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--hash", action="store_true", dest="include_hash")
    args = parser.parse_args()
    files = sorted(
        path
        for path in args.root.iterdir()
        if path.is_file() and path.suffix.lower() in {".onnx", ".ort", ".xml", ".bin"}
    )
    records = [inspect_file(path, args.include_hash) for path in files]
    result = {
        "root": str(args.root),
        "model_directory": str(args.root),
        "counts": {
            "onnx": sum(x["format"] == "onnx" for x in records),
            "ort": sum(x["format"] == "ort" for x in records),
            "openvino_ir": sum(x["format"] == "openvino_ir" for x in records),
            "openvino_ir_weights": sum(x["format"] == "openvino_ir_weights" for x in records),
            "other": sum(x["format"] == "unknown" for x in records),
        },
        "records": records,
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2) + os.linesep
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
