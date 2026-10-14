from pathlib import Path

from scripts.build_exact_validation_fixtures import build_fixtures


def test_exact_validation_fixtures_are_reproducible(tmp_path: Path) -> None:
    first = build_fixtures(tmp_path)
    second = build_fixtures(tmp_path)

    assert first == second
    assert {record["id"] for record in first["fixtures"]} == {
        "night-lights",
        "sensor-noise",
    }
    assert all(len(record["sha256"]) == 64 for record in first["fixtures"])
