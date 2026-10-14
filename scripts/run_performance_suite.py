"""Measure cold/warm local analysis latency on explicit validation inputs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.pipeline.factory import build_model_service
from ai.pipeline.model_service import OnnxModelService
from configs import load_config

DEFAULT_MODELS = [
    "face_detector_retinaface",
    "salient_object_improve_exp19_it150k",
    "MulticlassSegmentationV2",
]


def _run_once(service: OnnxModelService, image: Image.Image, models: list[str]) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    result = service.analyze(image, models)
    return round((time.perf_counter() - started) * 1000.0, 2), result


def run(image_path: Path, model_root: Path, models: list[str]) -> dict[str, Any]:
    service = build_model_service(load_config(ROOT), model_root=model_root)
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        cold_ms, cold_result = _run_once(service, image, models)
        warm_ms, warm_result = _run_once(service, image, models)
    return {
        "version": "0.1.0",
        "generated_by": "scripts/run_performance_suite.py",
        "image": str(image_path),
        "image_size": [image.width, image.height],
        "models": models,
        "cold_ms": cold_ms,
        "warm_ms": warm_ms,
        "cache": service.health()["cache"],
        "cold_status": {key: value.get("status") for key, value in cold_result.items()},
        "warm_status": {key: value.get("status") for key, value in warm_result.items()},
        "gate": "passed" if all(value.get("status") != "failed" for value in warm_result.values()) else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, default=ROOT / "models")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/performance-report.json")
    args = parser.parse_args()
    report = run(
        args.image.resolve(),
        args.model_root.resolve(),
        [item.strip() for item in args.models.split(",") if item.strip()],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("cold_ms", "warm_ms", "gate")}, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
