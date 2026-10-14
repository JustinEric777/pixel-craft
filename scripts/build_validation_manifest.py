"""Build a reproducible manifest for an external local image validation set."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path, source_root: Path) -> dict[str, Any]:
    digest = _sha256(path)
    record: dict[str, Any] = {
        "id": f"validation_{digest[:16]}",
        "path": str(path.resolve()),
        "relative_path": str(path.resolve().relative_to(source_root.resolve())),
        "filename": path.name,
        "sha256": digest,
        "size_bytes": path.stat().st_size,
    }
    try:
        with Image.open(path) as image:
            record.update(
                {
                    "width": image.width,
                    "height": image.height,
                    "mode": image.mode,
                    "format": image.format,
                    "icc_profile": bool(image.info.get("icc_profile")),
                    "exif_orientation": image.getexif().get(274),
                }
            )
    except (OSError, ValueError) as exc:
        record["inspection_error"] = f"{type(exc).__name__}: {exc}"
    return record


def _records(root: Path) -> list[dict[str, Any]]:
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED
    )
    return [_record(path, root) for path in paths]


def dataset_fingerprint(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["relative_path"])):
        digest.update(str(record["relative_path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _diff_records(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> dict[str, list[str]]:
    expected_by_path = {str(item["relative_path"]): str(item["sha256"]) for item in expected}
    actual_by_path = {str(item["relative_path"]): str(item["sha256"]) for item in actual}
    return {
        "missing": sorted(expected_by_path.keys() - actual_by_path.keys()),
        "extra": sorted(actual_by_path.keys() - expected_by_path.keys()),
        "changed": sorted(
            path
            for path in expected_by_path.keys() & actual_by_path.keys()
            if expected_by_path[path] != actual_by_path[path]
        ),
    }


def check(source_root: Path, output: Path, snapshot_root: Path | None = None) -> dict[str, Any]:
    source_root = source_root.resolve()
    if not output.is_file():
        return {"status": "stale", "reason": "manifest-missing", "output": str(output)}
    payload = json.loads(output.read_text(encoding="utf-8"))
    expected = list(payload.get("records", []))
    source_records = _records(source_root)
    source_diff = _diff_records(expected, source_records)
    snapshot_diff = None
    if snapshot_root is not None:
        snapshot_root = snapshot_root.resolve()
        snapshot_records = _records(snapshot_root) if snapshot_root.is_dir() else []
        snapshot_diff = _diff_records(expected, snapshot_records)
    expected_fingerprint = str(payload.get("dataset_fingerprint", ""))
    current_fingerprint = dataset_fingerprint(source_records)
    diffs = [source_diff, *(item for item in (snapshot_diff,) if item is not None)]
    fresh = bool(expected_fingerprint) and expected_fingerprint == current_fingerprint and not any(
        values for diff in diffs for values in diff.values()
    )
    return {
        "status": "fresh" if fresh else "stale",
        "output": str(output.resolve()),
        "expected_count": len(expected),
        "current_count": len(source_records),
        "expected_fingerprint": expected_fingerprint or None,
        "current_fingerprint": current_fingerprint,
        "source_diff": source_diff,
        "snapshot_diff": snapshot_diff,
    }


def _prune_snapshot(snapshot_root: Path, retained: set[Path]) -> int:
    if not snapshot_root.is_dir():
        return 0
    removed = 0
    for path in snapshot_root.rglob("*"):
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED
            and path.relative_to(snapshot_root) not in retained
        ):
            path.unlink()
            removed += 1
    for directory in sorted(
        (path for path in snapshot_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass
    return removed


def run(
    source_root: Path,
    output: Path,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    source_paths = sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED
    )
    manifest_root = source_root
    paths = source_paths
    pruned_count = 0
    if snapshot_root is not None:
        manifest_root = snapshot_root.resolve()
        if manifest_root == source_root:
            raise ValueError("snapshot directory must differ from source directory")
        copied: list[Path] = []
        for source in source_paths:
            destination = manifest_root / source.relative_to(source_root)
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            except FileNotFoundError:
                continue
            copied.append(destination)
        paths = copied
        retained = {path.relative_to(manifest_root) for path in copied}
        pruned_count = _prune_snapshot(manifest_root, retained)
    records = [_record(path, manifest_root) for path in paths]
    fingerprint = dataset_fingerprint(records)
    payload = {
        "version": "1.0.0",
        "generated_by": "scripts/build_validation_manifest.py",
        "source_root": str(manifest_root),
        "original_source_root": str(source_root),
        "count": len(records),
        "dataset_fingerprint": fingerprint,
        "pruned_count": pruned_count,
        "records": records,
        "purpose": "local image inference, edit preview/export and performance validation",
        "reference_note": "These inputs do not replace Luminar black-box outputs.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "source_root": str(manifest_root),
        "original_source_root": str(source_root),
        "count": len(records),
        "dataset_fingerprint": fingerprint,
        "pruned_count": pruned_count,
        "output": str(output),
        "ids": [record["id"] for record in records],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        help="copy the current source set before hashing so later source changes cannot invalidate cases",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "test_data/parity/validation-samples.json"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the source, snapshot and manifest without modifying any files",
    )
    args = parser.parse_args()
    if not args.source_dir.is_dir():
        parser.error(f"source directory does not exist or is not readable: {args.source_dir}")
    if args.check:
        result = check(args.source_dir, args.output, args.snapshot_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "fresh" else 1
    result = run(args.source_dir, args.output, args.snapshot_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
