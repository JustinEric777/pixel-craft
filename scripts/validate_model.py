"""Run an ONNX Runtime signature and random-input smoke test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.onnx_backend import OnnxRuntimeBackend


def shape_for(value: Any) -> tuple[int, ...]:
    shape = []
    for index, dimension in enumerate(value.shape):
        if isinstance(dimension, int) and dimension > 0:
            shape.append(dimension)
        elif index == 0:
            shape.append(1)
        elif len(value.shape) == 4 and index == 1:
            shape.append(3)
        else:
            shape.append(224)
    return tuple(shape)


def dtype_for(type_name: str) -> np.dtype:
    return {
        "tensor(float)": np.float32,
        "tensor(float16)": np.float16,
        "tensor(double)": np.float64,
        "tensor(int64)": np.int64,
        "tensor(int32)": np.int32,
        "tensor(uint8)": np.uint8,
    }.get(type_name, np.float32)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    backend = OnnxRuntimeBackend()
    backend.load(args.model)
    checker: dict[str, Any] = {"status": "skipped"}
    try:
        import onnx

        model = onnx.load(str(args.model), load_external_data=False)
        onnx.checker.check_model(model)
        checker = {"status": "passed", "ir_version": model.ir_version}
    except Exception as exc:  # noqa: BLE001 - validation result is reported
        checker = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    session = backend.session
    inputs = {
        value.name: np.zeros(shape_for(value), dtype=dtype_for(value.type))
        for value in session.get_inputs()
    }
    outputs = backend.run(inputs)
    result = {
        "model": str(args.model),
        "status": "validated",
        "onnx_checker": checker,
        "health": backend.health(),
        "input_shapes": {name: list(value.shape) for name, value in inputs.items()},
        "output_shapes": {name: list(value.shape) for name, value in outputs.items()},
        "output_finite": {name: bool(np.isfinite(value).all()) for name, value in outputs.items()},
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
