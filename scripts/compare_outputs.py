"""Compare two raster outputs and report deterministic visual metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _load(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0


def _resize(source: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(np.clip(source * 255.0, 0, 255).astype(np.uint8), "RGB")
    image = image.resize((shape[1], shape[0]), Image.Resampling.BICUBIC)
    return np.asarray(image, dtype=np.float32) / 255.0


def _ssim(reference: np.ndarray, candidate: np.ndarray) -> float:
    # Windowed SSIM is intentionally dependency-free; this is a regression
    # gate, not a replacement for LPIPS in a full evaluation environment.
    ref = reference.mean(axis=2)
    got = candidate.mean(axis=2)
    mu_ref, mu_got = float(ref.mean()), float(got.mean())
    var_ref, var_got = float(ref.var()), float(got.var())
    covariance = float(((ref - mu_ref) * (got - mu_got)).mean())
    c1, c2 = 0.01**2, 0.03**2
    return ((2 * mu_ref * mu_got + c1) * (2 * covariance + c2)) / ((mu_ref**2 + mu_got**2 + c1) * (var_ref + var_got + c2))


def _gradient_strength(image: np.ndarray) -> float:
    horizontal = np.abs(np.diff(image, axis=1)).mean() if image.shape[1] > 1 else 0.0
    vertical = np.abs(np.diff(image, axis=0)).mean() if image.shape[0] > 1 else 0.0
    return float((horizontal + vertical) / 2.0)


def _metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    delta = np.abs(reference - candidate)
    rmse = float(np.sqrt(np.mean(np.square(reference - candidate))))
    return {
        "mae": float(delta.mean()),
        "rmse": rmse,
        "psnr_db": float(20 * np.log10(1.0 / max(rmse, 1e-8))),
        "ssim": float(_ssim(reference, candidate)),
        "changed_pixel_fraction": float((delta.mean(axis=2) > 1.0 / 255.0).mean()),
        "max_delta": float(delta.max()),
        "p95_delta": float(np.quantile(delta, 0.95)),
        "mean_delta_rgb": [float(item) for item in delta.mean(axis=(0, 1))],
        "mean_rgb_reference": [float(item) for item in reference.mean(axis=(0, 1))],
        "mean_rgb_candidate": [float(item) for item in candidate.mean(axis=(0, 1))],
        "gradient_reference": _gradient_strength(reference),
        "gradient_candidate": _gradient_strength(candidate),
    }


def compare(
    reference_path: Path,
    candidate_path: Path,
    region: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    reference = _load(reference_path)
    candidate = _load(candidate_path)
    same_shape = reference.shape == candidate.shape
    aligned = candidate if same_shape else _resize(candidate, reference.shape[:2])
    if region is not None:
        left, top, right, bottom = region
        height, width = reference.shape[:2]
        x0 = max(0, min(width - 1, round(left * width)))
        y0 = max(0, min(height - 1, round(top * height)))
        x1 = max(x0 + 1, min(width, round(right * width)))
        y1 = max(y0 + 1, min(height, round(bottom * height)))
        reference = reference[y0:y1, x0:x1]
        aligned = aligned[y0:y1, x0:x1]
    metrics = _metrics(reference, aligned)
    return {
        "reference": str(reference_path),
        "candidate": str(candidate_path),
        "reference_shape": list(_load(reference_path).shape),
        "candidate_shape": list(_load(candidate_path).shape),
        "shape_match": same_shape,
        "region": list(region) if region is not None else None,
        **metrics,
    }


def compare_grain_statistics(
    source_path: Path,
    reference_path: Path,
    candidate_path: Path,
) -> dict[str, Any]:
    """Compare stochastic grain without requiring identical random samples."""
    source = _load(source_path)
    reference = _load(reference_path)
    candidate = _load(candidate_path)
    same_shape = source.shape == reference.shape == candidate.shape
    if not same_shape:
        return {"shape_match": False}
    reference_residual = reference - source
    candidate_residual = candidate - source
    reference_std = reference_residual.std(axis=(0, 1))
    candidate_std = candidate_residual.std(axis=(0, 1))
    relative_std_error = np.abs(candidate_std - reference_std) / np.maximum(
        reference_std, 1e-8
    )
    height, width = reference.shape[:2]
    reduced_shape = (max(1, height // 8), max(1, width // 8))
    return {
        "shape_match": True,
        "reference_residual_std_rgb": [float(value) for value in reference_std],
        "candidate_residual_std_rgb": [float(value) for value in candidate_std],
        "residual_std_relative_error_max": float(relative_std_error.max()),
        "residual_mean_delta_max": float(
            np.abs(
                candidate_residual.mean(axis=(0, 1))
                - reference_residual.mean(axis=(0, 1))
            ).max()
        ),
        "gradient_delta": abs(
            _gradient_strength(candidate) - _gradient_strength(reference)
        ),
        "low_frequency_ssim": float(
            _ssim(
                _resize(reference, reduced_shape),
                _resize(candidate, reduced_shape),
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--region",
        nargs=4,
        type=float,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="normalized region coordinates in the range 0..1",
    )
    args = parser.parse_args()
    report = compare(args.reference, args.candidate, tuple(args.region) if args.region else None)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
