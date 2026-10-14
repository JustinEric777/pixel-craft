"""Render every imported Luminar preset on one fixed validation image."""

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

from image_ops.effects.luminar_preset import apply_luminar_preset

SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def _default_source() -> Path:
    root = ROOT / "test_data/夏日户外拍照"
    source = next(
        (
            path
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGES
        ),
        None,
    )
    if source is None:
        raise FileNotFoundError(f"preset validation dataset has no images: {root}")
    return source


def _effects(preset: dict[str, Any]) -> list[dict[str, Any]]:
    graph = preset.get("edit_graph", [])
    if len(graph) != 1 or graph[0].get("effect") != "luminar_preset":
        raise ValueError(f"{preset.get('id', '<unknown>')}: invalid imported edit graph")
    effects = graph[0].get("parameters", {}).get("source_effects")
    if not isinstance(effects, list) or not effects:
        raise ValueError(f"{preset.get('id', '<unknown>')}: source_effects is empty")
    return effects


def run(config_path: Path, source_path: Path, asset_root: Path) -> dict[str, Any]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    with Image.open(source_path) as opened:
        source = opened.convert("RGB").copy()
    before = np.asarray(source, dtype=np.float32)
    records: list[dict[str, Any]] = []
    source_effect_ids: set[str] = set()
    for preset in payload.get("presets", []):
        effects = _effects(preset)
        source_effect_ids.update(str(item.get("id")) for item in effects)
        rendered = apply_luminar_preset(source, effects, asset_root=asset_root)
        delta = np.abs(np.asarray(rendered, dtype=np.float32) - before)
        mean_delta = float(delta.mean())
        records.append(
            {
                "id": preset["id"],
                "name": preset["name"],
                "category": preset["category"],
                "source_effect_count": len(effects),
                "mean_absolute_delta": round(mean_delta, 6),
                "status": "ready" if mean_delta > 0.0 else "unchanged",
            }
        )
    return {
        "version": "0.1.0",
        "generated_by": "scripts/run_preset_validation.py",
        "source": str(source_path),
        "count": len(records),
        "categories": len({item["category"] for item in records}),
        "source_effect_ids": sorted(source_effect_ids),
        "ready": sum(item["status"] == "ready" for item in records),
        "unchanged": sum(item["status"] == "unchanged" for item in records),
        "mean_absolute_delta": round(
            float(np.mean([item["mean_absolute_delta"] for item in records])), 6
        ),
        "luminar_blackbox_parity": "pending-reference-outputs",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/presets/free.json"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/diagnostics/preset-validation.json",
    )
    parser.add_argument("--asset-root", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    source = args.source.resolve() if args.source else _default_source()
    report = run(args.config.resolve(), source, args.asset_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "count",
                    "categories",
                    "ready",
                    "unchanged",
                    "mean_absolute_delta",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["count"] > 0 and report["unchanged"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
