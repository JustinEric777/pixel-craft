"""Run every currently dispatched model-specific analysis pipeline once."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.pipeline.factory import build_model_service
from configs import load_config
from storage.cache.artifact_cache import ArtifactCache

REQUESTED = [
    "face_detector_retinaface",
    "salient_object_improve_exp19_it150k",
    "SemanticSearchImage",
    "MulticlassSegmentationV2",
    "SegmentAnything",
    "mobilenet_exp78_portrait_BOKEH12",
    "LPTN_exp108_wires",
    "DFINEHumanTransportDetection",
    "dust_spot_det_i8",
    "GFPGANv1.3_2023",
    "DepthAnythingV2SmallOpenVino",
    "improved_sky_segmentator_v462_i8",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, default=Path("models"))
    parser.add_argument("--registry", type=Path, default=Path("configs/model.yaml"))
    parser.add_argument("--cache-root", type=Path, default=Path("data/cache/audit"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image = Image.new("RGB", (96, 72), (36, 70, 112))
    service = build_model_service(load_config(ROOT), model_root=args.model_root, registry_path=args.registry)
    cache = ArtifactCache(args.cache_root)
    source_path = args.cache_root / "audit-source.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(source_path)
    source_hash = cache.source_hash(source_path)
    results = service.analyze(image, REQUESTED, artifact_cache=cache, source_hash=source_hash)
    payload = {
        "version": "0.1.0",
        "requested": REQUESTED,
        "ready": sum(item.get("status") == "ready" for item in results.values()),
        "blocked": sum(item.get("status") == "blocked" for item in results.values()),
        "failed": sum(item.get("status") == "failed" for item in results.values()),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: payload[key] for key in ("ready", "blocked", "failed")}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
