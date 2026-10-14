"""Remove only reproducible test-data workspaces and transient files."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.prune_sampling_staging import plan_prune

DEFAULT_TEST_DATA_ROOT = ROOT / "test_data"


def _default_profile_root() -> Path:
    return load_reference_catalog(project_root=ROOT).resolve().diagnostics_root.parent

DERIVED_WORKSPACE_PARENTS = {"overlay-workspace", "ui-workspace"}


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def _is_derived_workspace(path: Path, diagnostics_root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(diagnostics_root.resolve())
    except ValueError:
        return False
    if len(relative.parts) != 2 or relative.parts[-1] != "workspace":
        return False
    parent = relative.parts[0]
    return parent == "candidate-outputs" or (
        parent.startswith("candidate-outputs-calibration")
        or parent in DERIVED_WORKSPACE_PARENTS
    )


def build_plan(test_data_root: Path, profile_root: Path) -> dict[str, Any]:
    test_data_root = test_data_root.resolve()
    profile_root = profile_root.resolve()
    diagnostics_root = profile_root / "diagnostics"
    capture_root = profile_root / "captures"

    workspace_directories = sorted(
        path.resolve()
        for path in diagnostics_root.glob("*/workspace")
        if path.is_dir() and _is_derived_workspace(path, diagnostics_root)
    )
    staging = plan_prune(capture_root, apply=False)
    stability_files = sorted(
        (capture_root / value).resolve() for value in staging["removed"]
    )
    metadata_files = sorted(
        path.resolve() for path in test_data_root.rglob(".DS_Store") if path.is_file()
    )

    categories = {
        "workspace_directories": [str(path) for path in workspace_directories],
        "stale_stability_files": [str(path) for path in stability_files],
        "metadata_files": [str(path) for path in metadata_files],
    }
    paths = workspace_directories + stability_files + metadata_files
    return {
        "test_data_root": str(test_data_root),
        "profile_root": str(profile_root),
        "categories": categories,
        "counts": {name: len(values) for name, values in categories.items()},
        "path_count": len(paths),
        "reclaimable_bytes": sum(_path_size(path) for path in paths),
        "preserved": {
            "canonical_captures": str(capture_root),
            "native_exports": str(profile_root / "native-exports"),
            "current_candidates": str(diagnostics_root / "candidate-outputs"),
            "failed_staging_policy": "retain the last three full and preview stability frames",
            "versioned_references": str(test_data_root / "parity" / "references"),
            "source_dataset": str(test_data_root / "夏日户外拍照"),
        },
    }


def _assert_safe_target(path: Path, test_data_root: Path) -> None:
    resolved = path.resolve()
    root = test_data_root.resolve()
    if resolved == root or root not in resolved.parents:
        raise RuntimeError(f"refusing to remove path outside test_data: {resolved}")


def apply_plan(plan: dict[str, Any]) -> None:
    test_data_root = Path(plan["test_data_root"])
    profile_root = Path(plan["profile_root"])
    diagnostics_root = profile_root / "diagnostics"
    capture_staging_root = profile_root / "captures" / "staging"
    categories = plan["categories"]

    for value in categories["workspace_directories"]:
        path = Path(value)
        _assert_safe_target(path, test_data_root)
        if not _is_derived_workspace(path, diagnostics_root):
            raise RuntimeError(f"refusing unexpected workspace path: {path}")
        if path.is_dir():
            shutil.rmtree(path)

    for value in categories["stale_stability_files"]:
        path = Path(value)
        _assert_safe_target(path, test_data_root)
        try:
            path.resolve().relative_to(capture_staging_root.resolve())
        except ValueError as exc:
            raise RuntimeError(f"refusing unexpected stability path: {path}") from exc
        if not path.name.startswith("stable-") or path.suffix.lower() != ".png":
            raise RuntimeError(f"refusing unexpected stability file: {path}")
        path.unlink(missing_ok=True)

    for value in categories["metadata_files"]:
        path = Path(value)
        _assert_safe_target(path, test_data_root)
        if path.name != ".DS_Store":
            raise RuntimeError(f"refusing unexpected metadata file: {path}")
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-data-root", type=Path, default=DEFAULT_TEST_DATA_ROOT)
    parser.add_argument("--profile-root", type=Path, default=_default_profile_root())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = build_plan(args.test_data_root, args.profile_root)
    if args.apply:
        apply_plan(plan)
    report = {
        "status": "applied" if args.apply else "dry-run",
        **plan,
    }
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
