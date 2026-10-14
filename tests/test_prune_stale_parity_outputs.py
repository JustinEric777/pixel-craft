import os
from pathlib import Path

from scripts.prune_stale_parity_outputs import build_plan


def test_build_plan_keeps_reports_newer_than_the_active_cases(tmp_path: Path) -> None:
    candidates = tmp_path / "candidate-outputs"
    diagnostics = tmp_path / "diagnostics"
    candidates.mkdir()
    diagnostics.mkdir()
    (candidates / "active-case").mkdir()
    (candidates / "old-case").mkdir()
    (candidates / "workspace").mkdir()
    stale_report = diagnostics / "preset-validation.json"
    fresh_report = diagnostics / "dataset-freshness.json"
    stale_report.write_text("{}", encoding="utf-8")
    fresh_report.write_text("{}", encoding="utf-8")
    os.utime(stale_report, (10, 10))
    os.utime(fresh_report, (30, 30))

    plan = build_plan(
        (candidates,),
        diagnostics,
        {"active-case"},
        minimum_report_mtime=20,
    )

    assert plan["candidate_directories"] == [str((candidates / "old-case").resolve())]
    assert plan["workspace_directories"] == [str((candidates / "workspace").resolve())]
    assert plan["report_files"] == [str(stale_report.resolve())]
