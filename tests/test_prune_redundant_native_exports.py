import json
from pathlib import Path

from scripts.prune_redundant_native_exports import apply_plan, build_plan


def test_prune_keeps_only_ready_canonical_export_and_removes_staging(
    tmp_path: Path,
) -> None:
    captures = tmp_path / "captures"
    exports = tmp_path / "native-exports"
    (captures / "state").mkdir(parents=True)
    (captures / "staging" / "case").mkdir(parents=True)
    exports.mkdir()
    canonical = exports / "case--ready.jpeg"
    duplicate = exports / "case--failed.jpeg"
    canonical.write_bytes(b"ready")
    duplicate.write_bytes(b"failed")
    (captures / "staging" / "case" / "rejected-export.jpeg").write_bytes(b"bad")
    (captures / "state" / "case.json").write_text(
        json.dumps(
            {
                "canonical": {"status": "ready", "attempt_id": "ready"},
                "last_attempt": {
                    "attempt_id": "ready",
                    "export_path": str(canonical),
                },
            }
        ),
        encoding="utf-8",
    )

    plan = build_plan(captures, exports)
    assert plan["canonical_export_count"] == 1
    assert plan["redundant_exports"] == [str(duplicate)]
    assert len(plan["transient_paths"]) == 1

    apply_plan(captures, exports, plan)

    assert canonical.is_file()
    assert not duplicate.exists()
    assert not (captures / "staging" / "case").exists()
