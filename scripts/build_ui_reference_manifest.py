"""Build a fail-closed manifest for native Luminar UI reference screenshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingKind, SamplingQueue
from scripts.luminar_capture.ui_evidence import sha256_file, ui_fixture_identity


def _relative_artifact(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def build_manifest(
    *,
    queue: SamplingQueue,
    capture_root: Path,
    reference_root: Path,
    sampling_config: Path,
    expected_app: dict[str, str],
    ui_matrix: dict[str, Any],
) -> dict[str, Any]:
    config = load_luminar_sampling_config(sampling_config)
    if ui_matrix.get("reference_id") != queue.reference_id:
        raise ValueError("UI matrix and sampling queue use different references")
    matrix_fingerprint = str(ui_matrix.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        raise ValueError("UI matrix fingerprint must be a SHA-256 digest")
    expected_ids = {
        str(item["id"])
        for item in ui_matrix.get("records", [])
        if isinstance(item, dict) and item.get("id")
    }
    if not expected_ids:
        raise ValueError("UI matrix has no records")
    records: list[dict[str, Any]] = []
    actual_ids: set[str] = set()
    for record in queue.records:
        if record.kind is not SamplingKind.UI:
            continue
        matrix_state_id = str(record.payload.get("matrix_state_id") or "")
        state = CaptureLayout(capture_root, record.capture_id).state_path
        payload = json.loads(state.read_text(encoding="utf-8")) if state.is_file() else {}
        canonical = payload.get("canonical") or {}
        fixture_id, fixture_hash = ui_fixture_identity(record, config)
        issues: list[str] = []
        if matrix_state_id not in expected_ids:
            issues.append("matrix-state-id-unexpected")
        elif matrix_state_id in actual_ids:
            issues.append("matrix-state-id-duplicate")
        actual_ids.add(matrix_state_id)
        if record.payload.get("matrix_fingerprint") != matrix_fingerprint:
            issues.append("matrix-fingerprint-mismatch")
        if canonical.get("reference_id") != queue.reference_id:
            issues.append("reference-id-missing-or-mismatch")
        if canonical.get("app_version") != expected_app:
            issues.append("app-version-missing-or-mismatch")
        if canonical.get("fixture_id") != fixture_id or canonical.get("fixture_hash") != fixture_hash:
            issues.append("fixture-missing-or-mismatch")
        if canonical.get("matrix_state_id") != matrix_state_id:
            issues.append("ui-state-mismatch")
        if canonical.get("matrix_fingerprint") != matrix_fingerprint:
            issues.append("canonical-matrix-fingerprint-mismatch")
        if canonical.get("viewport") != record.payload["viewport"]:
            issues.append("viewport-mismatch")
        artifacts: dict[str, str | None] = {}
        for field, hash_field in (
            ("screenshot", "screenshot_sha256"),
            ("accessibility_tree", "accessibility_tree_sha256"),
        ):
            raw = canonical.get(field)
            path = Path(str(raw)).resolve() if raw else reference_root / "__missing__"
            relative = _relative_artifact(path, reference_root)
            artifacts[field] = relative
            if relative is None:
                issues.append(f"{field}-outside-reference-root")
            elif not path.is_file():
                issues.append(f"{field}-missing")
            elif canonical.get(hash_field) != sha256_file(path):
                issues.append(f"{field}-hash-mismatch")
        records.append(
            {
                "id": record.record_id,
                "capture_id": record.capture_id,
                "matrix_state_id": matrix_state_id,
                "viewport": record.payload["viewport"],
                "fixture_id": fixture_id,
                "fixture_hash": fixture_hash,
                "attempt_id": canonical.get("attempt_id"),
                "captured_at": canonical.get("published_at"),
                "screenshot": artifacts["screenshot"],
                "screenshot_sha256": canonical.get("screenshot_sha256"),
                "accessibility_tree": artifacts["accessibility_tree"],
                "accessibility_tree_sha256": canonical.get(
                    "accessibility_tree_sha256"
                ),
                "status": "verified" if not issues else "invalid-evidence",
                "issues": issues,
            }
        )
    invalid = sum(item["status"] != "verified" for item in records)
    missing_ids = sorted(expected_ids - actual_ids)
    return {
        "version": "2.0",
        "reference_id": queue.reference_id,
        "matrix_fingerprint": matrix_fingerprint,
        "app_version": expected_app,
        "queue_fingerprint": queue.fingerprint,
        "record_count": len(records),
        "verified": len(records) - invalid,
        "invalid": invalid,
        "missing_matrix_state_ids": missing_ids,
        "gate": "passed" if records and not invalid and not missing_ids else "blocked",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--sampling-config", type=Path, default=ROOT / "configs/luminar_sampling.yaml"
    )
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    queue_path = (args.queue or profile.diagnostics_root / "sampling-queue.json").resolve()
    queue = SamplingQueue.load(queue_path, expected_reference_id=profile.id)
    report = build_manifest(
        queue=queue,
        capture_root=profile.capture_root,
        reference_root=profile.ui_reference_root,
        sampling_config=args.sampling_config.resolve(),
        expected_app={
            "version": profile.version,
            "build": profile.build,
            "bundle_id": profile.bundle_id,
        },
        ui_matrix=json.loads(args.matrix.resolve().read_text(encoding="utf-8")),
    )
    output = (args.output or profile.ui_reference_root / "reference-manifest.json").resolve()
    write_json_atomic(output, report)
    print(
        json.dumps(
            {key: report[key] for key in ("record_count", "verified", "invalid", "gate")},
            ensure_ascii=False,
        )
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
