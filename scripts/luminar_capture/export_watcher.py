"""Wait for a Luminar export to finish writing before it is imported."""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

SUPPORTED_EXPORT_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _is_complete_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, SyntaxError, ValueError):
        return False


def snapshot_export_files(directory: Path) -> dict[Path, tuple[int, int]]:
    """Record supported exports directly inside one configured output directory."""

    if not directory.is_dir():
        return {}
    snapshot: dict[Path, tuple[int, int]] = {}
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXPORT_SUFFIXES:
            continue
        stat = path.stat()
        snapshot[path.resolve()] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def wait_for_stable_file(
    path: Path,
    *,
    timeout_seconds: float = 120.0,
    stable_seconds: float = 0.4,
    poll_seconds: float = 0.2,
) -> Path:
    deadline = time.monotonic() + timeout_seconds
    previous: tuple[int, int] | None = None
    stable_since: float | None = None
    while time.monotonic() < deadline:
        if path.is_file():
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            if stat.st_size > 0 and signature == previous:
                stable_since = stable_since or time.monotonic()
                if (
                    time.monotonic() - stable_since >= stable_seconds
                    and _is_complete_image(path)
                ):
                    return path
            else:
                previous = signature
                stable_since = None
        time.sleep(poll_seconds)
    raise TimeoutError(f"export did not become stable within {timeout_seconds}s: {path}")


def wait_for_new_stable_export(
    directory: Path,
    *,
    stem: str,
    before: dict[Path, tuple[int, int]],
    timeout_seconds: float = 120.0,
    stable_seconds: float = 0.4,
    poll_seconds: float = 0.2,
) -> Path:
    """Return a new or changed export with the requested stem and any valid suffix."""

    deadline = time.monotonic() + timeout_seconds
    stable_candidate: Path | None = None
    stable_signature: tuple[int, int] | None = None
    stable_since: float | None = None
    while time.monotonic() < deadline:
        current = snapshot_export_files(directory)
        candidates = [
            path
            for path, signature in current.items()
            if path.stem == stem and signature != before.get(path) and signature[0] > 0
        ]
        candidate = max(
            candidates,
            key=lambda path: current[path][1],
            default=None,
        )
        if candidate is not None:
            signature = current[candidate]
            if candidate == stable_candidate and signature == stable_signature:
                stable_since = stable_since or time.monotonic()
                if (
                    time.monotonic() - stable_since >= stable_seconds
                    and _is_complete_image(candidate)
                ):
                    return candidate
            else:
                stable_candidate = candidate
                stable_signature = signature
                stable_since = None
        time.sleep(poll_seconds)
    visible = sorted(path.name for path in snapshot_export_files(directory))
    raise TimeoutError(
        f"export {stem!r} did not appear in {directory} within {timeout_seconds}s; "
        f"visible exports: {visible}"
    )
