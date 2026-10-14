import json
from pathlib import Path

import pytest

from scripts.merge_interaction_raw_executions import merge


def write_raw(path: Path, identifier: str, *, build_hash: str = "a" * 64) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "2.0",
                "reference_id": "reference",
                "environment": {"build_hash": build_hash},
                "records": [{"id": identifier, "status": "passed"}],
            }
        ),
        encoding="utf-8",
    )


def test_merges_unique_records_from_one_environment(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_raw(first, "first")
    write_raw(second, "second")

    assert [item["id"] for item in merge([first, second])["records"]] == [
        "first",
        "second",
    ]


def test_rejects_mixed_frontend_hashes(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_raw(first, "first")
    write_raw(second, "second", build_hash="b" * 64)

    with pytest.raises(ValueError, match="environment mismatch"):
        merge([first, second])
