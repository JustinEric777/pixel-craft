import importlib.util
import json
from pathlib import Path

from PIL import Image

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/build_validation_manifest.py"
_SPEC = importlib.util.spec_from_file_location("build_validation_manifest", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_manifest = _MODULE.run
check_manifest = _MODULE.check


def test_validation_manifest_records_image_contract(tmp_path: Path) -> None:
    source = tmp_path / "20个原图"
    source.mkdir()
    Image.new("RGB", (13, 9), (20, 40, 60)).save(source / "样本 01.jpg")
    output = tmp_path / "validation.json"

    result = build_manifest(source, output)

    assert result["count"] == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    record = payload["records"][0]
    assert record["width"] == 13
    assert record["height"] == 9
    assert record["format"] == "JPEG"
    assert len(record["sha256"]) == 64
    assert len(payload["dataset_fingerprint"]) == 64


def test_validation_manifest_can_freeze_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "nested" / "sample.jpg"
    image.parent.mkdir()
    Image.new("RGB", (8, 6), (10, 20, 30)).save(image)
    snapshot = tmp_path / "snapshot"
    output = tmp_path / "validation.json"

    build_manifest(source, output, snapshot)
    image.unlink()

    record = json.loads(output.read_text(encoding="utf-8"))["records"][0]
    assert Path(record["path"]).is_file()
    assert Path(record["path"]).is_relative_to(snapshot)


def test_validation_manifest_prunes_deleted_snapshot_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    retained = source / "retained.jpg"
    removed = source / "removed.jpg"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(retained)
    Image.new("RGB", (8, 6), (40, 50, 60)).save(removed)
    snapshot = tmp_path / "snapshot"
    output = tmp_path / "validation.json"

    build_manifest(source, output, snapshot)
    removed.unlink()
    result = build_manifest(source, output, snapshot)

    assert result["count"] == 1
    assert result["pruned_count"] == 1
    assert (snapshot / "retained.jpg").is_file()
    assert not (snapshot / "removed.jpg").exists()


def test_validation_manifest_check_detects_source_and_snapshot_drift(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    image = source / "sample.jpg"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(image)
    snapshot = tmp_path / "snapshot"
    output = tmp_path / "validation.json"
    build_manifest(source, output, snapshot)

    assert check_manifest(source, output, snapshot)["status"] == "fresh"

    Image.new("RGB", (8, 6), (40, 50, 60)).save(image)
    report = check_manifest(source, output, snapshot)

    assert report["status"] == "stale"
    assert report["source_diff"]["changed"] == ["sample.jpg"]
