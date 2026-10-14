import json
from pathlib import Path

from scripts.validate_invalid_references import validate_registry


def test_current_invalid_reference_registry_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    report = validate_registry(
        root / "configs/parity/invalid-references.json",
        reference_config=root / "configs/reference.yaml",
    )

    assert report["gate"] == "passed"
    assert report["record_count"] == 0
    assert report["confirmed_invalid"] == 0
    assert report["suspected_invalid"] == 0
    assert report["policy"] == "registry-never-exempts-required-gates"


def test_invalid_reference_registry_fails_closed_for_broad_action(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "configs/parity/invalid-references.json").read_text(encoding="utf-8")
    )
    queue = json.loads(
        (
            root
            / "test_data/outputs/luminar-1.28.1-23487/diagnostics/sampling-queue.json"
        ).read_text(encoding="utf-8")
    )
    payload["records"] = [
        {
            "id": "invalid-policy-test",
            "capture_id": queue["records"][0]["id"],
            "status": "suspected-invalid",
            "reason_code": "test-only",
            "artifact": "diagnostics/sampling-queue.json",
            "evidence": "diagnostics/sampling-queue.json",
            "allowed_action": "ignore-gate",
            "blocks": ["sampling-queue-evidence"],
        }
    ]
    registry = tmp_path / "invalid-references.json"
    registry.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_registry(
        registry,
        reference_config=root / "configs/reference.yaml",
    )

    assert report["gate"] == "blocked"
    assert "record[0]:invalid-allowed-action" in report["errors"]
