"""Compare two frozen Native persistence snapshots without mutating either tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

SQLITE_HEADER = b"SQLite format 3\x00"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_snapshot(path: Path) -> dict[str, Any] | None:
    with path.open("rb") as handle:
        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            return None
    connection = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        schema_rows = connection.execute(
            "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        tables: dict[str, Any] = {}
        for object_type, name, _, _ in schema_rows:
            if object_type != "table":
                continue
            quoted = '"' + str(name).replace('"', '""') + '"'
            row_hashes = []
            for row in connection.execute(f"SELECT * FROM {quoted}"):
                encoded = json.dumps(row, ensure_ascii=False, default=repr, separators=(",", ":"))
                row_hashes.append(hashlib.sha256(encoded.encode()).hexdigest())
            tables[str(name)] = {
                "row_count": len(row_hashes),
                "row_hashes": sorted(row_hashes),
            }
        schema_blob = json.dumps(schema_rows, ensure_ascii=False, separators=(",", ":"))
        return {
            "schema_sha256": hashlib.sha256(schema_blob.encode()).hexdigest(),
            "object_count": len(schema_rows),
            "tables": tables,
        }
    finally:
        connection.close()


def snapshot(root: Path) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        files[relative] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256(path),
            "sqlite": sqlite_snapshot(path),
        }
    return {"root": str(root.resolve()), "file_count": len(files), "files": files}


def compare(before: Path, after: Path) -> dict[str, Any]:
    left = snapshot(before)
    right = snapshot(after)
    left_files = left["files"]
    right_files = right["files"]
    added = sorted(set(right_files) - set(left_files))
    removed = sorted(set(left_files) - set(right_files))
    changed = sorted(
        path
        for path in set(left_files) & set(right_files)
        if left_files[path]["sha256"] != right_files[path]["sha256"]
    )
    sqlite_deltas: dict[str, Any] = {}
    for path in sorted(set(left_files) | set(right_files)):
        left_db = left_files.get(path, {}).get("sqlite")
        right_db = right_files.get(path, {}).get("sqlite")
        if not left_db and not right_db:
            continue
        table_deltas: dict[str, Any] = {}
        left_tables = (left_db or {}).get("tables", {})
        right_tables = (right_db or {}).get("tables", {})
        for table in sorted(set(left_tables) | set(right_tables)):
            left_rows = Counter(left_tables.get(table, {}).get("row_hashes", []))
            right_rows = Counter(right_tables.get(table, {}).get("row_hashes", []))
            added_rows = list((right_rows - left_rows).elements())
            removed_rows = list((left_rows - right_rows).elements())
            if added_rows or removed_rows:
                table_deltas[table] = {
                    "before_count": sum(left_rows.values()),
                    "after_count": sum(right_rows.values()),
                    "added_row_hashes": sorted(added_rows),
                    "removed_row_hashes": sorted(removed_rows),
                }
        sqlite_deltas[path] = {
            "before_schema_sha256": (left_db or {}).get("schema_sha256"),
            "after_schema_sha256": (right_db or {}).get("schema_sha256"),
            "table_deltas": table_deltas,
        }
    return {
        "version": "1.0",
        "read_only": True,
        "before": left,
        "after": right,
        "files_added": added,
        "files_removed": removed,
        "files_changed": changed,
        "sqlite_deltas": sqlite_deltas,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.before.is_dir() or not args.after.is_dir():
        parser.error("--before and --after must be frozen snapshot directories")
    report = compare(args.before, args.after)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added": len(report["files_added"]), "removed": len(report["files_removed"]), "changed": len(report["files_changed"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
