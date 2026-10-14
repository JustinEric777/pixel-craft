from pathlib import Path

import pytest
from PIL import Image

from scripts.prepare_ui_evidence_fixture import prepare_fixture


def _image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (16, 12), color).save(path)


def test_prepare_fixture_imports_unique_images_once(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _image(dataset / "a.png", (255, 0, 0))
    _image(dataset / "b.png", (0, 0, 255))

    report = prepare_fixture(
        dataset=dataset,
        data_root=tmp_path / "data",
        expected_count=2,
        collection="fixture",
    )

    assert report["catalog_count"] == 2
    assert report["unique_source_hash_count"] == 2
    assert len(report["records"]) == 2
    assert report["catalog_schema"]["compatibility_layers"] == []


def test_prepare_fixture_rejects_non_empty_data_root(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _image(dataset / "a.png", (255, 0, 0))
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "existing.txt").write_text("occupied", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not empty"):
        prepare_fixture(
            dataset=dataset,
            data_root=data_root,
            expected_count=1,
            collection="fixture",
        )


def test_prepare_fixture_rejects_duplicate_content(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _image(dataset / "a.png", (255, 0, 0))
    (dataset / "b.png").write_bytes((dataset / "a.png").read_bytes())

    with pytest.raises(RuntimeError, match="duplicate image content"):
        prepare_fixture(
            dataset=dataset,
            data_root=tmp_path / "data",
            expected_count=2,
            collection="fixture",
        )
