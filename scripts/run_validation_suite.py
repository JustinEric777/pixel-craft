"""Run local model analysis on a manifest of validation images."""

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
from configs import load_config

DEFAULT_MODELS = [
    "face_detector_retinaface",
    "salient_object_improve_exp19_it150k",
    "MulticlassSegmentationV2",
    "SemanticSearchImage",
]


def run(
    manifest_path: Path,
    model_root: Path,
    requested_models: list[str],
    limit: int | None = None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    service = build_model_service(load_config(ROOT), model_root=model_root)
    records = manifest.get("records", [])[:limit]
    results: list[dict[str, Any]] = []
    for record in records:
        started = time.perf_counter()
        item: dict[str, Any] = {"id": record["id"], "path": record["path"]}
        try:
            with Image.open(record["path"]) as image:
                analysis = service.analyze(image.convert("RGB"), requested_models)
            item["analysis"] = {
                key: {
                    "status": value.get("status"),
                    "model": value.get("model"),
                    "quality": value.get("quality"),
                    "shape": value.get("shape"),
                    "error": value.get("error"),
                    "reason": value.get("reason"),
                }
                for key, value in analysis.items()
            }
            failed_models = [
                key for key, value in analysis.items() if value.get("status") == "failed"
            ]
            item["status"] = "failed" if failed_models else "ready"
            if failed_models:
                item["error"] = "model analysis failed: " + ", ".join(failed_models)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            item["status"] = "failed"
            item["error"] = f"{type(exc).__name__}: {exc}"
        item["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
        results.append(item)
    return {
        "version": "0.1.0",
        "generated_by": "scripts/run_validation_suite.py",
        "manifest": str(manifest_path),
        "models": requested_models,
        "count": len(results),
        "ready": sum(item["status"] == "ready" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "test_data/parity/validation-samples.json"
    )
    parser.add_argument("--model-root", type=Path, default=ROOT / "models")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/diagnostics/validation-report.json"
    )
    args = parser.parse_args()
    report = run(
        args.manifest.resolve(),
        args.model_root.resolve(),
        [item.strip() for item in args.models.split(",") if item.strip()],
        args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "ready", "failed")}, ensure_ascii=False))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
