"""Fail closed when queue, canonical evidence, attempts or job artifacts diverge."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingQueue


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _matching_run_evidence(
    latest_run_path: Path, queue_fingerprint: str
) -> tuple[Path | None, str | None]:
    """Find run evidence for one queue without assuming it ran most recently."""
    candidates = [latest_run_path]
    archive_root = latest_run_path.parent / "sampling-runs"
    if archive_root.is_dir():
        candidates.extend(
            sorted(
                archive_root.glob("*.json"),
                key=lambda path: (path.stat().st_mtime_ns, path.name),
                reverse=True,
            )
        )
    observed_latest: str | None = None
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        payload = json.loads(path.read_text(encoding="utf-8"))
        fingerprint = payload.get("queue_fingerprint")
        if path == latest_run_path:
            observed_latest = fingerprint if isinstance(fingerprint, str) else None
        if fingerprint == queue_fingerprint:
            return path, observed_latest
    return None, observed_latest


def _validate_parameter_binding(
    record: Any, state: dict[str, Any]
) -> dict[str, Any] | None:
    expected = record.payload.get("parameter_binding")
    if expected is None:
        return None
    attempt = state.get("last_attempt") or {}
    if attempt.get("parameter_binding") != expected:
        return {"id": "parameter-binding-mismatch", "case_id": record.capture_id}
    control_id = attempt.get("control")
    controls = [
        item
        for item in attempt.get("controls", [])
        if isinstance(item, dict) and item.get("identifier") == control_id
    ]
    if len(controls) != 1:
        return {"id": "parameter-control-evidence", "case_id": record.capture_id}
    control = controls[0]
    minimum = control.get("min_value")
    maximum = control.get("max_value")
    requested = expected.get("value")
    if not all(isinstance(value, (int, float)) for value in (minimum, maximum, requested)):
        return {"id": "parameter-range-evidence", "case_id": record.capture_id}
    if requested < 0:
        if minimum >= 0:
            return {"id": "parameter-value-unrepresentable", "case_id": record.capture_id}
        expected_native = abs(float(requested)) * float(minimum)
    else:
        expected_native = float(requested) * float(maximum)
    observed = attempt.get("value")
    if not isinstance(observed, (int, float)) or abs(float(observed) - expected_native) > 1e-6:
        return {
            "id": "parameter-native-value-mismatch",
            "case_id": record.capture_id,
            "expected": expected_native,
            "actual": observed,
        }
    return None


def validate_chain(
    queue_path: Path,
    capture_root: Path,
    *,
    ui_reference_root: Path | None = None,
    jobs_root: Path | None = None,
    latest_run_path: Path | None = None,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    raw_queue = json.loads(queue_path.read_text(encoding="utf-8"))
    queue = SamplingQueue.load(
        queue_path.resolve(), expected_reference_id=str(raw_queue["reference_id"])
    )
    issues: list[dict[str, Any]] = []
    ready = 0
    run_evidence_path: Path | None = None
    records = tuple(
        record
        for record in queue.records
        if not case_ids or record.capture_id in case_ids
    )
    if case_ids:
        missing_case_ids = case_ids - {record.capture_id for record in records}
        if missing_case_ids:
            raise ValueError(
                f"unknown capture case ids: {', '.join(sorted(missing_case_ids))}"
            )
    for record in records:
        layout = CaptureLayout(capture_root.resolve(), record.capture_id)
        if not layout.state_path.is_file():
            issues.append({"id": "missing-state", "case_id": record.capture_id})
            continue
        state = json.loads(layout.state_path.read_text(encoding="utf-8"))
        canonical = state.get("canonical") or {}
        if state.get("schema_version") != 2:
            issues.append({"id": "state-schema", "case_id": record.capture_id})
            continue
        if state.get("status") != "ready" or canonical.get("status") != "ready":
            issues.append(
                {
                    "id": "canonical-not-ready",
                    "case_id": record.capture_id,
                    "status": state.get("status"),
                }
            )
            continue
        attempt_id = str(canonical.get("attempt_id") or "")
        if not attempt_id or not layout.attempt_path(attempt_id).is_file():
            issues.append({"id": "missing-canonical-attempt", "case_id": record.capture_id})
            continue
        if record.kind.value == "ui":
            viewport = record.payload["viewport"]
            ui_state = str(record.payload["ui_state"])
            ui_dir = (ui_reference_root or Path()) / f"{viewport[0]}x{viewport[1]}"
            if not (ui_dir / f"{ui_state}.png").is_file() or not (
                ui_dir / f"{ui_state}.ax.json"
            ).is_file():
                issues.append({"id": "missing-ui-evidence", "case_id": record.capture_id})
                continue
        else:
            if not layout.metadata_path.is_file():
                issues.append({"id": "missing-metadata", "case_id": record.capture_id})
                continue
            metadata = json.loads(layout.metadata_path.read_text(encoding="utf-8"))
            native = metadata.get("native_export") or {}
            native_path = Path(str(native.get("path") or ""))
            if not native_path.is_file():
                issues.append({"id": "missing-native-export", "case_id": record.capture_id})
                continue
            if _sha256(native_path) != native.get("sha256"):
                issues.append({"id": "native-export-hash", "case_id": record.capture_id})
                continue
            binding_issue = _validate_parameter_binding(record, state)
            if binding_issue:
                issues.append(binding_issue)
                continue
        ready += 1

    run_evidence_paths: list[str] = []
    if latest_run_path:
        source_fingerprints = raw_queue.get("source_queue_fingerprints")
        if raw_queue.get("profile") == "exact-active-cohort":
            if not isinstance(source_fingerprints, list) or not source_fingerprints:
                issues.append({"id": "missing-cohort-source-fingerprints"})
                expected_fingerprints: list[str] = []
            else:
                expected_fingerprints = [str(item) for item in source_fingerprints]
            declared = set(expected_fingerprints)
            for record in raw_queue.get("records", []):
                if record.get("source_queue_fingerprint") not in declared:
                    issues.append(
                        {
                            "id": "cohort-record-source-fingerprint",
                            "case_id": record.get("case_id"),
                        }
                    )
            for fingerprint in expected_fingerprints:
                path, observed_latest = _matching_run_evidence(
                    latest_run_path, fingerprint
                )
                if path is None:
                    issues.append(
                        {
                            "id": "missing-cohort-run-evidence",
                            "expected": fingerprint,
                            "latest_actual": observed_latest,
                            "latest_path": str(latest_run_path),
                        }
                    )
                else:
                    run_evidence_paths.append(str(path))
        else:
            run_evidence_path, observed_latest = _matching_run_evidence(
                latest_run_path, queue.fingerprint
            )
            if run_evidence_path is None:
                issues.append(
                    {
                        "id": "missing-queue-run-evidence",
                        "expected": queue.fingerprint,
                        "latest_actual": observed_latest,
                        "latest_path": str(latest_run_path),
                    }
                )
            else:
                run_evidence_paths.append(str(run_evidence_path))

    checked_jobs = 0
    if jobs_root and jobs_root.is_dir():
        for path in sorted(jobs_root.glob("*.json")):
            job = json.loads(path.read_text(encoding="utf-8"))
            checked_jobs += 1
            if job.get("status") in {"succeeded", "completed"}:
                missing = set(job.get("requested_models", [])) - set(
                    job.get("completed_models", {})
                )
                if missing:
                    issues.append(
                        {"id": "incomplete-job", "job_id": job.get("id"), "models": sorted(missing)}
                    )
                for output in job.get("completed_models", {}).values():
                    for result in output.values():
                        if not isinstance(result, dict) or not result.get("artifact_path"):
                            continue
                        artifact = jobs_root.parents[1] / "cache" / "inference" / result["artifact_path"]
                        if not artifact.is_file() or _sha256(artifact) != result.get("artifact_sha256"):
                            issues.append(
                                {"id": "job-artifact-integrity", "job_id": job.get("id"), "path": str(artifact)}
                            )
    return {
        "reference_id": queue.reference_id,
        "queue_fingerprint": queue.fingerprint,
        "run_evidence": run_evidence_paths[0] if len(run_evidence_paths) == 1 else None,
        "run_evidence_paths": run_evidence_paths,
        "record_count": len(records),
        "canonical_ready": ready,
        "checked_jobs": checked_jobs,
        "issue_count": len(issues),
        "status": "passed" if not issues else "blocked",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--jobs-root", type=Path, default=ROOT / "data/jobs/inference")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    queue_path = (args.queue or profile.diagnostics_root / "sampling-queue.json").resolve()
    report = validate_chain(
        queue_path,
        profile.capture_root,
        ui_reference_root=profile.ui_reference_root,
        jobs_root=args.jobs_root.resolve(),
        latest_run_path=(
            None
            if args.case_ids
            else profile.diagnostics_root / "sampling-queue-run-latest.json"
        ),
        case_ids=set(args.case_ids or []),
    )
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
