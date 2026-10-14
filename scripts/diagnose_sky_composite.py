"""Save Sky AI masks, aligned texture and composite diagnostics for one image."""

from __future__ import annotations

import argparse
import json
import sys
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
from image_ops.effects.sky_compositor import (
    _fit_texture,
    _prepare_mask,
    _protect_foreground,
)


def _save_mask(values: np.ndarray, path: Path) -> None:
    image = Image.fromarray((np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8), "L")
    image.save(path)


def run(source_path: Path, sky_path: Path, output_root: Path, model_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as opened:
        source = opened.convert("RGB").copy()
    with Image.open(sky_path) as opened:
        texture = opened.convert("RGB").copy()
    service = build_model_service(load_config(ROOT), model_root=model_root)
    parameters: dict[str, Any] = {
        "amount": 0.4,
        "_sky_texture": texture,
        "sky_scale": 1.0,
        "sky_global": 1.0,
        "fix_gaps": 0.0,
        "edge_refinement": 6.0,
        "horizon_offset": 0.58,
        "horizon_blending": 0.5,
        "foreground_relight": 0.0,
        "relight_saturation": 1.0,
        "relight_human": 0.25,
        "reflection_amount": 0.0,
        "reflection_blur": 4.0,
        "sky_grain": 0.05,
        "atmospheric_haze": 0.05,
    }
    sky_mask, sky_info = service._sky_mask(source)
    parameters["_detected_horizon"] = sky_info["horizon_fraction"]
    prepared_mask = _prepare_mask(
        sky_mask,
        source.size,
        parameters,
    )
    texture_layer = _fit_texture(source, texture, parameters)
    reflection = service._sky_reflection_mask(source)
    foreground = service._human_foreground_mask(source)
    _save_mask(sky_mask, output_root / "sky-mask-model.png")
    prepared_mask.save(output_root / "sky-mask-prepared.png")
    texture_layer.save(output_root / "texture-aligned.png")
    if reflection is not None:
        _save_mask(reflection, output_root / "reflection-mask-model.png")
        _prepare_mask(reflection, source.size, parameters).save(
            output_root / "reflection-mask-prepared.png"
        )
    if foreground is not None:
        _save_mask(foreground, output_root / "human-foreground-mask.png")
        parameters["_foreground_mask"] = foreground
        _protect_foreground(prepared_mask, foreground, source.size).save(
            output_root / "sky-mask-effective.png"
        )
    context = service.execution(["sky_replace"], "sky-diagnostic")
    trace = context.__enter__()
    try:
        result = service.apply_image_effect(source, "sky_replace", parameters)
    finally:
        context.__exit__(None, None, None)
    if result is None:
        raise RuntimeError("Sky edit returned no image")
    result.save(output_root / "final-output.png")
    alpha = np.asarray(prepared_mask, dtype=np.float32) / 255.0
    source_array = np.asarray(source, dtype=np.float32)
    result_array = np.asarray(result, dtype=np.float32)
    delta = np.abs(result_array - source_array)
    height = result_array.shape[0]
    band = result_array[round(height * 0.38) : max(round(height * 0.72), 1)]
    vertical = float(np.abs(np.diff(band, axis=0)).mean()) if len(band) > 1 else 0.0
    horizontal = float(np.abs(np.diff(band, axis=1)).mean()) if band.shape[1] > 1 else 0.0
    report = {
        "version": "0.1.0",
        "generated_by": "scripts/diagnose_sky_composite.py",
        "source": str(source_path),
        "sky_asset": str(sky_path),
        "output_root": str(output_root),
        "size": list(source.size),
        "sky_info": sky_info,
        "sky_coverage": round(float(np.mean(alpha > 0.25)), 6),
        "prepared_alpha_min": round(float(alpha.min()), 6),
        "prepared_alpha_max": round(float(alpha.max()), 6),
        "mean_absolute_delta": round(float(delta.mean()), 6),
        "changed_pixel_ratio": round(float(np.mean(np.max(delta, axis=2) > 2.0)), 6),
        "transition_vertical_gradient": round(vertical, 6),
        "transition_horizontal_gradient": round(horizontal, 6),
        "vertical_to_horizontal_gradient_ratio": round(vertical / max(horizontal, 1e-6), 6),
        "trace": trace,
        "artifacts": [str(path) for path in sorted(output_root.iterdir())],
    }
    (output_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--sky", type=Path, default=ROOT / "assets/materials/SkyTextures/Blue Sky/Blue Sky 1.jpg"
    )
    parser.add_argument("--model-root", type=Path, default=ROOT / "models")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    output_root = (
        args.output_root or profile.diagnostics_root / "sky-diagnostics/current"
    ).resolve()
    report = run(
        args.source.resolve(),
        args.sky.resolve(),
        output_root,
        args.model_root.resolve(),
    )
    print(json.dumps({key: report[key] for key in ("size", "sky_coverage", "changed_pixel_ratio", "vertical_to_horizontal_gradient_ratio")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
