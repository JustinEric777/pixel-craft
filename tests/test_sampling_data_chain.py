from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_sampling_data_chain import _matching_run_evidence


def _write_run(path: Path, fingerprint: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"queue_fingerprint": fingerprint}), encoding="utf-8"
    )


def test_matching_run_evidence_prefers_matching_latest(tmp_path: Path) -> None:
    latest = tmp_path / "sampling-queue-run-latest.json"
    _write_run(latest, "smoke")
    _write_run(tmp_path / "sampling-runs" / "older.json", "smoke")

    path, observed_latest = _matching_run_evidence(latest, "smoke")

    assert path == latest
    assert observed_latest == "smoke"


def test_matching_run_evidence_finds_queue_specific_archive(tmp_path: Path) -> None:
    latest = tmp_path / "sampling-queue-run-latest.json"
    archived = tmp_path / "sampling-runs" / "smoke.json"
    _write_run(latest, "exact")
    _write_run(archived, "smoke")

    path, observed_latest = _matching_run_evidence(latest, "smoke")

    assert path == archived
    assert observed_latest == "exact"


def test_matching_run_evidence_reports_missing_fingerprint(tmp_path: Path) -> None:
    latest = tmp_path / "sampling-queue-run-latest.json"
    _write_run(latest, "exact")

    path, observed_latest = _matching_run_evidence(latest, "smoke")

    assert path is None
    assert observed_latest == "exact"
