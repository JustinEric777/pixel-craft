import sqlite3
from pathlib import Path

from scripts.capture_native_persistence_delta import compare


def create_database(path: Path, values: list[str]) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE state(id INTEGER PRIMARY KEY, value TEXT)")
    connection.executemany("INSERT INTO state(value) VALUES (?)", [(value,) for value in values])
    connection.commit()
    connection.close()


def test_reports_files_and_sqlite_row_delta_without_writes(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    create_database(before / "catalog.db", ["one"])
    create_database(after / "catalog.db", ["one", "two"])
    (after / "resource.bin").write_bytes(b"resource")

    report = compare(before, after)

    assert report["read_only"] is True
    assert report["files_added"] == ["resource.bin"]
    delta = report["sqlite_deltas"]["catalog.db"]["table_deltas"]["state"]
    assert delta["before_count"] == 1
    assert delta["after_count"] == 2
    assert len(delta["added_row_hashes"]) == 1
