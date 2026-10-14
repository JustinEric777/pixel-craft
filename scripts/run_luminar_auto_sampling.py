"""Run resumable semantic sampling against the installed Luminar Neo app."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.accessibility_driver import LuminarAccessibilityDriver
from scripts.luminar_capture.app_controller import LuminarAppController
from scripts.luminar_capture.auto_sampler import LuminarAutoSampler
from scripts.luminar_capture.case_reader import load_cases
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.preflight import (
    NativeCaptureRequirements,
    run_preflight,
)


def requires_ui_control(*, preflight: bool, dry_run: bool) -> bool:
    """Return whether the requested command may activate or control Luminar."""
    return preflight or not dry_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--sampling-config",
        type=Path,
        default=ROOT / "configs/luminar_sampling.yaml",
    )
    parser.add_argument("--app", type=Path)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--capability-id", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-ui-control",
        action="store_true",
        help="explicitly allow Luminar to take foreground keyboard and mouse control",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="verify app version, selected inputs and current accessibility window",
    )
    args = parser.parse_args()

    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    config = load_luminar_sampling_config(args.sampling_config.resolve())
    if config.reference_id != profile.id:
        raise RuntimeError(
            f"sampling reference mismatch: {config.reference_id!r} != {profile.id!r}"
        )
    app_path = (args.app or config.app_path).resolve()
    controller = LuminarAppController(app_path)
    profile.validate_app_version(controller.version())
    cases = load_cases(
        profile.cases_path,
        case_ids=set(args.case_id or ()) or None,
        capability_ids=set(args.capability_id or ()) or None,
        limit=args.limit,
    )
    if requires_ui_control(preflight=args.preflight, dry_run=args.dry_run) and not args.allow_ui_control:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "foreground-ui-control-not-authorized",
                    "message": (
                        "Luminar preflight and sampling may activate or control the active "
                        "macOS desktop. Run again with --allow-ui-control only in a dedicated "
                        "GUI session."
                    ),
                    "native_export_root": str(config.native_export_root),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    if args.preflight:
        preflight: dict[str, object]
        try:
            preflight = run_preflight(
                controller,
                LuminarAccessibilityDriver(
                    timeout_seconds=config.timeouts.action_seconds
                ),
                output_dir=profile.diagnostics_root / "preflight",
                timeout_seconds=config.timeouts.action_seconds,
                requirements=NativeCaptureRequirements(
                    reference_id=profile.id,
                    app_version=profile.version,
                    app_build=profile.build,
                    bundle_id=profile.bundle_id,
                    locale=profile.locale,
                    logical_viewport=config.logical_viewport,
                    physical_viewport=config.viewports[0],
                    environment_evidence_path=config.environment_evidence_path,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - native app boundary
            preflight = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        missing_inputs = [str(case.input_path) for case in cases if not case.input_path.is_file()]
        ready = not missing_inputs and preflight.get("ok") is True
        print(
            json.dumps(
                {
                    "status": "ready" if ready else "blocked",
                    "reference_id": profile.id,
                    "app": str(app_path),
                    "app_version": controller.version(),
                    "case_count": len(cases),
                    "missing_inputs": missing_inputs,
                    "preflight": preflight,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if ready else 1
    if args.dry_run:
        print(
            json.dumps(
                [
                    {
                        "case_id": case.case_id,
                        "capability_id": case.capability_id,
                        "recipe": asdict(config.recipe_for(case.capability_id)),
                    }
                    for case in cases
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    driver = LuminarAccessibilityDriver(
        timeout_seconds=config.timeouts.action_seconds
    )
    try:
        native_preflight = run_preflight(
            controller,
            driver,
            output_dir=profile.diagnostics_root / "preflight",
            timeout_seconds=config.timeouts.action_seconds,
            requirements=NativeCaptureRequirements(
                reference_id=profile.id,
                app_version=profile.version,
                app_build=profile.build,
                bundle_id=profile.bundle_id,
                locale=profile.locale,
                logical_viewport=config.logical_viewport,
                physical_viewport=config.viewports[0],
                environment_evidence_path=config.environment_evidence_path,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - native app boundary
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "native-preflight-failed",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    if native_preflight.get("ok") is not True:
        return 1

    sampler = LuminarAutoSampler(
        config,
        controller,
        driver,
        reference_build=profile.id,
        app_version=controller.version(),
    )
    results = []
    for case in cases:
        layout = CaptureLayout(profile.capture_root, case.case_id)
        current = (
            json.loads(layout.state_path.read_text(encoding="utf-8"))
            if layout.state_path.is_file()
            else {}
        )
        if current.get("status") == "ready":
            continue
        results.append(asdict(sampler.probe(case, layout, config.recipe_for(case.capability_id))))
    report = {
        "reference_id": profile.id,
        "attempted": len(results),
        "ready": sum(item["status"] == "ready" for item in results),
        "effect_sampled": sum(item["status"] == "effect-sampled" for item in results),
        "panel_probed": sum(item["status"] == "panel-probed" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    output = profile.diagnostics_root / "auto-sampling-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
