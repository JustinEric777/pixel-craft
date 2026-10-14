"""Validate the fail-closed registry for unusable native reference evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.luminar_capture.sampling_queue import SamplingQueue

ALLOWED_STATUSES = {"confirmed-invalid", "suspected-invalid"}
ALLOWED_ACTIONS = {"targeted-reobserve-only"}


def validate_registry(
    registry_path: Path,
    *,
    reference_config: Path,
    reference_id: str | None = None,
) -> dict[str, object]:
    profile = load_reference_catalog(
        reference_config.resolve(), project_root=ROOT
    ).resolve(reference_id)
    payload = json.loads(registry_path.resolve().read_text(encoding="utf-8"))
    queue = SamplingQueue.load(
        profile.diagnostics_root / "sampling-queue.json",
        expected_reference_id=profile.id,
    )
    known_captures = {record.capture_id for record in queue.records}
    output_root = profile.diagnostics_root.parent
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_artifacts: set[str] = set()
    records = payload.get("records")
    if payload.get("reference_id") != profile.id:
        errors.append("reference-id-mismatch")
    if not isinstance(records, list):
        errors.append("records-missing")
        records = []
    for index, record in enumerate(records):
        prefix = f"record[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix}:not-object")
            continue
        record_id = str(record.get("id", ""))
        artifact = str(record.get("artifact", ""))
        capture_id = str(record.get("capture_id", ""))
        if not record_id or record_id in seen_ids:
            errors.append(f"{prefix}:invalid-or-duplicate-id")
        seen_ids.add(record_id)
        if not artifact or artifact in seen_artifacts:
            errors.append(f"{prefix}:invalid-or-duplicate-artifact")
        seen_artifacts.add(artifact)
        if capture_id not in known_captures:
            errors.append(f"{prefix}:unknown-capture-id")
        if record.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{prefix}:invalid-status")
        if record.get("allowed_action") not in ALLOWED_ACTIONS:
            errors.append(f"{prefix}:invalid-allowed-action")
        if not record.get("reason_code"):
            errors.append(f"{prefix}:reason-code-missing")
        blocks = record.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"{prefix}:blocks-missing")
        for field in ("artifact", "evidence"):
            relative = record.get(field)
            if not isinstance(relative, str) or not (output_root / relative).is_file():
                errors.append(f"{prefix}:{field}-missing")
    return {
        "version": "1.0",
        "reference_id": profile.id,
        "registry": str(registry_path.resolve()),
        "record_count": len(records),
        "confirmed_invalid": sum(
            record.get("status") == "confirmed-invalid"
            for record in records
            if isinstance(record, dict)
        ),
        "suspected_invalid": sum(
            record.get("status") == "suspected-invalid"
            for record in records
            if isinstance(record, dict)
        ),
        "errors": errors,
        "gate": "passed" if not errors else "blocked",
        "policy": "registry-never-exempts-required-gates",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "configs/parity/invalid-references.json",
    )
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_registry(
        args.registry,
        reference_config=args.reference_config,
        reference_id=args.reference_id,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
