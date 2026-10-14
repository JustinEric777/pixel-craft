from __future__ import annotations

import json
from pathlib import Path

from scripts.build_absolute_alignment_worklist import build_worklist


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_build_worklist_keeps_distinct_gate_responsibilities(tmp_path: Path) -> None:
    scope = _write(
        tmp_path / "scope.json",
        {
            "issues": {
                "missing_exact_amount_anchors": ["face_ai"],
                "insufficient_holdout_inputs": ["face_ai"],
            }
        },
    )
    main = _write(
        tmp_path / "main.json",
        {
            "cases": [
                {
                    "case_id": "main-face",
                    "capability_id": "face_ai",
                    "status": "failed",
                    "metrics": {"mae": 0.04, "ssim": 0.97},
                },
                {"case_id": "main-pass", "status": "passed"},
            ]
        },
    )
    exact = _write(
        tmp_path / "exact.json",
        {"cases": [{"case_id": "exact-face", "capability_id": "face_ai", "status": "failed"}]},
    )
    ui_execution = _write(
        tmp_path / "ui-execution.json", {"issues": [{"id": "stale-frontend-build"}]}
    )
    ui_parity = _write(
        tmp_path / "ui-parity.json",
        {
            "issues": [{"id": "threshold-failure", "state": "edit"}],
            "records": [
                {"viewport": "4x3", "state": "catalog", "status": "failed"},
                {"viewport": "4x3", "state": "edit", "status": "passed"},
            ],
        },
    )
    interaction = _write(
        tmp_path / "interaction.json",
        {"issues": [{"id": "missing-execution", "contract": "preset"}]},
    )

    report = build_worklist(
        scope_path=scope,
        main_path=main,
        exact_path=exact,
        ui_execution_path=ui_execution,
        ui_parity_path=ui_parity,
        interaction_path=interaction,
    )

    assert report["gate"] == "blocked"
    assert report["item_count"] == 8
    assert report["summary"]["by_gate"] == {
        "absolute-scope-coverage": 2,
        "exact-incremental-parity": 1,
        "interaction-execution": 1,
        "output-parity": 1,
        "ui-execution-evidence": 1,
        "ui-parity": 2,
    }
    assert len({item["id"] for item in report["items"]}) == 8
    assert all(len(source["sha256"]) == 64 for source in report["sources"].values())


def test_build_worklist_passes_when_all_evidence_has_no_failures(tmp_path: Path) -> None:
    sources = {
        name: _write(tmp_path / f"{name}.json", {"issues": {}} if name == "scope" else {"cases": []} if name in {"main", "exact"} else {"issues": []})
        for name in ("scope", "main", "exact", "ui_execution", "ui_parity", "interaction")
    }

    report = build_worklist(
        scope_path=sources["scope"],
        main_path=sources["main"],
        exact_path=sources["exact"],
        ui_execution_path=sources["ui_execution"],
        ui_parity_path=sources["ui_parity"],
        interaction_path=sources["interaction"],
    )

    assert report["gate"] == "passed"
    assert report["items"] == []
