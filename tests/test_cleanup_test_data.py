import json
from pathlib import Path

from scripts.cleanup_test_data import apply_plan, build_plan


def _write_state(path: Path, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status}), encoding="utf-8")


def test_cleanup_removes_only_derived_and_transient_paths(tmp_path: Path) -> None:
    test_data = tmp_path / "test_data"
    profile = test_data / "outputs" / "luminar-1.28.0-23071"
    diagnostics = profile / "diagnostics"
    captures = profile / "captures"

    workspace = diagnostics / "candidate-outputs" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "upload.png").write_bytes(b"workspace")
    candidate = diagnostics / "candidate-outputs" / "case-1" / "export.png"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"candidate")
    unrelated_workspace = diagnostics / "model-conversion-artifacts" / "workspace"
    unrelated_workspace.mkdir(parents=True)
    (unrelated_workspace / "model.onnx").write_bytes(b"model")

    ready_staging = captures / "staging" / "ready-case"
    ready_staging.mkdir(parents=True)
    (ready_staging / "stable-001.png").write_bytes(b"old-ready")
    _write_state(captures / "state" / "ready-case.json", "ready")

    failed_staging = captures / "staging" / "failed-case"
    failed_staging.mkdir(parents=True)
    for index in range(1, 5):
        (failed_staging / f"stable-{index:03d}.png").write_bytes(
            str(index).encode()
        )
    _write_state(captures / "state" / "failed-case.json", "failed")

    metadata_file = test_data / ".DS_Store"
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.write_bytes(b"finder")

    plan = build_plan(test_data, profile)
    assert plan["counts"] == {
        "workspace_directories": 1,
        "stale_stability_files": 2,
        "metadata_files": 1,
    }

    apply_plan(plan)

    assert not workspace.exists()
    assert candidate.is_file()
    assert unrelated_workspace.is_dir()
    assert not (ready_staging / "stable-001.png").exists()
    assert not (failed_staging / "stable-001.png").exists()
    assert (failed_staging / "stable-002.png").is_file()
    assert (failed_staging / "stable-004.png").is_file()
    assert not metadata_file.exists()
