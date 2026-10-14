"""Prepare one fail-closed catalog fixture for formal UI evidence capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import create_app
from configs.reference import load_reference_catalog
from scripts.seed_ui_validation_catalog import validation_images
from scripts.validate_luminar_catalog_schema import validate as validate_catalog_schema


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(records: list[dict[str, Any]]) -> str:
    semantic_records = [
        {
            "relative_path": record["relative_path"],
            "source_sha256": record["source_sha256"],
            "size_bytes": record["size_bytes"],
        }
        for record in records
    ]
    payload = json.dumps(
        semantic_records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def prepare_fixture(
    *,
    dataset: Path,
    data_root: Path,
    expected_count: int,
    collection: str,
) -> dict[str, Any]:
    dataset = dataset.resolve()
    data_root = data_root.resolve()
    if data_root.exists() and any(data_root.iterdir()):
        raise RuntimeError(f"UI evidence data root is not empty: {data_root}")

    images = validation_images(dataset)
    if len(images) != expected_count:
        raise RuntimeError(
            f"UI evidence dataset count mismatch: {len(images)} != {expected_count}"
        )
    source_hashes = [_sha256(path) for path in images]
    if len(set(source_hashes)) != len(images):
        raise RuntimeError("UI evidence dataset contains duplicate image content")

    editor = create_app(data_root=data_root).state.editor
    imported: list[dict[str, Any]] = []
    for path, source_sha256 in zip(images, source_hashes, strict=True):
        result = editor.upload_asset(
            path.name,
            path.read_bytes(),
            collection=collection,
        )
        imported.append(
            {
                "relative_path": path.relative_to(dataset).as_posix(),
                "filename": path.name,
                "source_sha256": source_sha256,
                "size_bytes": path.stat().st_size,
                "asset_id": result["asset_id"],
                "project_id": result["project_id"],
            }
        )

    catalog = editor.catalog(view="all", query="", sort="name")
    catalog_asset_ids = {str(record["asset_id"]) for record in catalog["records"]}
    imported_asset_ids = {str(record["asset_id"]) for record in imported}
    if catalog["count"] != expected_count:
        raise RuntimeError(
            f"UI evidence catalog count mismatch: {catalog['count']} != {expected_count}"
        )
    if catalog_asset_ids != imported_asset_ids:
        raise RuntimeError("UI evidence catalog assets differ from imported fixtures")

    sqlite_files = sorted(
        (
            {
                "relative_path": path.relative_to(data_root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in data_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}
        ),
        key=lambda record: str(record["relative_path"]),
    )
    schema = validate_catalog_schema()
    records = sorted(imported, key=lambda record: str(record["relative_path"]))
    return {
        "version": "1.0",
        "dataset": str(dataset),
        "data_root": str(data_root),
        "collection": collection,
        "expected_count": expected_count,
        "catalog_count": catalog["count"],
        "unique_source_hash_count": len(set(source_hashes)),
        "fixture_fingerprint": _fingerprint(records),
        "records": records,
        "sqlite_files": sqlite_files,
        "catalog_schema": {
            "passed": schema["passed"],
            "schema_version": schema["schema_version"],
            "object_count": schema["schema_objects"],
            "table_count": schema["tables"],
            "schema_hash": schema["structure_sha256"],
            "compatibility_layers": schema["compatibility_layers"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "test_data/parity/inputs/summer-outdoor",
    )
    parser.add_argument(
        "--reference-config",
        type=Path,
        default=ROOT / "configs/reference.yaml",
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=46)
    parser.add_argument("--collection", default="夏日户外拍照")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    data_root = args.data_root.resolve()
    allowed_root = (ROOT / "test_data/outputs").resolve()
    if allowed_root not in data_root.parents:
        raise ValueError(f"UI evidence data root must be a child of {allowed_root}")

    report = prepare_fixture(
        dataset=args.dataset,
        data_root=data_root,
        expected_count=args.expected_count,
        collection=args.collection,
    )
    output = (
        args.output
        or profile.diagnostics_root / "ui-evidence-fixture-manifest.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "catalog_count": report["catalog_count"],
                "unique_source_hash_count": report["unique_source_hash_count"],
                "fixture_fingerprint": report["fixture_fingerprint"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
