"""Keep one native export per ready canonical capture and remove transient images."""

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


def _active_roots() -> tuple[Path, Path]:
    profile = load_reference_catalog(project_root=ROOT).resolve()
    return profile.capture_root, profile.diagnostics_root.parent / "native-exports"


def build_plan(capture_root: Path, export_root: Path) -> dict[str, Any]:
    capture_root = capture_root.resolve()
    export_root = export_root.resolve()
    canonical_exports: set[Path] = set()
    ready_capture_count = 0
    for state_path in sorted((capture_root / "state").glob("*.json")):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        canonical = state.get("canonical") or {}
        last_attempt = state.get("last_attempt") or {}
        if canonical.get("status") != "ready":
            continue
        ready_capture_count += 1
        if canonical.get("attempt_id") != last_attempt.get("attempt_id"):
            continue
        raw_path = last_attempt.get("export_path")
        if not isinstance(raw_path, str):
            continue
        resolved = Path(raw_path).resolve()
        if resolved.parent == export_root or export_root in resolved.parents:
            canonical_exports.add(resolved)

    redundant_exports = sorted(
        path.resolve()
        for path in export_root.rglob("*")
        if path.is_file() and path.resolve() not in canonical_exports
    )
    staging_root = capture_root / "staging"
    transient_paths = (
        sorted(path.resolve() for path in staging_root.iterdir())
        if staging_root.is_dir()
        else []
    )
    return {
        "ready_capture_count": ready_capture_count,
        "canonical_export_count": len(canonical_exports),
        "canonical_exports": [str(path) for path in sorted(canonical_exports)],
        "redundant_exports": [str(path) for path in redundant_exports],
        "transient_paths": [str(path) for path in transient_paths],
        "reclaimable_bytes": sum(path.stat().st_size for path in redundant_exports)
        + sum(_path_size(path) for path in transient_paths),
    }


def apply_plan(capture_root: Path, export_root: Path, plan: dict[str, Any]) -> None:
    capture_root = capture_root.resolve()
    export_root = export_root.resolve()
    staging_root = (capture_root / "staging").resolve()
    for raw_path in plan["redundant_exports"]:
        path = Path(raw_path).resolve()
        if path.parent != export_root and export_root not in path.parents:
            raise RuntimeError(f"refusing to remove export outside root: {path}")
        path.unlink(missing_ok=True)
    for raw_path in plan["transient_paths"]:
        path = Path(raw_path).resolve()
        if path.parent != staging_root:
            raise RuntimeError(f"refusing to remove transient outside staging: {path}")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    for directory in sorted(
        (path for path in export_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    capture_root, export_root = _active_roots()
    parser.add_argument("--capture-root", type=Path, default=capture_root)
    parser.add_argument("--export-root", type=Path, default=export_root)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    capture_root = args.capture_root.resolve()
    export_root = args.export_root.resolve()
    plan = build_plan(capture_root, export_root)
    if args.apply:
        apply_plan(capture_root, export_root, plan)
    report = {"status": "applied" if args.apply else "dry-run", **plan}
    if args.output:
        args.output.resolve().write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
