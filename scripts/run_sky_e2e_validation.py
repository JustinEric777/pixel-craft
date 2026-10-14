"""Run the complete local Sky AI edit graph on every validation image."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.pipeline.factory import build_model_service
from configs import load_config
from configs.reference import load_reference_catalog

EXPECTED_MODELS = {
    "improved_sky_segmentator_v462_i8",
    "horizon_align_i8",
    "skyinwater_v16_i8",
}


def _pixel_hash(image: Image.Image) -> str:
    return hashlib.sha256(np.asarray(image.convert("RGB"), dtype=np.uint8).tobytes()).hexdigest()


def _diagnostics(source: Image.Image, result: Image.Image) -> dict[str, float]:
    before = np.asarray(source.convert("RGB"), dtype=np.float32)
    after = np.asarray(result.convert("RGB"), dtype=np.float32)
    delta = np.abs(after - before)
    height = after.shape[0]
    band = after[round(height * 0.38) : max(round(height * 0.72), 1)]
    vertical_gradient = float(np.abs(np.diff(band, axis=0)).mean()) if len(band) > 1 else 0.0
    horizontal_gradient = float(np.abs(np.diff(band, axis=1)).mean()) if band.shape[1] > 1 else 0.0
    return {
        "mean_absolute_delta": round(float(delta.mean()), 6),
        "changed_pixel_ratio": round(float(np.mean(np.max(delta, axis=2) > 2.0)), 6),
        "transition_vertical_gradient": round(vertical_gradient, 6),
        "transition_horizontal_gradient": round(horizontal_gradient, 6),
        "vertical_to_horizontal_gradient_ratio": round(
            vertical_gradient / max(horizontal_gradient, 1e-6), 6
        ),
    }


def run(
    manifest_path: Path,
    model_root: Path,
    sky_path: Path,
    *,
    reference_id: str,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    service = build_model_service(load_config(ROOT), model_root=model_root)
    expected_models = {service._resolve_model_id(model_id) for model_id in EXPECTED_MODELS}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with Image.open(sky_path) as texture_source:
        texture = texture_source.convert("RGB").copy()
    records = []
    source_records = manifest.get("records", [])
    for index, source_record in enumerate(source_records, start=1):
        if progress_path is not None:
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            progress_path.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "reference_id": reference_id,
                        "current": index,
                        "total": len(source_records),
                        "record_id": source_record.get("id"),
                        "status": "running",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        started = time.perf_counter()
        try:
            with Image.open(source_record["path"]) as opened:
                source = opened.convert("RGB")
            sky_mask, sky_info = service._sky_mask(source)
            sky_coverage = float(np.mean(np.asarray(sky_mask) > 0.25))
            parameters = {
                "amount": 1.0,
                "_sky_texture": texture,
                "sky_scale": 1.0,
                "sky_global": 1.0,
                "fix_gaps": 0.0,
                "edge_refinement": 2.0,
                "foreground_relight": 0.2,
                "relight_saturation": 1.0,
                "relight_human": 0.25,
                "reflection_amount": 0.2,
                "reflection_blur": 4.0,
                "sky_grain": 0.05,
                "atmospheric_haze": 0.05,
            }
            with service.execution(["sky_replace"], "validation") as trace:
                result = service.apply_image_effect(source, "sky_replace", parameters)
            if result is None:
                raise RuntimeError("Sky edit returned no image")
            invoked = {item["id"] for item in trace["models"] if item.get("status") == "ready"}
            missing = sorted(expected_models - invoked)
            diagnostics = _diagnostics(source, result)
            failures = []
            if missing:
                failures.append("models-not-ready:" + ",".join(missing))
            if result.size != source.size:
                failures.append("size-changed")
            if diagnostics["changed_pixel_ratio"] <= 0.01 and sky_coverage > 0.01:
                failures.append("effect-not-visible")
            records.append(
                {
                    "id": source_record["id"],
                    "filename": source_record["filename"],
                    "status": "failed" if failures else "ready",
                    "failures": failures,
                    "source_sha256": source_record["sha256"],
                    "result_pixel_sha256": _pixel_hash(result),
                    "size": list(result.size),
                    "diagnostics": diagnostics,
                    "scene": {
                        "classification": (
                            "replaceable-sky" if sky_coverage > 0.01 else "no-detected-sky"
                        ),
                        "sky_coverage": round(sky_coverage, 6),
                        "mask_model": sky_info["model"],
                        "mask_quality": sky_info["quality"],
                    },
                    "trace": {
                        "status": trace["status"],
                        "duration_ms": trace["duration_ms"],
                        "models": trace["models"],
                    },
                    "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
                }
            )
        except Exception as exc:  # noqa: BLE001 - retain per-image validation evidence
            records.append(
                {
                    "id": source_record["id"],
                    "filename": source_record["filename"],
                    "status": "failed",
                    "failures": [f"{type(exc).__name__}: {exc}"],
                    "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
                }
            )
        if progress_path is not None:
            progress_path.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "reference_id": reference_id,
                        "current": index,
                        "total": len(source_records),
                        "record_id": source_record.get("id"),
                        "status": "completed",
                        "record_status": records[-1]["status"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    return {
        "version": "0.1.0",
        "generated_by": "scripts/run_sky_e2e_validation.py",
        "reference_build": reference_id,
        "manifest": str(manifest_path),
        "sky_asset": str(sky_path),
        "count": len(records),
        "ready": sum(item["status"] == "ready" for item in records),
        "failed": sum(item["status"] == "failed" for item in records),
        "luminar_blackbox_parity": "pending-reference-outputs",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "test_data/parity/validation-samples.json"
    )
    parser.add_argument("--model-root", type=Path, default=ROOT / "models")
    parser.add_argument(
        "--sky",
        type=Path,
        default=ROOT / "assets/materials/SkyTextures/Blue Sky/Blue Sky 1.jpg",
    )
    parser.add_argument(
        "--output", type=Path
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    output = (
        args.output or profile.diagnostics_root / "validation-sky-e2e-report.json"
    ).resolve()
    report = run(
        args.manifest.resolve(),
        args.model_root.resolve(),
        args.sky.resolve(),
        reference_id=profile.id,
        progress_path=output.with_suffix(".progress.json"),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "ready", "failed")}))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
