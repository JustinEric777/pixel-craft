from pathlib import Path

from PIL import Image

from scripts.luminar_capture.export_watcher import (
    snapshot_export_files,
    wait_for_new_stable_export,
)


def test_snapshot_export_files_ignores_non_images(tmp_path: Path) -> None:
    image = tmp_path / "case.jpeg"
    Image.new("RGB", (2, 2), "red").save(image)
    (tmp_path / "report.json").write_text("{}", encoding="utf-8")

    snapshot = snapshot_export_files(tmp_path)

    assert set(snapshot) == {image.resolve()}


def test_wait_for_new_export_accepts_actual_supported_extension(tmp_path: Path) -> None:
    before = snapshot_export_files(tmp_path)
    exported = tmp_path / "case.jpg"
    Image.new("RGB", (2, 2), "red").save(exported)

    result = wait_for_new_stable_export(
        tmp_path,
        stem="case",
        before=before,
        timeout_seconds=0.2,
        stable_seconds=0,
        poll_seconds=0.01,
    )

    assert result == exported.resolve()


def test_wait_for_new_export_requires_new_or_changed_file(tmp_path: Path) -> None:
    existing = tmp_path / "case.png"
    Image.new("RGB", (2, 2), "red").save(existing)
    before = snapshot_export_files(tmp_path)
    Image.new("RGB", (3, 2), "blue").save(existing)

    result = wait_for_new_stable_export(
        tmp_path,
        stem="case",
        before=before,
        timeout_seconds=0.2,
        stable_seconds=0,
        poll_seconds=0.01,
    )

    assert result == existing.resolve()


def test_wait_for_new_export_rejects_truncated_image(tmp_path: Path) -> None:
    exported = tmp_path / "case.png"
    exported.write_bytes(b"not-a-complete-image")

    try:
        wait_for_new_stable_export(
            tmp_path,
            stem="case",
            before={},
            timeout_seconds=0.04,
            stable_seconds=0,
            poll_seconds=0.01,
        )
    except TimeoutError:
        pass
    else:
        raise AssertionError("a truncated image must not be treated as a completed export")
