"""Stateful, resumable capture operations shared by the CLI."""

from __future__ import annotations

import shutil
from pathlib import Path
from time import monotonic
from typing import Any

from PIL import Image

from .app_controller import LuminarAppController
from .case_reader import CaptureCase
from .layout import CaptureLayout
from .metadata_writer import build_metadata, sha256_file, write_metadata
from .state_machine import CaptureJournal, CaptureStatus


def _copy_as_png(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        if image.format == "PNG" and image.mode == "RGB":
            image.verify()
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            return
        image.convert("RGB").save(destination, format="PNG")


def prepare_case(
    case: CaptureCase,
    layout: CaptureLayout,
    controller: LuminarAppController,
) -> None:
    layout.prepare()
    controller.launch()
    controller.activate()
    controller.ensure_window()
    CaptureJournal(layout).transition(
        CaptureStatus.APP_READY,
        capability_id=case.capability_id,
        input_path=str(case.input_path),
        operator_instruction="照片已导入；按文件名选择 input_path，然后进入指定工具。",
        parameters=case.parameters,
        asset_id=case.asset_id,
    )


def capture_ui(
    layout: CaptureLayout,
    controller: LuminarAppController,
    *,
    stage: str,
) -> Path:
    destination = (
        layout.staging_before_path if stage == "before" else layout.staging_after_path
    )
    bounds = controller.screenshot_window(destination)
    status = (
        CaptureStatus.BASELINE_VERIFIED
        if stage == "before"
        else CaptureStatus.AFTER_CAPTURED
    )
    CaptureJournal(layout).transition(status, window_bounds=bounds.__dict__)
    return destination


def import_computer_use_state(
    layout: CaptureLayout,
    *,
    stage: str,
    screenshot_source: Path,
    accessibility_source: Path,
) -> Path:
    """Import one Computer Use screenshot and AX tree as staged evidence."""

    if stage not in {"before", "after"}:
        raise ValueError(f"unsupported Computer Use stage: {stage}")
    layout.prepare()
    screenshot_destination = (
        layout.staging_before_path if stage == "before" else layout.staging_after_path
    )
    ax_destination = (
        layout.staging_before_ax_path
        if stage == "before"
        else layout.staging_after_ax_path
    )
    _copy_as_png(screenshot_source, screenshot_destination)
    ax_destination.write_text(
        accessibility_source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    status = (
        CaptureStatus.BASELINE_VERIFIED
        if stage == "before"
        else CaptureStatus.AFTER_CAPTURED
    )
    CaptureJournal(layout).transition(
        status,
        capture_source="computer-use",
        screenshot=str(screenshot_destination),
        accessibility_tree=str(ax_destination),
    )
    return screenshot_destination


def finalize_case(
    case: CaptureCase,
    layout: CaptureLayout,
    *,
    preview_source: Path,
    export_source: Path,
    reference_build: str,
    operator_mode: str,
    app_version: dict[str, str],
    mask_source: Path | None = None,
    preview_evidence: str = "provided-preview",
    export_evidence: str = "provided-export",
) -> dict[str, Any]:
    started = monotonic()
    checkpoint = started
    publish_timings_ms: dict[str, float] = {}

    def mark(stage: str) -> None:
        nonlocal checkpoint
        now = monotonic()
        publish_timings_ms[stage] = round((now - checkpoint) * 1000.0, 3)
        checkpoint = now

    layout.prepare()
    _copy_as_png(preview_source, layout.preview_path)
    mark("preview_convert")
    native_export = layout.native_export_path(export_source.suffix)
    if export_source.resolve() != native_export.resolve():
        shutil.copy2(export_source, native_export)
    mark("native_export_copy")
    _copy_as_png(export_source, layout.export_path)
    mark("export_convert")
    if mask_source:
        _copy_as_png(mask_source, layout.mask_path)
    for staged, destination in (
        (layout.staging_before_path, layout.before_path),
        (layout.staging_after_path, layout.after_path),
        (layout.staging_before_ax_path, layout.before_ax_path),
        (layout.staging_after_ax_path, layout.after_ax_path),
    ):
        if staged.is_file():
            shutil.copy2(staged, destination)
    mark("evidence_copy")
    metadata = build_metadata(
        case,
        layout,
        reference_build=reference_build,
        operator_mode=operator_mode,
        app_version=app_version,
        evidence_sources={
            "preview": preview_evidence,
            "export": export_evidence,
        },
    )
    metadata["native_export"] = {
        "path": str(native_export),
        "format": native_export.suffix.lstrip(".").upper(),
        "size": native_export.stat().st_size,
        "sha256": sha256_file(native_export),
    }
    write_metadata(layout.metadata_path, metadata)
    mark("metadata_write")
    CaptureJournal(layout).transition(
        CaptureStatus.READY,
        metadata=str(layout.metadata_path),
        finalize_seconds=round(monotonic() - started, 6),
        publish_timings_ms=publish_timings_ms,
    )
    return metadata
