#!/usr/bin/env python3
"""Recertify unchanged current-build UI evidence after a scope-only matrix cut."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingKind, SamplingQueue


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def recertify(
    queue: SamplingQueue,
    *,
    capture_root: Path,
    ui_reference_root: Path,
    predecessor_fingerprint: str,
    expected_app: dict[str, str],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Rebind only byte-verified, identity-equivalent UI evidence."""

    if len(predecessor_fingerprint) != 64:
        raise ValueError("predecessor matrix fingerprint must be a SHA-256")
    now = datetime.now(UTC).isoformat()
    results: list[dict[str, Any]] = []
    for record in queue.records:
        if record.kind is not SamplingKind.UI:
            continue
        layout = CaptureLayout(capture_root, record.capture_id)
        state = (
            json.loads(layout.state_path.read_text(encoding="utf-8"))
            if layout.state_path.is_file()
            else {}
        )
        canonical = state.get("canonical")
        if not isinstance(canonical, dict) or canonical.get("status") != "ready":
            results.append({"id": record.record_id, "status": "pending", "reason": "no-ready-canonical"})
            continue
        current_fingerprint = str(record.payload["matrix_fingerprint"])
        recorded_fingerprint = str(canonical.get("matrix_fingerprint") or "")
        if recorded_fingerprint == current_fingerprint:
            results.append({"id": record.record_id, "status": "retained", "reason": "already-current"})
            continue
        errors: list[str] = []
        if recorded_fingerprint != predecessor_fingerprint:
            errors.append("unapproved-predecessor-fingerprint")
        for field, expected in {
            "reference_id": queue.reference_id,
            "matrix_state_id": record.payload["matrix_state_id"],
            "ui_state": record.payload["ui_state"],
            "viewport": record.payload["viewport"],
        }.items():
            if canonical.get(field) != expected:
                errors.append(f"canonical-{field.replace('_', '-')}-mismatch")
        canonical_app = canonical.get("app_version") or {}
        for field, expected in expected_app.items():
            if str(canonical_app.get(field, "")) != str(expected):
                errors.append(f"canonical-app-{field}-mismatch")
        width, height = record.payload["viewport"]
        screenshot = ui_reference_root / f"{width}x{height}" / f"{record.payload['ui_state']}.png"
        accessibility = screenshot.with_suffix(".ax.json")
        for field, path in (
            ("screenshot_sha256", screenshot),
            ("accessibility_tree_sha256", accessibility),
        ):
            if not path.is_file():
                errors.append(f"missing-{field.replace('_sha256', '').replace('_', '-')}")
            elif canonical.get(field) != _sha256(path):
                errors.append(f"canonical-{field.replace('_', '-')}-mismatch")
        source = record.payload.get("input")
        if isinstance(source, dict) and canonical.get("fixture_hash") != source.get("sha256"):
            errors.append("canonical-fixture-hash-mismatch")
        if errors:
            results.append({"id": record.record_id, "status": "refused", "errors": sorted(set(errors))})
            continue
        recertification = {
            "recertified_at": now,
            "source_matrix_fingerprint": recorded_fingerprint,
            "target_matrix_fingerprint": current_fingerprint,
            "reason": "scope-only-removal-of-non-native-parameter-records",
            "artifact_hashes_reverified": True,
            "attempt_mutated": False,
        }
        if not dry_run:
            updated = {
                **state,
                "status": "ready",
                "updated_at": now,
                "canonical": {
                    **canonical,
                    "queue_record_id": record.record_id,
                    "semantic_key": record.semantic_key,
                    "matrix_fingerprint": current_fingerprint,
                    "recertification": recertification,
                },
                "recertifications": [
                    *(state.get("recertifications") or []),
                    recertification,
                ],
            }
            write_json_atomic(layout.state_path, updated)
        results.append({"id": record.record_id, "status": "recertified", **recertification})
    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("recertified", "retained", "pending", "refused")
    }
    return {
        "version": "1.0",
        "generated_at": now,
        "reference_id": queue.reference_id,
        "queue_fingerprint": queue.fingerprint,
        "predecessor_matrix_fingerprint": predecessor_fingerprint,
        "dry_run": dry_run,
        "record_count": len(results),
        "counts": counts,
        "gate": "passed" if counts["refused"] == 0 else "blocked",
        "records": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--predecessor-matrix-fingerprint", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(args.reference_config.resolve(), project_root=ROOT).resolve(args.reference_id)
    queue_path = profile.diagnostics_root / "sampling-queue.json"
    queue = SamplingQueue.load(queue_path, expected_reference_id=profile.id)
    report = recertify(
        queue,
        capture_root=profile.capture_root,
        ui_reference_root=profile.ui_reference_root,
        predecessor_fingerprint=args.predecessor_matrix_fingerprint,
        expected_app={
            "version": profile.version,
            "build": profile.build,
            "bundle_id": profile.bundle_id,
        },
        dry_run=args.dry_run,
    )
    output = (args.output or profile.diagnostics_root / "ui-evidence-recertification.json").resolve()
    write_json_atomic(output, report)
    print(json.dumps({"output": str(output), **{key: report[key] for key in ("record_count", "counts", "gate")}}, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
