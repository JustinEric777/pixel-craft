from __future__ import annotations

import os
from pathlib import Path

from scripts.deduplicate_sampling_storage import audit_storage


def test_audit_does_not_replace_duplicates_with_hardlinks(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("same", encoding="utf-8")
    second.write_text("same", encoding="utf-8")

    report = audit_storage(tmp_path, detach_hardlinks=False)

    assert report["duplicate_count"] == 1
    assert report["shared_inode_group_count"] == 0
    assert first.stat().st_ino != second.stat().st_ino


def test_detach_hardlinks_prevents_cross_file_mutation(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("original", encoding="utf-8")
    os.link(first, second)

    report = audit_storage(tmp_path, detach_hardlinks=True)
    second.write_text("changed", encoding="utf-8")

    assert report["shared_inode_group_count"] == 1
    assert report["detached_path_count"] == 1
    assert first.stat().st_ino != second.stat().st_ino
    assert first.read_text(encoding="utf-8") == "original"
