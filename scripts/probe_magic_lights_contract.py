"""Probe the frozen Magic Lights ONNX contract on positive and negative fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.onnx.light_detection.magic_lights_exp37_dataset123_1024 import (
    MagicLightsExp37OnnxInference,
)
from ai.model.registry import ModelRegistry
from configs.reference import load_reference_catalog

MODEL_ID = "magic_lights_exp37_dataset123_1024_onnx"
DEFAULT_POSITIVE = (
    ROOT
    / "test_data/parity/inputs/summer-outdoor"
    / "a_7641587156716241427/004_67f337016c.jpg"
)
DEFAULT_NEGATIVE = (
    ROOT
    / "test_data/parity/inputs/summer-outdoor"
    / "a_7637493472862011940/008_e45cd3c34a.jpg"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_result(
    wrapper: MagicLightsExp37OnnxInference,
    path: Path,
    *,
    expected: str,
) -> dict[str, Any]:
    with Image.open(path) as source:
        rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
    bgr = np.ascontiguousarray(rgb[..., ::-1])
    started = perf_counter()
    inputs = wrapper.preprocess(bgr)
    outputs = wrapper.predict(inputs)
    result = wrapper.postprocess(outputs)
    duration_ms = (perf_counter() - started) * 1000.0
    raw = {
        name: {
            "shape": list(np.asarray(value).shape),
            "dtype": str(np.asarray(value).dtype),
            "finite": bool(np.isfinite(value).all()),
            "minimum": float(np.min(value)),
            "maximum": float(np.max(value)),
        }
        for name, value in outputs.items()
    }
    scores = np.asarray(result["scores"], dtype=np.float32)
    detected = int(scores.size)
    expectation_passed = detected > 0 if expected == "positive" else detected == 0
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "expected": expected,
        "input_shape": list(rgb.shape),
        "duration_ms": round(duration_ms, 3),
        "raw_outputs": raw,
        "detection_count": detected,
        "score_minimum": float(scores.min()) if detected else None,
        "score_maximum": float(scores.max()) if detected else None,
        "boxes": np.asarray(result["boxes"], dtype=np.float32).round(8).tolist(),
        "expectation_passed": expectation_passed,
    }


def run(registry_path: Path, positive: Path, negative: Path) -> dict[str, Any]:
    registry = ModelRegistry.from_yaml(registry_path)
    record = registry.require(MODEL_ID)
    for path in (record.path, positive, negative):
        if not path.is_file():
            raise FileNotFoundError(path)
    wrapper = MagicLightsExp37OnnxInference(
        record.id,
        record.path,
        device=record.device,
    )
    try:
        wrapper.load_model()
        fixtures = [
            _fixture_result(wrapper, positive, expected="positive"),
            _fixture_result(wrapper, negative, expected="negative"),
        ]
    finally:
        wrapper.unload_model()
    output_shapes = {
        tuple(item["shape"])
        for fixture in fixtures
        for item in fixture["raw_outputs"].values()
    }
    expected_shapes = {
        (1, 3, 32, 32, 6),
        (1, 3, 64, 64, 6),
        (1, 3, 128, 128, 6),
    }
    all_finite = all(
        item["finite"]
        for fixture in fixtures
        for item in fixture["raw_outputs"].values()
    )
    passed = (
        all(item["expectation_passed"] for item in fixtures)
        and all_finite
        and output_shapes == expected_shapes
    )
    return {
        "version": "magic-lights-contract-probe-v1",
        "model_id": record.id,
        "logical_model_id": record.logical_id,
        "artifact": {"path": str(record.path), "sha256": _sha256(record.path)},
        "preprocess": {
            "color_order": "RGB",
            "layout": "NCHW",
            "input_size": [1024, 1024],
            "scale": 1.0 / 255.0,
        },
        "postprocess": {
            "family": "YOLOv5 three-scale decode",
            "confidence_threshold": 0.25,
            "nms_iou_threshold": 0.45,
            "max_detections": 256,
        },
        "fixtures": fixtures,
        "raw_output_shapes_passed": output_shapes == expected_shapes,
        "finite_outputs_passed": all_finite,
        "gate": "passed" if passed else "blocked",
        "scope": (
            "model-specific preprocessing, forward output, decode and NMS only; "
            "Luminar rendering parity remains a separate gate"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument("--positive", type=Path, default=DEFAULT_POSITIVE)
    parser.add_argument("--negative", type=Path, default=DEFAULT_NEGATIVE)
    active = load_reference_catalog(project_root=ROOT).resolve()
    parser.add_argument(
        "--output",
        type=Path,
        default=active.diagnostics_root / "magic-lights-contract-probe.json",
    )
    args = parser.parse_args()
    report = run(
        args.registry.resolve(), args.positive.resolve(), args.negative.resolve()
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "model_id": report["model_id"],
                "gate": report["gate"],
                "detections": [
                    fixture["detection_count"] for fixture in report["fixtures"]
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
