"""Validate evidence completeness for every record in the Luminar sampling queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.luminar_capture.queue_validator import validate_queue
from scripts.luminar_capture.sampling_queue import SamplingQueue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    queue_path = (args.queue or profile.diagnostics_root / "sampling-queue.json").resolve()
    queue = SamplingQueue.load(queue_path, expected_reference_id=profile.id)
    report = {
        "version": "1.0",
        "reference_id": profile.id,
        "queue": str(queue_path),
        **validate_queue(
            queue.records,
            capture_root=profile.capture_root,
            ui_reference_root=profile.ui_reference_root,
            expected_reference_id=profile.id,
            expected_app={
                "version": profile.version,
                "build": profile.build,
                "bundle_id": profile.bundle_id,
            },
        ),
    }
    output = (
        args.output or profile.diagnostics_root / "sampling-queue-evidence.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reference_id": profile.id,
                "record_count": report["record_count"],
                "ready": report["ready"],
                "pending": report["pending"],
                "gate": report["gate"],
                "by_kind": report["by_kind"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
