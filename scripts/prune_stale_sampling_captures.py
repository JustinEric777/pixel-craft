"""Prune native Luminar captures that are not part of the active sampling queue."""

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
from scripts.luminar_capture.sampling_queue import SamplingQueue

DIRECTORY_COLLECTIONS = ("luminar_outputs", "luminar_ui")
FILE_COLLECTIONS = {"metadata": ".json", "state": ".json", "logs": ".jsonl"}


def build_plan(capture_root: Path, active_capture_ids: set[str]) -> dict[str, object]:
    stale: list[Path] = []
    for collection in DIRECTORY_COLLECTIONS:
        root = capture_root / collection
        if not root.is_dir():
            continue
        stale.extend(
            child
            for child in root.iterdir()
            if child.is_dir() and child.name not in active_capture_ids
        )
    for collection, suffix in FILE_COLLECTIONS.items():
        root = capture_root / collection
        if not root.is_dir():
            continue
        stale.extend(
            child
            for child in root.iterdir()
            if child.is_file()
            and child.suffix == suffix
            and child.name.removesuffix(suffix) not in active_capture_ids
        )
    staging_root = capture_root / "staging"
    transient = (
        sorted(child for child in staging_root.iterdir() if child.is_dir())
        if staging_root.is_dir()
        else []
    )
    paths = sorted(stale) + transient
    return {
        "stale_paths": [str(path.resolve()) for path in sorted(stale)],
        "transient_paths": [str(path.resolve()) for path in transient],
        "reclaimable_bytes": sum(_path_size(path) for path in paths),
    }


def apply_plan(capture_root: Path, plan: dict[str, object]) -> None:
    root = capture_root.resolve()
    paths = [
        Path(value)
        for key in ("stale_paths", "transient_paths")
        for value in plan[key]  # type: ignore[index]
    ]
    for path in paths:
        resolved = path.resolve()
        if resolved.parent == root or root not in resolved.parents:
            raise RuntimeError(f"refusing to remove path outside capture collections: {resolved}")
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink(missing_ok=True)


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    queue_path = (args.queue or profile.diagnostics_root / "sampling-queue.json").resolve()
    queue = SamplingQueue.load(queue_path, expected_reference_id=profile.id)
    plan = build_plan(
        profile.capture_root,
        {record.capture_id for record in queue.records},
    )
    if args.apply:
        apply_plan(profile.capture_root, plan)
    print(
        json.dumps(
            {
                "status": "applied" if args.apply else "dry-run",
                "reference_id": profile.id,
                "active_capture_ids": len(queue.records),
                "stale_paths": len(plan["stale_paths"]),
                "transient_paths": len(plan["transient_paths"]),
                "reclaimable_bytes": plan["reclaimable_bytes"],
                "plan": plan,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
