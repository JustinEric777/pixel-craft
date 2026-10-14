"""Publish existing native evidence after a validator-only false rejection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.app_controller import LuminarAppController
from scripts.luminar_capture.capture_runner import finalize_case
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingQueue
from scripts.luminar_capture.stability import (
    normalized_image_change_metrics,
    normalized_image_mae,
)
from scripts.luminar_capture.state_machine import CaptureJournal, CaptureStatus


def validate_recovery_evidence(
    *,
    attempt: dict[str, Any],
    parameter_binding: dict[str, Any],
    baseline_preview: Path,
    preview: Path,
    native_export: Path,
    screenshot_mae_max: float,
    change_pixel_delta_min: float,
    change_pixel_fraction_min: float,
    stable_samples: int,
    comparison_size: int,
    preview_export_rgb_mae_max: float,
    preview_export_luma_mae_max: float,
) -> dict[str, Any]:
    if attempt.get("status") != "failed":
        raise RuntimeError("validation recovery requires an immutable failed attempt")
    if attempt.get("parameter_binding") != parameter_binding:
        raise RuntimeError("failed attempt parameter binding does not match the queue")
    if int(attempt.get("stable_samples") or 0) < stable_samples:
        raise RuntimeError("failed attempt has insufficient stable preview samples")
    for path in (baseline_preview, preview, native_export):
        if not path.is_file():
            raise FileNotFoundError(f"recovery evidence is missing: {path}")
    change = normalized_image_change_metrics(
        baseline_preview,
        preview,
        pixel_delta=change_pixel_delta_min,
    )
    if (
        change["mae"] < screenshot_mae_max
        and change["strong_changed_pixel_fraction"] < change_pixel_fraction_min
    ):
        raise RuntimeError("native preview change does not exceed the stability noise floor")
    rgb_mae = normalized_image_mae(preview, native_export, size=comparison_size)
    luma_mae = normalized_image_mae(
        preview, native_export, size=comparison_size, mode="L"
    )
    if rgb_mae > preview_export_rgb_mae_max or luma_mae > preview_export_luma_mae_max:
        raise RuntimeError("native preview and export do not represent the same result")
    return {
        "preview_change": change,
        "preview_export_rgb_mae": rgb_mae,
        "preview_export_luma_mae": luma_mae,
    }


def validate_state_authoritative_recovery(
    *,
    attempt: dict[str, Any],
    source: Path,
    preview: Path,
    native_export: Path,
    change_pixel_delta_min: float,
    export_source_mae_min: float,
    change_pixel_fraction_min: float,
) -> dict[str, Any]:
    """Validate an exported effect whose committed edit state is authoritative."""

    if attempt.get("status") != "failed":
        raise RuntimeError("validation recovery requires an immutable failed attempt")
    edit_state = attempt.get("edit_state")
    if not isinstance(edit_state, dict) or edit_state.get("verified") is not True:
        raise RuntimeError("failed attempt has no verified restore-original edit state")
    if int(attempt.get("stable_samples") or 0) < 1:
        raise RuntimeError("failed attempt has no native preview evidence")
    for path in (source, preview, native_export):
        if not path.is_file():
            raise FileNotFoundError(f"recovery evidence is missing: {path}")
    change = normalized_image_change_metrics(
        source,
        native_export,
        pixel_delta=change_pixel_delta_min,
    )
    if (
        change["mae"] < export_source_mae_min
        and change["strong_changed_pixel_fraction"] < change_pixel_fraction_min
    ):
        raise RuntimeError("native export does not contain a measurable effect")
    return {
        "edit_state": edit_state,
        "export_change": change,
        "render_completion": "native-export-stable-file",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--source-attempt-id", required=True)
    parser.add_argument("--native-export", type=Path, required=True)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument(
        "--sampling-config", type=Path, default=ROOT / "configs/luminar_sampling.yaml"
    )
    args = parser.parse_args()
    catalog = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    )
    profile = catalog.resolve()
    config = load_luminar_sampling_config(args.sampling_config.resolve())
    queue = SamplingQueue.load(
        args.queue.resolve(), expected_reference_id=profile.id
    )
    matches = [record for record in queue.records if record.capture_id == args.case_id]
    if len(matches) != 1:
        raise RuntimeError(f"exact queue did not resolve one case: {args.case_id}")
    record = matches[0]
    binding = record.payload.get("parameter_binding")
    layout = CaptureLayout(profile.capture_root, record.capture_id)
    state = CaptureJournal(layout).read()
    if (state.get("canonical") or {}).get("status") == "ready":
        raise RuntimeError("capture already has canonical evidence")
    attempt_path = layout.attempt_path(args.source_attempt_id)
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    if attempt.get("queue_record_id") != record.record_id:
        raise RuntimeError("failed attempt belongs to a different queue record")
    record.verify_inputs()
    if isinstance(binding, dict):
        metrics = validate_recovery_evidence(
            attempt=attempt,
            parameter_binding=binding,
            baseline_preview=layout.staging_dir / "baseline-preview.png",
            preview=layout.staging_preview_path,
            native_export=args.native_export.resolve(),
            screenshot_mae_max=config.screenshot_mae_max,
            change_pixel_delta_min=config.change_pixel_delta_min,
            change_pixel_fraction_min=config.change_pixel_fraction_min,
            stable_samples=config.stable_samples,
            comparison_size=config.preview_export_comparison_size,
            preview_export_rgb_mae_max=config.preview_export_rgb_mae_max,
            preview_export_luma_mae_max=config.preview_export_luma_mae_max,
        )
    else:
        recipe = config.recipes.get(str(record.payload.get("capability_id")))
        effective = recipe.effective if recipe is not None else {}
        metrics = validate_state_authoritative_recovery(
            attempt=attempt,
            source=record.to_capture_case().input_path,
            preview=layout.staging_preview_path,
            native_export=args.native_export.resolve(),
            change_pixel_delta_min=config.change_pixel_delta_min,
            export_source_mae_min=float(
                effective.get("export_source_mae_min", config.export_source_mae_min)
            ),
            change_pixel_fraction_min=float(
                effective.get(
                    "change_pixel_fraction_min",
                    config.change_pixel_fraction_min,
                )
            ),
        )
    journal = CaptureJournal(layout)
    copied_fields = {
        key: attempt[key]
        for key in (
            "automation",
            "locator_id",
            "strategy",
            "controls",
            "control",
            "value",
            "parameter_binding",
            "edit_state",
            "stable_samples",
        )
        if key in attempt
    }
    journal.begin_attempt(
        queue_record_id=record.record_id,
        scan_order=record.scan_order,
        kind=record.kind.value,
        page=record.page,
        section=record.section,
        validation_recovery=True,
        source_attempt_id=args.source_attempt_id,
        validation_metrics=metrics,
        **copied_fields,
    )
    journal.transition(
        CaptureStatus.EXPORTED,
        export_path=str(args.native_export.resolve()),
        validation_recovery=True,
    )
    app_version = LuminarAppController(config.app_path).version()
    profile.validate_app_version(app_version)
    finalize_case(
        record.to_capture_case(),
        layout,
        preview_source=layout.staging_preview_path,
        export_source=args.native_export.resolve(),
        reference_build=profile.id,
        operator_mode="macos-accessibility-validation-recovery",
        app_version=app_version,
        preview_evidence="native-window-preview",
        export_evidence="native-export",
    )
    print(
        json.dumps(
            {
                "status": "ready",
                "case_id": record.capture_id,
                "source_attempt_id": args.source_attempt_id,
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
