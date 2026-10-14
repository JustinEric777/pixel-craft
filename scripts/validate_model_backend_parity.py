"""Validate model-specific ONNX and OpenVINO fallback behavior on identical fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.factory import create_inference
from ai.model.registry import ModelRecord, ModelRegistry

ABSOLUTE_TOLERANCE = 1e-4
RELATIVE_TOLERANCE = 1e-3
FIXTURE_NAMES = ("black", "white", "gradient")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture(name: str, *, height: int = 769, width: int = 1031) -> np.ndarray:
    if name == "black":
        return np.zeros((height, width, 3), dtype=np.uint8)
    if name == "white":
        return np.full((height, width, 3), 255, dtype=np.uint8)
    if name != "gradient":
        raise ValueError(f"unknown fixture: {name}")
    yy, xx = np.indices((height, width), dtype=np.uint32)
    return np.stack(
        (
            (xx * 17 + yy * 3) % 256,
            (xx * 5 + yy * 11 + 29) % 256,
            (xx * 7 + yy * 13 + 71) % 256,
        ),
        axis=-1,
    ).astype(np.uint8)


def _sha256_array(value: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(json.dumps(list(value.shape)).encode("ascii"))
    digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def _tensor_metrics(primary: Any, fallback: Any) -> dict[str, Any]:
    left = np.asarray(primary)
    right = np.asarray(fallback)
    result: dict[str, Any] = {
        "primary_shape": list(left.shape),
        "fallback_shape": list(right.shape),
        "primary_dtype": str(left.dtype),
        "fallback_dtype": str(right.dtype),
        "primary_finite": bool(np.isfinite(left).all()),
        "fallback_finite": bool(np.isfinite(right).all()),
    }
    if left.shape != right.shape:
        return {**result, "status": "shape-mismatch"}
    if not result["primary_finite"] or not result["fallback_finite"]:
        return {**result, "status": "non-finite"}
    if np.issubdtype(left.dtype, np.integer) or np.issubdtype(left.dtype, np.bool_):
        equal = bool(np.array_equal(left, right))
        return {**result, "equal": equal, "status": "passed" if equal else "failed"}
    left32 = left.astype(np.float32, copy=False)
    right32 = right.astype(np.float32, copy=False)
    difference = np.abs(left32 - right32)
    denominator = np.maximum(np.maximum(np.abs(left32), np.abs(right32)), 1e-6)
    close = np.isclose(
        left32,
        right32,
        atol=ABSOLUTE_TOLERANCE,
        rtol=RELATIVE_TOLERANCE,
    )
    return {
        **result,
        "max_absolute_error": float(difference.max(initial=0.0)),
        "mean_absolute_error": float(difference.mean()) if difference.size else 0.0,
        "max_relative_error": float((difference / denominator).max(initial=0.0)),
        "different_element_count": int(np.size(close) - np.count_nonzero(close)),
        "status": "passed" if bool(close.all()) else "failed",
    }


def _compare_sequences(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    primary_items = list(primary.items())
    fallback_items = list(fallback.items())
    tensors = []
    for index in range(max(len(primary_items), len(fallback_items))):
        if index >= len(primary_items) or index >= len(fallback_items):
            tensors.append({"index": index, "status": "count-mismatch"})
            continue
        primary_name, primary_value = primary_items[index]
        fallback_name, fallback_value = fallback_items[index]
        tensors.append(
            {
                "index": index,
                "primary_name": primary_name,
                "fallback_name": fallback_name,
                **_tensor_metrics(primary_value, fallback_value),
            }
        )
    passed = len(primary_items) == len(fallback_items) and all(
        item["status"] == "passed" for item in tensors
    )
    return {
        "primary_count": len(primary_items),
        "fallback_count": len(fallback_items),
        "tensors": tensors,
        "status": "passed" if passed else "failed",
    }


def _compare_semantics(primary: Any, fallback: Any) -> dict[str, Any]:
    if not isinstance(primary, dict) or not isinstance(fallback, dict):
        return {"status": "failed", "reason": "postprocess-result-is-not-a-dict"}
    if set(primary) != set(fallback):
        return {
            "status": "failed",
            "reason": "key-mismatch",
            "primary_keys": sorted(primary),
            "fallback_keys": sorted(fallback),
        }
    tensors = [
        {"name": name, **_tensor_metrics(primary[name], fallback[name])}
        for name in sorted(primary)
    ]
    return {
        "keys": sorted(primary),
        "tensors": tensors,
        "status": (
            "passed" if all(item["status"] == "passed" for item in tensors) else "failed"
        ),
    }


def _pairs(
    registry: ModelRegistry, source_map: dict[str, Any]
) -> list[tuple[ModelRecord, ModelRecord]]:
    selected = {str(key): str(value) for key, value in source_map["selected_variants"].items()}
    scope = {str(item["id"]): str(item["product_scope_status"]) for item in source_map["models"]}
    pairs = []
    for fallback in registry.records.values():
        logical_id = fallback.logical_id or fallback.id
        if fallback.format != "openvino_ir":
            continue
        if not scope.get(fallback.id, "").startswith("required-"):
            continue
        primary_id = selected.get(logical_id)
        if primary_id is None or primary_id == fallback.id:
            continue
        primary = registry.require(primary_id)
        if primary.format not in {"onnx", "ort"}:
            raise ValueError(
                f"required fallback {fallback.id} does not have an ONNX primary: {primary.id}"
            )
        pairs.append((primary, fallback))
    return pairs


def validate_pair(
    primary: ModelRecord,
    fallback: ModelRecord,
    fixture_names: tuple[str, ...],
) -> dict[str, Any]:
    primary_wrapper = create_inference(primary, device="cpu")
    fallback_wrapper = create_inference(fallback, device="CPU")
    fixtures = []
    try:
        primary_wrapper.load_model()
        fallback_wrapper.load_model()
        for fixture_name in fixture_names:
            image = _fixture(fixture_name)
            primary_inputs = primary_wrapper.preprocess(image)
            fallback_inputs = fallback_wrapper.preprocess(image)
            input_comparison = _compare_sequences(primary_inputs, fallback_inputs)
            primary_outputs = primary_wrapper.predict(primary_inputs)
            fallback_outputs = fallback_wrapper.predict(fallback_inputs)
            raw_comparison = _compare_sequences(primary_outputs, fallback_outputs)
            semantic_comparison = _compare_semantics(
                primary_wrapper.postprocess(primary_outputs),
                fallback_wrapper.postprocess(fallback_outputs),
            )
            fixtures.append(
                {
                    "fixture": fixture_name,
                    "fixture_sha256": _sha256_array(image),
                    "input": input_comparison,
                    "raw_output": raw_comparison,
                    "semantic_output": semantic_comparison,
                    "status": (
                        "passed"
                        if all(
                            item["status"] == "passed"
                            for item in (
                                input_comparison,
                                raw_comparison,
                                semantic_comparison,
                            )
                        )
                        else "failed"
                    ),
                }
            )
    finally:
        primary_wrapper.unload_model()
        fallback_wrapper.unload_model()
    return {
        "logical_id": primary.logical_id or primary.id,
        "primary_model_id": primary.id,
        "fallback_model_id": fallback.id,
        "fixtures": fixtures,
        "status": "passed" if all(item["status"] == "passed" for item in fixtures) else "failed",
    }


def run(
    registry_path: Path,
    source_map_path: Path,
    *,
    model_ids: set[str] | None = None,
    fixture_names: tuple[str, ...] = FIXTURE_NAMES,
) -> dict[str, Any]:
    registry = ModelRegistry.from_yaml(registry_path)
    pairs = _pairs(registry, _load(source_map_path))
    if model_ids:
        pairs = [pair for pair in pairs if pair[1].id in model_ids]
    results = []
    for primary, fallback in pairs:
        try:
            results.append(validate_pair(primary, fallback, fixture_names))
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            results.append(
                {
                    "logical_id": primary.logical_id or primary.id,
                    "primary_model_id": primary.id,
                    "fallback_model_id": fallback.id,
                    "fixtures": [],
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "version": "1.0",
        "generated_by": "scripts/validate_model_backend_parity.py",
        "registry": str(registry_path),
        "source_map": str(source_map_path),
        "thresholds": {
            "absolute_tolerance": ABSOLUTE_TOLERANCE,
            "relative_tolerance": RELATIVE_TOLERANCE,
            "fixtures": list(fixture_names),
        },
        "pair_count": len(results),
        "passed": sum(item["status"] == "passed" for item in results),
        "failed": sum(item["status"] != "passed" for item in results),
        "gate": (
            "passed"
            if results and all(item["status"] == "passed" for item in results)
            else "blocked"
        ),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--model-id", action="append")
    parser.add_argument("--fixture", action="append", choices=FIXTURE_NAMES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-exact", action="store_true")
    args = parser.parse_args()
    report = run(
        args.registry.resolve(),
        args.source_map.resolve(),
        model_ids=set(args.model_id or ()) or None,
        fixture_names=tuple(args.fixture or FIXTURE_NAMES),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: report[key] for key in ("pair_count", "passed", "failed", "gate")},
            ensure_ascii=False,
        )
    )
    return 0 if not args.require_exact or report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
