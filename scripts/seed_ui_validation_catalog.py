"""Build an isolated web catalog from the active UI validation dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import create_app
from configs.reference import load_reference_catalog

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def validation_images(root: Path) -> list[Path]:
    directories = sorted({path.parent for path in root.rglob("*") if path.is_file()})
    # Luminar shows the newest imported folder first while retaining filename
    # order inside each folder. Import each folder in reverse filename order so
    # an added-at-descending catalog reproduces that stable batch ordering.
    return [
        path
        for directory in directories
        for path in sorted(
            (
                item
                for item in directory.iterdir()
                if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES
            ),
            reverse=True,
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "test_data" / "夏日户外拍照"
    )
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs" / "reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove only the resolved diagnostics/ui-workspace before importing",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    data_root = (
        args.data_root or profile.diagnostics_root / "ui-workspace"
    ).resolve()
    allowed_root = (ROOT / "test_data" / "outputs").resolve()
    if data_root != allowed_root and allowed_root not in data_root.parents:
        raise ValueError(f"UI validation data root must stay under {allowed_root}")
    dataset = args.dataset.resolve()
    images = validation_images(dataset)
    if not images:
        raise FileNotFoundError(f"validation dataset contains no images: {dataset}")
    if args.reset and data_root.exists():
        shutil.rmtree(data_root)

    editor = create_app(data_root=data_root).state.editor
    existing = {
        str(item["asset_id"])
        for item in editor.catalog(view="all", query="", sort="name")["records"]
    }
    imported = 0
    expected_asset_ids: set[str] = set()
    for path in images:
        content = path.read_bytes()
        asset_id = hashlib.sha256(content).hexdigest()[:24]
        expected_asset_ids.add(asset_id)
        if asset_id in existing:
            continue
        result = editor.upload_asset(path.name, content)
        existing.add(result["asset_id"])
        imported += 1
    catalog = editor.catalog(view="all", query="", sort="name")
    print(
        json.dumps(
            {
                "dataset": str(dataset),
                "data_root": str(data_root),
                "dataset_images": len(images),
                "catalog_records": catalog["count"],
                "imported": imported,
            },
            ensure_ascii=False,
        )
    )
    return 0 if catalog["count"] == len(expected_asset_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
