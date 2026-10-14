import json
from pathlib import Path

from PIL import Image

from scripts.build_validation_manifest import run as build_manifest
from scripts.validate_dataset_freshness import run


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_dataset_freshness_requires_same_fingerprint_and_case_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source / "sample.jpg")
    snapshot = tmp_path / "snapshot"
    manifest_path = tmp_path / "manifest.json"
    build_manifest(source, manifest_path, snapshot)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fingerprint = manifest["dataset_fingerprint"]
    record = manifest["records"][0]
    matrix = _write(tmp_path / "matrix.json", {"dataset_fingerprint": fingerprint})
    cases = _write(
        tmp_path / "cases.json",
        {
            "dataset_fingerprint": fingerprint,
            "cases": [
                {
                    "case_id": "case",
                    "input": {"path": record["path"], "sha256": record["sha256"]},
                }
            ],
        },
    )
    queue = _write(tmp_path / "queue.json", {"dataset_fingerprint": fingerprint})

    report = run(source, snapshot, manifest_path, matrix, cases, queue)

    assert report["gate"] == "passed"

    _write(queue, {"dataset_fingerprint": "old"})
    report = run(source, snapshot, manifest_path, matrix, cases, queue)

    assert report["gate"] == "blocked"
    assert report["issues"]["mismatched_artifacts"] == ["queue"]
