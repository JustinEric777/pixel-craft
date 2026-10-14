"""Prepare, screenshot, or finalize reproducible Luminar black-box cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.app_controller import LuminarAppController
from scripts.luminar_capture.capture_runner import (
    capture_ui,
    finalize_case,
    import_computer_use_state,
    prepare_case,
)
from scripts.luminar_capture.case_reader import load_cases
from scripts.luminar_capture.layout import CaptureLayout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "list",
            "recipe",
            "prepare",
            "capture-before",
            "capture-after",
            "import-computer-use",
            "finalize",
        ),
    )
    parser.add_argument(
        "--cases",
        type=Path,
    )
    parser.add_argument(
        "--capture-root",
        type=Path,
    )
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--sampling-config",
        type=Path,
        default=ROOT / "configs/luminar_sampling.yaml",
    )
    parser.add_argument("--case-id")
    parser.add_argument("--capability-id")
    parser.add_argument("--app", type=Path, default=Path("/Applications/Luminar Neo.app"))
    parser.add_argument("--preview-source", type=Path)
    parser.add_argument("--export-source", type=Path)
    parser.add_argument("--mask-source", type=Path)
    parser.add_argument("--stage", choices=("before", "after"))
    parser.add_argument("--screenshot-source", type=Path)
    parser.add_argument("--accessibility-source", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    cases_path = (args.cases or profile.cases_path).resolve()
    capture_root = (args.capture_root or profile.capture_root).resolve()
    case_ids = {args.case_id} if args.case_id else None
    capability_ids = {args.capability_id} if args.capability_id else None
    cases = load_cases(cases_path, case_ids=case_ids, capability_ids=capability_ids)
    if args.action == "list":
        payload = [
            case.__dict__ | {"input_path": str(case.input_path)} for case in cases
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    sampling = load_luminar_sampling_config(args.sampling_config.resolve())
    if sampling.reference_id != profile.id:
        raise RuntimeError(
            f"sampling reference mismatch: {sampling.reference_id!r} != {profile.id!r}"
        )
    if len(cases) != 1:
        raise SystemExit("prepare/capture/finalize requires exactly one selected case")
    case = cases[0]
    layout = CaptureLayout(capture_root, case.case_id)
    controller = LuminarAppController(args.app)
    app_version = controller.version()
    profile.validate_app_version(app_version)
    if args.action == "recipe":
        recipe = sampling.recipe_for(case.capability_id)
        print(json.dumps(recipe.__dict__, ensure_ascii=False, indent=2))
    elif args.action == "prepare":
        prepare_case(case, layout, controller)
    elif args.action in {"capture-before", "capture-after"}:
        stage = args.action.removeprefix("capture-")
        path = capture_ui(layout, controller, stage=stage)
        print(path)
    elif args.action == "import-computer-use":
        if not args.stage or not args.screenshot_source or not args.accessibility_source:
            raise SystemExit(
                "import-computer-use requires --stage, --screenshot-source and "
                "--accessibility-source"
            )
        path = import_computer_use_state(
            layout,
            stage=args.stage,
            screenshot_source=args.screenshot_source.resolve(),
            accessibility_source=args.accessibility_source.resolve(),
        )
        print(path)
    else:
        if not args.preview_source or not args.export_source:
            raise SystemExit("finalize requires --preview-source and --export-source")
        metadata = finalize_case(
            case,
            layout,
            preview_source=args.preview_source.resolve(),
            export_source=args.export_source.resolve(),
            mask_source=args.mask_source.resolve() if args.mask_source else None,
            reference_build=profile.id,
            operator_mode="guided",
            app_version=app_version,
        )
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
