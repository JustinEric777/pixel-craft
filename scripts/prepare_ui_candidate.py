"""Derive a physical UI candidate from a logical in-app Browser capture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_candidate(
    source: Path,
    output: Path,
    *,
    logical_viewport: tuple[int, int],
    device_scale_factor: float,
) -> dict[str, object]:
    if device_scale_factor <= 0:
        raise ValueError("device scale factor must be positive")
    source = source.resolve()
    output = output.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"logical UI capture is missing: {source}")
    target_size = tuple(round(value * device_scale_factor) for value in logical_viewport)
    with Image.open(source) as image:
        if image.size != logical_viewport:
            raise ValueError(
                f"logical UI capture size mismatch: {image.size} != {logical_viewport}"
            )
        candidate = image.convert("RGB").resize(target_size, Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    candidate.save(temporary, format="PNG")
    temporary.replace(output)
    return {
        "source": str(source),
        "source_sha256": sha256_file(source),
        "source_size": list(logical_viewport),
        "output": str(output),
        "output_sha256": sha256_file(output),
        "output_size": list(target_size),
        "device_scale_factor": device_scale_factor,
        "scale_method": "lanczos",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--logical-width", type=int, default=1440)
    parser.add_argument("--logical-height", type=int, default=900)
    parser.add_argument("--device-scale-factor", type=float, default=2.0)
    args = parser.parse_args()
    report = prepare_candidate(
        args.source,
        args.output,
        logical_viewport=(args.logical_width, args.logical_height),
        device_scale_factor=args.device_scale_factor,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
