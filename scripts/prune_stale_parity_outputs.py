"""Prune derived candidate evidence that is not part of the active case set."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog

STALE_REPORTS = (
    "candidate-model-invocations.json",
    "candidate-output-report.json",
    "dataset-freshness.json",
    "free-capability-coverage.json",
    "multi-image-workflow-smoke.json",
    "parity-cases-candidates.json",
    "parity-report.json",
    "preset-validation.json",
    "quality-gates-exact.json",
    "quality-gates-functional.json",
    "reference-capture-audit.json",
    "sampling-queue-evidence.json",
    "ui-parity.json",
    "validation-sky-e2e-report.json",
)


def build_plan(
    candidate_roots: tuple[Path, ...],
    diagnostics_root: Path,
    case_ids: set[str],
    *,
    minimum_report_mtime: float,
) -> dict[str, list[str]]:
    stale_candidates: list[str] = []
    stale_workspaces: list[str] = []
    for root in candidate_roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.name == "workspace" and child.is_dir():
                stale_workspaces.append(str(child.resolve()))
            elif child.is_dir() and child.name not in case_ids:
                stale_candidates.append(str(child.resolve()))
    stale_reports = [
        str((diagnostics_root / name).resolve())
        for name in STALE_REPORTS
        if (diagnostics_root / name).is_file()
        and (diagnostics_root / name).stat().st_mtime < minimum_report_mtime
    ]
    return {
        "candidate_directories": sorted(stale_candidates),
        "workspace_directories": sorted(stale_workspaces),
        "report_files": sorted(stale_reports),
    }


def apply_plan(plan: dict[str, list[str]]) -> None:
    for value in plan["candidate_directories"] + plan["workspace_directories"]:
        shutil.rmtree(Path(value))
    for value in plan["report_files"]:
        Path(value).unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    cases = json.loads(profile.cases_path.read_text(encoding="utf-8"))
    case_ids = {str(item["case_id"]) for item in cases.get("cases", [])}
    profile_root = profile.diagnostics_root.parent
    candidate_roots = (
        profile_root / "candidate-outputs",
        profile.diagnostics_root / "candidate-outputs",
    )
    plan = build_plan(
        candidate_roots,
        profile.diagnostics_root,
        case_ids,
        minimum_report_mtime=profile.cases_path.stat().st_mtime,
    )
    if args.apply:
        apply_plan(plan)
    counts = {key: len(value) for key, value in plan.items()}
    print(
        json.dumps(
            {"status": "applied" if args.apply else "dry-run", "counts": counts, "plan": plan},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
