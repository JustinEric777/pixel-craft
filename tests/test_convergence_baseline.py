import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_convergence_baseline import build_baseline


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_convergence_baseline_freezes_failures_and_hashes(tmp_path: Path) -> None:
    diagnostics = tmp_path / "diagnostics"
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    reference.write_bytes(b"reference")
    candidate.write_bytes(b"candidate")
    _write(
        diagnostics / "quality-gates-exact-final.json",
        {
            "reference_id": "reference",
            "gate_count": 3,
            "passed": 1,
            "failed": 1,
            "optional_failed": 1,
            "status": "blocked",
            "failed_gates": ["output-parity"],
            "optional_failed_gates": ["inventory"],
        },
    )
    failed_case = {
        "case_id": "case",
        "capability_id": "effect",
        "status": "failed",
        "metrics": {
            "mae": 0.1,
            "ssim": 0.9,
            "shape_match": True,
            "reference": str(reference),
            "candidate": str(candidate),
        },
    }
    _write(
        diagnostics / "parity-report.json",
        {
            "reference_id": "reference",
            "case_count": 1,
            "passed": 0,
            "failed": 1,
            "pending": 0,
            "cases": [failed_case],
        },
    )
    _write(
        diagnostics / "exact-incremental-parity.json",
        {
            "reference_id": "reference",
            "case_count": 1,
            "passed": 1,
            "failed": 0,
            "pending": 0,
            "cases": [],
        },
    )
    _write(
        diagnostics / "ui-parity.json",
        {
            "reference_id": "reference",
            "case_count": 1,
            "passed": 0,
            "failed": 1,
            "pending": 0,
            "records": [
                {"state": "edit", "status": "failed", "metrics": {"mae": 0.2}}
            ],
        },
    )
    _write(
        diagnostics / "ui-execution-evidence.json",
        {
            "reference_id": "reference",
            "expected": 1,
            "executed": 1,
            "passed": 0,
            "issue_count": 1,
            "gate": "blocked",
        },
    )
    _write(
        diagnostics / "interaction-execution.json",
        {
            "reference_id": "reference",
            "contract_count": 2,
            "passed": 0,
            "issue_count": 4,
        },
    )
    _write(
        diagnostics / "multi-image-workflow-smoke.json",
        {
            "reference_id": "reference",
            "count": 3,
            "passed": 2,
            "failed": 1,
            "gate": "blocked",
        },
    )
    _write(
        diagnostics / "test-data-cleanup-final-postcheck.json",
        {"path_count": 0, "reclaimable_bytes": 0},
    )

    baseline, registry = build_baseline(tmp_path)

    assert baseline["quality_gates"]["required_failed"] == 1
    assert baseline["domains"]["ui_execution"]["passed"] == 0
    assert baseline["domains"]["interaction_execution"]["missing"] == 2
    assert baseline["domains"]["multi_image"]["failed"] == 1
    assert baseline["failure_count"] == 2
    assert registry["failure_count"] == 2
    assert registry["failures"][0]["owner_batch"] is None
    assert registry["failures"][1]["owner_batch"] == "P3"
    assert registry["failures"][0]["reference"]["sha256"] == hashlib.sha256(
        b"reference"
    ).hexdigest()


def test_build_convergence_baseline_accepts_explicit_reports(tmp_path: Path) -> None:
    test_build_convergence_baseline_freezes_failures_and_hashes(tmp_path)
    custom = tmp_path / "current-quality.json"
    _write(
        custom,
        {
            "reference_id": "reference",
            "gate_count": 28,
            "passed": 21,
            "failed": 6,
            "optional_failed": 1,
            "status": "blocked",
        },
    )

    baseline, _ = build_baseline(
        tmp_path, report_paths={"quality_gates": custom}
    )

    assert baseline["quality_gates"]["passed"] == 21
    assert baseline["reports"]["quality_gates"]["path"] == str(custom.resolve())


def test_build_convergence_baseline_rejects_mixed_reference_ids(tmp_path: Path) -> None:
    test_build_convergence_baseline_freezes_failures_and_hashes(tmp_path)
    report = tmp_path / "diagnostics/ui-execution-evidence.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["reference_id"] = "other-reference"
    _write(report, payload)

    with pytest.raises(ValueError, match="do not match reference_id"):
        build_baseline(tmp_path)
