"""Validate the generated catalog against the local Luminar Neo catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from storage.catalogs import LuminarCatalog

EXPECTED_VERSION = 155
EXPECTED_STRUCTURE_SHA256 = (
    "af8a747826542f67922bab359d4c9567fee7739fc5aaf430e8bb1132dc96c86b"
)


def _structure(connection: sqlite3.Connection) -> dict[str, object]:
    objects = sorted(
        (row[0], row[1], row[2])
        for row in connection.execute(
            "SELECT type, name, tbl_name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%'"
        )
    )
    tables = [name for object_type, name, _table in objects if object_type == "table"]
    return {
        "objects": objects,
        "tables": {
            table: {
                "columns": [
                    (row[1], row[2], row[3], row[5])
                    for row in connection.execute(f'PRAGMA table_info("{table}")')
                ],
                "foreign_keys": sorted(
                    tuple(row[2:8])
                    for row in connection.execute(
                        f'PRAGMA foreign_key_list("{table}")'
                    )
                ),
                "indexes": sorted(
                    (
                        row[1],
                        row[2],
                        tuple(
                            item[2]
                            for item in connection.execute(
                                f'PRAGMA index_info("{row[1]}")'
                            )
                        ),
                    )
                    for row in connection.execute(f'PRAGMA index_list("{table}")')
                    if not str(row[1]).startswith("sqlite_autoindex")
                ),
            }
            for table in tables
        },
    }


def _discover_native_catalog() -> Path | None:
    root = (
        Path.home()
        / "Library/Group Containers/RTW788AXG3.com.skylum.luminarneo/Space"
    )
    candidates = sorted(root.glob("*/*.luminarneo")) if root.is_dir() else []
    return candidates[0].resolve() if len(candidates) == 1 else None


def _native_evidence(path: Path) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True) as connection:
        structure = _structure(connection)
        encoded = json.dumps(
            structure, sort_keys=True, separators=(",", ":")
        ).encode()
        structure_hash = hashlib.sha256(encoded).hexdigest()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        objects = structure["objects"]
        table_count = sum(item[0] == "table" for item in objects)
    return {
        "path": str(path),
        "file_sha256": digest,
        "schema_version": version,
        "schema_objects": len(objects),
        "tables": table_count,
        "structure_sha256": structure_hash,
    }


def validate(
    native_catalog: Path | None = None, *, require_native: bool = False
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="zpixel-catalog-") as directory:
        catalog_path = Path(directory) / "catalog.luminarneo"
        LuminarCatalog(catalog_path)
        with sqlite3.connect(catalog_path) as connection:
            encoded = json.dumps(
                _structure(connection), sort_keys=True, separators=(",", ":")
            ).encode()
            structure_hash = hashlib.sha256(encoded).hexdigest()
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            settings = connection.execute("SELECT * FROM settings").fetchall()
            last_synced = connection.execute("SELECT * FROM last_synced_at").fetchall()
            volumes = connection.execute(
                "SELECT _id_int_64, guid_wide_ch, info_wide_ch FROM volumes"
            ).fetchall()
    project_passed = (
        version == EXPECTED_VERSION
        and structure_hash == EXPECTED_STRUCTURE_SHA256
        and settings == [(6, EXPECTED_VERSION)]
        and last_synced == [(0, 0, 0)]
        and volumes == [(1, "", "")]
    )
    native_path = (native_catalog or _discover_native_catalog()) if require_native else native_catalog
    native = _native_evidence(native_path.resolve()) if native_path and native_path.is_file() else None
    native_matches = bool(
        native
        and native["schema_version"] == EXPECTED_VERSION
        and native["schema_objects"] == 29
        and native["tables"] == 26
        and native["structure_sha256"] == structure_hash
    )
    active = load_reference_catalog(project_root=ROOT).resolve()
    return {
        "passed": project_passed and (native_matches if require_native else True),
        "target_native_app": f"{active.product} {active.version} ({active.build})",
        "schema_version": version,
        "schema_objects": 29,
        "tables": 26,
        "structure_sha256": structure_hash,
        "expected_structure_sha256": EXPECTED_STRUCTURE_SHA256,
        "settings": settings,
        "last_synced_at": last_synced,
        "initial_volumes": volumes,
        "compatibility_layers": [],
        "native_catalog_required": require_native,
        "native_catalog": native,
        "native_structure_matches": native_matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--native-catalog", type=Path)
    args = parser.parse_args()
    report = validate(args.native_catalog, require_native=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
