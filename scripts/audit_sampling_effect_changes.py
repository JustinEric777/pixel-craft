"""Reject native captures whose export is only an unchanged-source re-encode."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingKind, SamplingQueue
from scripts.luminar_capture.stability import normalized_image_change_metrics
from scripts.luminar_capture.state_machine import CaptureJournal

VISUAL_KINDS = {
    SamplingKind.EFFECT,
    SamplingKind.PRESET,
    SamplingKind.SKY,
    SamplingKind.OVERLAY,
}


def audit_record(
    record,
    *,
    capture_root: Path,
    mae_min: float,
    pixel_delta: float,
    pixel_fraction_min: float,
    force_render_change: bool = False,
) -> dict[str, Any]:
    if record.kind not in VISUAL_KINDS or record.strategy == "panel_only":
        return {"record_id": record.record_id, "status": "not-applicable"}
    layout = CaptureLayout(capture_root, record.capture_id)
    if not layout.metadata_path.is_file() or not layout.export_path.is_file():
        return {"record_id": record.record_id, "status": "missing-evidence"}
    metadata = json.loads(layout.metadata_path.read_text(encoding="utf-8"))
    source = Path(str(metadata.get("input_path") or ""))
    if not source.is_file():
        return {
            "record_id": record.record_id,
            "status": "missing-evidence",
            "missing": str(source),
        }
    metrics = normalized_image_change_metrics(
        source,
        layout.export_path,
        pixel_delta=pixel_delta,
    )
    changed = (
        metrics["mae"] >= mae_min
        or metrics["strong_changed_pixel_fraction"] >= pixel_fraction_min
    )
    binding = record.payload.get("parameter_binding")
    neutral_anchor = (
        isinstance(binding, dict)
        and binding.get("parameter") == "amount"
        and isinstance(binding.get("value"), (int, float))
        and abs(float(binding["value"])) <= 1e-9
    )
    status = "ready" if changed else "invalid-unchanged-export"
    if neutral_anchor and not force_render_change and not changed:
        status = "valid-neutral-anchor"
    return {
        "record_id": record.record_id,
        "capture_id": record.capture_id,
        "kind": record.kind.value,
        "status": status,
        "metrics": metrics,
        "thresholds": {
            "mae_min": mae_min,
            "pixel_delta": pixel_delta,
            "pixel_fraction_min": pixel_fraction_min,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--sampling-config", type=Path, default=ROOT / "configs/luminar_sampling.yaml"
    )
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--invalidate", action="store_true")
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    config = load_luminar_sampling_config(args.sampling_config.resolve())
    queue_path = (args.queue or profile.diagnostics_root / "sampling-queue.json").resolve()
    queue = SamplingQueue.load(queue_path, expected_reference_id=profile.id)
    records = []
    for record in queue.records:
        capability_id = record.payload.get("capability_id")
        recipe = config.recipes.get(str(capability_id))
        effective = recipe.effective if recipe is not None else {}
        records.append(
            audit_record(
                record,
                capture_root=profile.capture_root,
                mae_min=float(
                    effective.get(
                        "export_source_mae_min",
                        config.export_source_mae_min,
                    )
                ),
                pixel_delta=config.change_pixel_delta_min,
                pixel_fraction_min=float(
                    effective.get(
                        "change_pixel_fraction_min",
                        config.change_pixel_fraction_min,
                    )
                ),
                force_render_change=bool(
                    recipe
                    and recipe.effective.get("export_source_change_required") is True
                ),
            )
        )
    invalid = [item for item in records if item["status"] == "invalid-unchanged-export"]
    if args.invalidate:
        by_id = {record.record_id: record for record in queue.records}
        for item in invalid:
            record = by_id[str(item["record_id"])]
            CaptureJournal(
                CaptureLayout(profile.capture_root, record.capture_id)
            ).invalidate_evidence(metrics=item["metrics"])
    counts = Counter(str(item["status"]) for item in records)
    report = {
        "version": "1.0",
        "reference_id": profile.id,
        "thresholds": {
            "mae_min": config.export_source_mae_min,
            "pixel_delta": config.change_pixel_delta_min,
            "pixel_fraction_min": config.change_pixel_fraction_min,
        },
        "counts": dict(sorted(counts.items())),
        "invalidated": len(invalid) if args.invalidate else 0,
        "records": records,
    }
    output = profile.diagnostics_root / "sampling-effect-change-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "reference_id": profile.id,
                "counts": report["counts"],
                "invalidated": report["invalidated"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 1 if invalid and not args.invalidate else 0


if __name__ == "__main__":
    raise SystemExit(main())
