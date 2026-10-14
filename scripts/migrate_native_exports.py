"""One-time promotion of existing exports into per-case native evidence paths."""

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

from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.metadata_writer import sha256_file

SUFFIXES = (".jpeg", ".jpg", ".png", ".tif", ".tiff")


def migrate_exports(
    capture_root: Path,
    source_root: Path,
    *,
    apply: bool,
) -> dict[str, Any]:
    capture_root = capture_root.resolve()
    source_root = source_root.resolve()
    source_by_stem = {
        path.stem: path
        for path in source_root.iterdir()
        if path.is_file() and path.suffix.lower() in SUFFIXES
    }
    records = []
    for metadata_path in sorted((capture_root / "metadata").glob("*.json")):
        layout = CaptureLayout(capture_root, metadata_path.stem)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        source = source_by_stem.get(layout.case_id)
        provenance = "original-native-export"
        if source is None:
            source = layout.export_path
            provenance = "normalized-legacy-export"
        if not source.is_file():
            records.append({"case_id": layout.case_id, "status": "missing"})
            continue
        destination = layout.native_export_path(source.suffix)
        records.append(
            {
                "case_id": layout.case_id,
                "status": "ready" if destination.exists() else "promote",
                "source": str(source),
                "destination": str(destination),
                "provenance": provenance,
            }
        )
        if apply and not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        if apply:
            metadata["native_export"] = {
                "path": str(destination),
                "format": destination.suffix.lstrip(".").upper(),
                "size": destination.stat().st_size,
                "sha256": sha256_file(destination),
                "provenance": provenance,
            }
            write_json_atomic(metadata_path, metadata)
    return {
        "capture_root": str(capture_root),
        "source_root": str(source_root),
        "applied": apply,
        "ready": sum(item["status"] in {"ready", "promote"} for item in records),
        "missing": sum(item["status"] == "missing" for item in records),
        "normalized_fallbacks": sum(
            item.get("provenance") == "normalized-legacy-export" for item in records
        ),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = migrate_exports(args.capture_root, args.source_root, apply=args.apply)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["missing"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
