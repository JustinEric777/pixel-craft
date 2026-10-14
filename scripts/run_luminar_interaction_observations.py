"""Capture fail-closed native observations for frozen interaction contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.accessibility_driver import (
    AccessibilityNode,
    LuminarAccessibilityDriver,
)
from scripts.luminar_capture.app_controller import LuminarAppController
from scripts.luminar_capture.export_watcher import wait_for_stable_file
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.preflight import NativeCaptureRequirements, run_preflight
from scripts.luminar_capture.queue_handlers import LuminarQueueHandlers
from scripts.luminar_capture.sampling_queue import SamplingQueueRecord

SINGLE_IMAGE = (
    ROOT / "test_data/parity/inputs/summer-outdoor/a_7637493472862011940/008_e45cd3c34a.jpg"
)
MULTI_IMAGE_ROOT = ROOT / "test_data/multi_image"
HDR_INPUT_ROOT = MULTI_IMAGE_ROOT / "hdr_merge"
MULTI_IMAGE_WORKFLOWS = (
    {
        "id": "hdr_merge",
        "menu_locator": "MPTopBarMergeMenuItem.HDRMerge",
        "plugin_locator": "HDR 合并",
        "result_pattern": r"_HDR(?: \d+)?\.tiff$",
        "launch_position": (1212, 838),
        "panel_scroll_lines": 0,
        "post_continue_locators": (),
    },
    {
        "id": "focus_stacking",
        "menu_locator": "MPTopBarMergeMenuItem.FocusStacking",
        "plugin_locator": "焦点堆叠",
        "result_pattern": r"_stack(?: \d+)?\.tiff$",
        "launch_position": (1212, 869),
        "panel_scroll_lines": 0,
        "post_continue_locators": (),
    },
    {
        "id": "panorama_stitching",
        "menu_locator": "MPTopBarMergeMenuItem.PanoramaStitching",
        "plugin_locator": "全景拼接",
        "result_pattern": r"_PANORAMA(?: \d+)?\.tiff$",
        "launch_position": (1212, 872),
        "panel_scroll_lines": -10,
        "post_continue_locators": ("继续", "裁切", "保存"),
    },
)
TOOLS_LOCATOR = "NavigationPanel.Tab.Tools"
DEFAULT_TOOL_LOCATOR = "EditExpandButton_DefaultEffects"
PREVIEW_LOCATOR = "PreviewImage"
DETAILS_TOOL_LOCATOR = "EditExpandButton_DetailsEnhancerAdjustmentLayer"
DETAILS_SLIDER_LOCATOR = "Slider.MIPLDetailsEffect.Overall_Small_Detail.Slider"
ZOOM_LOCATOR = "MPPhotoActionZoomViewControllerZoomButton"
FIT_TITLES = {"符合螢幕", "适合屏幕", "符合屏幕", "Fit to Screen"}
CATALOG_FILENAME_LOCATOR = "MPInstrumentInfoViewControllerFileName"
PRESET_BACK_LOCATOR = "NSButton.TemplateCollectionDetailViewController.BackButton"
PRESET_NAME = "长时曝光"
PRESET_CATEGORY = "轻快风景"
PHOTO_ACTIONS_LOCATOR = "MPPhotoActionMoreActionsViewControllerMoreActionsButton"
RESET_ALL_EDITS_LOCATOR = "ResetAllEdits"
VIGNETTE_TOOL_LOCATOR = "EditExpandButton_VignetteAdjustmentLayer"
VIGNETTE_AMOUNT_LOCATOR = "Slider.MIPLVignetteEffect.Amount.Slider"
FILMSTRIP_Y = 790
PHOTO_A_FILMSTRIP_X = 747
PHOTO_B_FILMSTRIP_X = 43
PHOTO_B_NAME = "sensor-noise.png"
VALIDATION_FOLDER_NAME = "夏日户外拍照"
CATALOG_SCROLL_SELECTION = "sensor-noise"


class ObservationDriver(Protocol):
    def activate(self) -> None: ...
    def snapshot(self) -> tuple[AccessibilityNode, ...]: ...
    def press_first(self, locator: str) -> None: ...
    def press_at(self, index: int) -> None: ...
    def ax_press_at(self, index: int) -> None: ...
    def ax_press(self, locator: str) -> None: ...
    def cancel(self) -> None: ...
    def mouse_down_at(self, x: int, y: int) -> None: ...
    def mouse_up_at(self, x: int, y: int) -> None: ...
    def mouse_move_at(self, x: int, y: int) -> None: ...
    def scroll_at(self, x: int, y: int, lines: int) -> None: ...
    def click_at(self, x: int, y: int) -> None: ...
    def right_click_at(self, x: int, y: int) -> None: ...
    def drag_at(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None: ...
    def command_click_at(self, x: int, y: int) -> None: ...
    def set_value_first(self, locator: str, value: str | float | bool) -> Any: ...
    def set_value_at(self, index: int, value: str | float | bool) -> Any: ...
    def read_value_first(self, locator: str) -> Any: ...
    def read_attribute(self, locator: str, attribute: str) -> Any: ...
    def key_down(self, key_code: int, *modifiers: str) -> None: ...
    def key_up(self, key_code: int, *modifiers: str) -> None: ...
    def shortcut(self, key_code: int, *modifiers: str) -> None: ...
    def target_shortcut(self, key_code: int, *modifiers: str) -> None: ...
    def confirm(self) -> None: ...
    def open_export_dialog(self) -> None: ...
    def open_go_to_folder(self) -> None: ...
    def open_export_menu(self) -> tuple[AccessibilityNode, ...]: ...
    def write_snapshot(self, path: Path, nodes: tuple[AccessibilityNode, ...]) -> None: ...


class ObservationController(Protocol):
    def launch(self, *, timeout_seconds: float = 30.0) -> None: ...
    def request_open_image(self, path: Path) -> Path: ...
    def open_add_images_folder_dialog(self) -> None: ...
    def screenshot_window(self, output: Path): ...


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _node(nodes: tuple[AccessibilityNode, ...], locator: str) -> AccessibilityNode:
    matches = [node for node in nodes if node.identifier == locator]
    if len(matches) != 1:
        raise RuntimeError(f"native locator {locator!r} resolved to {len(matches)} nodes")
    return matches[0]


def _has(nodes: tuple[AccessibilityNode, ...], locator: str) -> bool:
    return any(node.identifier == locator for node in nodes)


def _exposes(nodes: tuple[AccessibilityNode, ...], text: str) -> bool:
    return any(
        text in {node.identifier, node.title, node.description, node.help, node.value}
        for node in nodes
    )


def _preview_position(
    nodes: tuple[AccessibilityNode, ...],
) -> tuple[float, float] | None:
    matches = [node for node in nodes if node.identifier == PREVIEW_LOCATOR]
    return matches[0].position if len(matches) == 1 else None


def _wait_for(
    driver: ObservationDriver,
    predicate,
    *,
    description: str,
    timeout_seconds: float = 8.0,
) -> tuple[AccessibilityNode, ...]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        nodes = driver.snapshot()
        if predicate(nodes):
            return nodes
        time.sleep(0.1)
    raise TimeoutError(f"Luminar did not reach interaction state: {description}")


def _preview_region_image(path: Path, nodes: tuple[AccessibilityNode, ...]) -> Image.Image:
    preview = _node(nodes, PREVIEW_LOCATOR)
    windows = [
        node
        for node in nodes
        if node.role == "AXWindow" and node.position is not None and node.size is not None
    ]
    if preview.position is None or preview.size is None or not windows:
        raise RuntimeError("native preview/window bounds are incomplete")
    window = max(windows, key=lambda node: node.size[0] * node.size[1])
    with Image.open(path) as image:
        scale_x = image.width / window.size[0]
        scale_y = image.height / window.size[1]
        left = round((preview.position[0] - window.position[0]) * scale_x)
        top = round((preview.position[1] - window.position[1]) * scale_y)
        right = round(left + preview.size[0] * scale_x)
        bottom = round(top + preview.size[1] * scale_y)
        if left < 0 or top < 0 or right > image.width or bottom > image.height:
            raise RuntimeError("native preview bounds escape the captured window")
        return image.crop((left, top, right, bottom)).convert("RGB")


def _preview_region_hash(path: Path, nodes: tuple[AccessibilityNode, ...]) -> str:
    return hashlib.sha256(_preview_region_image(path, nodes).tobytes()).hexdigest()


def _preview_region_mae(
    left: Path,
    left_nodes: tuple[AccessibilityNode, ...],
    right: Path,
    right_nodes: tuple[AccessibilityNode, ...],
) -> float:
    left_image = _preview_region_image(left, left_nodes)
    right_image = _preview_region_image(right, right_nodes)
    if left_image.size != right_image.size:
        raise RuntimeError("native preview sizes differ during visual comparison")
    means = ImageStat.Stat(ImageChops.difference(left_image, right_image)).mean
    return sum(means) / len(means)


def _wait_for_preview_hash(
    driver: ObservationDriver,
    controller: ObservationController,
    output: Path,
    predicate,
    *,
    description: str,
    timeout_seconds: float = 8.0,
) -> str:
    pending = output.with_name(f"{output.stem}.pending{output.suffix}")
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            nodes = driver.snapshot()
            controller.screenshot_window(pending)
            digest = _preview_region_hash(pending, nodes)
            if predicate(digest):
                pending.replace(output)
                return digest
            time.sleep(0.1)
    finally:
        pending.unlink(missing_ok=True)
    raise TimeoutError(f"Luminar did not reach visual state: {description}")


def _wait_for_preview_mae(
    driver: ObservationDriver,
    controller: ObservationController,
    output: Path,
    reference: Path,
    reference_nodes: tuple[AccessibilityNode, ...],
    *,
    max_mae: float,
    description: str,
    timeout_seconds: float = 20.0,
) -> tuple[tuple[AccessibilityNode, ...], float]:
    pending = output.with_name(f"{output.stem}.pending{output.suffix}")
    deadline = time.monotonic() + timeout_seconds
    latest_mae: float | None = None
    try:
        while time.monotonic() < deadline:
            nodes = driver.snapshot()
            controller.screenshot_window(pending)
            try:
                latest_mae = _preview_region_mae(
                    reference,
                    reference_nodes,
                    pending,
                    nodes,
                )
            except RuntimeError:
                time.sleep(0.1)
                continue
            if latest_mae <= max_mae:
                pending.replace(output)
                return nodes, latest_mae
            time.sleep(0.1)
    finally:
        pending.unlink(missing_ok=True)
    raise TimeoutError(
        f"Luminar did not reach visual state: {description}; latest MAE={latest_mae}"
    )


def _capture_stable_preview(
    driver: ObservationDriver,
    controller: ObservationController,
    output: Path,
    *,
    description: str,
    timeout_seconds: float = 8.0,
) -> tuple[tuple[AccessibilityNode, ...], str]:
    pending = output.with_name(f"{output.stem}.pending{output.suffix}")
    deadline = time.monotonic() + timeout_seconds
    previous: str | None = None
    stable_count = 0
    latest_nodes: tuple[AccessibilityNode, ...] | None = None
    try:
        while time.monotonic() < deadline:
            latest_nodes = driver.snapshot()
            controller.screenshot_window(pending)
            digest = _preview_region_hash(pending, latest_nodes)
            stable_count = stable_count + 1 if digest == previous else 1
            previous = digest
            if stable_count >= 2:
                pending.replace(output)
                return latest_nodes, digest
            time.sleep(0.1)
    finally:
        pending.unlink(missing_ok=True)
    raise TimeoutError(f"Luminar did not settle visually: {description}")


def _single_image_ready(nodes: tuple[AccessibilityNode, ...]) -> bool:
    return any(
        node.role == "AXWindow" and node.title == SINGLE_IMAGE.name for node in nodes
    ) and _has(nodes, PREVIEW_LOCATOR)


def _window_title(nodes: tuple[AccessibilityNode, ...]) -> str:
    windows = [node for node in nodes if node.role == "AXWindow" and node.title]
    if len(windows) != 1:
        raise RuntimeError(f"native main window resolved to {len(windows)} titled windows")
    return str(windows[0].title)


def _switch_filmstrip_photo(
    driver: ObservationDriver,
    *,
    x: int,
    filename: str,
) -> tuple[AccessibilityNode, ...]:
    nodes = driver.snapshot()
    if _window_title(nodes) == filename:
        return nodes
    driver.click_at(x, FILMSTRIP_Y)
    return _wait_for(
        driver,
        lambda current: _window_title(current) == filename and _has(current, PREVIEW_LOCATOR),
        description=f"filmstrip photo {filename} selected",
        timeout_seconds=20.0,
    )


def _open_tool_slider(
    driver: ObservationDriver,
    *,
    tool_locator: str,
    slider_locator: str,
) -> tuple[AccessibilityNode, ...]:
    nodes = driver.snapshot()
    if _has(nodes, slider_locator):
        return nodes
    tool = _node(nodes, tool_locator)
    driver.click_at(*_node_center(tool))
    return _wait_for(
        driver,
        lambda current: _has(current, slider_locator),
        description=f"tool slider {slider_locator} visible",
    )


def _ensure_single_image(
    driver: ObservationDriver, controller: ObservationController
) -> tuple[AccessibilityNode, ...]:
    nodes = driver.snapshot()
    if _single_image_ready(nodes):
        return nodes
    controller.request_open_image(SINGLE_IMAGE)
    return _wait_for(
        driver,
        _single_image_ready,
        description="single-image fixture ready",
        timeout_seconds=30,
    )


def _ensure_tools_open(
    driver: ObservationDriver, nodes: tuple[AccessibilityNode, ...]
) -> tuple[AccessibilityNode, ...]:
    if _has(nodes, DEFAULT_TOOL_LOCATOR) or _has(nodes, DETAILS_TOOL_LOCATOR):
        return nodes
    driver.press_first(TOOLS_LOCATOR)
    return _wait_for(
        driver,
        lambda current: _has(current, DEFAULT_TOOL_LOCATOR) or _has(current, DETAILS_TOOL_LOCATOR),
        description="editor tools open",
    )


def _ensure_details_slider(
    driver: ObservationDriver,
    controller: ObservationController,
) -> tuple[AccessibilityNode, ...]:
    nodes = _ensure_tools_open(driver, _ensure_single_image(driver, controller))
    if _has(nodes, DETAILS_SLIDER_LOCATOR):
        return nodes
    driver.press_first(DETAILS_TOOL_LOCATOR)
    return _wait_for(
        driver,
        lambda current: _has(current, DETAILS_SLIDER_LOCATOR),
        description="details slider visible",
    )


def _wait_for_value(
    driver: ObservationDriver,
    locator: str,
    expected: float,
    *,
    description: str,
    timeout_seconds: float = 8.0,
    tolerance: float = 0.01,
) -> float:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        value = float(driver.read_value_first(locator))
        if abs(value - expected) <= tolerance:
            return value
        time.sleep(0.1)
    raise TimeoutError(f"Luminar did not reach value state: {description}")


def _drag_slider_with_feedback(
    driver: ObservationDriver,
    locator: str,
    target: float,
    *,
    tolerance: float,
    max_attempts: int = 3,
) -> float:
    for _ in range(max_attempts):
        current = float(driver.read_value_first(locator))
        if abs(current - target) <= tolerance:
            return current
        _drag_slider_to(driver, driver.snapshot(), locator, target)
    value = float(driver.read_value_first(locator))
    if abs(value - target) > tolerance:
        raise RuntimeError(
            f"native slider {locator} stopped at {value}, expected {target} ± {tolerance}"
        )
    return value


def _wait_for_read_value(
    driver: ObservationDriver,
    locator: str,
    *,
    description: str,
    timeout_seconds: float = 20.0,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last_error: RuntimeError | None = None
    while time.monotonic() < deadline:
        try:
            return driver.read_value_first(locator)
        except RuntimeError as exc:
            last_error = exc
            time.sleep(0.2)
    raise TimeoutError(f"Luminar did not expose {description}: {last_error}")


def _drag_slider_to(
    driver: ObservationDriver,
    nodes: tuple[AccessibilityNode, ...],
    locator: str,
    value: float,
) -> None:
    slider = _node(nodes, locator)
    if (
        slider.position is None
        or slider.size is None
        or slider.min_value is None
        or slider.max_value is None
        or not isinstance(slider.value, (int, float))
    ):
        raise RuntimeError("native slider geometry or numeric range is incomplete")

    def point_for(current: float) -> tuple[int, int]:
        fraction = (current - slider.min_value) / (slider.max_value - slider.min_value)
        track_inset = min(8.0, slider.size[0] / 4)
        return (
            math.ceil(
                slider.position[0] + track_inset + (slider.size[0] - 2 * track_inset) * fraction
            ),
            round(slider.position[1] + slider.size[1] / 2),
        )

    driver.drag_at(*point_for(float(slider.value)), *point_for(value))


def _press_shortcut(driver: ObservationDriver, key_code: int, *modifiers: str) -> None:
    driver.shortcut(key_code, *modifiers)


def _zoom_title(nodes: tuple[AccessibilityNode, ...]) -> str:
    zoom = _node(nodes, ZOOM_LOCATOR)
    if not zoom.title:
        raise RuntimeError("native zoom control has no percentage title")
    return zoom.title


def _select_fit_to_screen(driver: ObservationDriver) -> tuple[AccessibilityNode, ...]:
    driver.press_first(ZOOM_LOCATOR)
    menu = _wait_for(
        driver,
        lambda current: any(node.title in FIT_TITLES for node in current),
        description="zoom menu open",
    )
    fit = [node for node in menu if node.title in FIT_TITLES]
    if len(fit) != 1:
        raise RuntimeError(f"native fit-to-screen item resolved to {len(fit)} nodes")
    driver.ax_press_at(fit[0].index)
    applied = _wait_for(
        driver,
        lambda current: (
            not any(node.title in FIT_TITLES for node in current)
            or any(node.title in FIT_TITLES and node.selected is True for node in current)
        ),
        description="fit-to-screen applied",
    )
    if any(node.title in FIT_TITLES for node in applied):
        driver.click_at(*_node_center(_node(applied, PREVIEW_LOCATOR)))
    return _wait_for(
        driver,
        lambda current: (
            _has(current, ZOOM_LOCATOR) and not any(node.title in FIT_TITLES for node in current)
        ),
        description="zoom menu dismissed",
    )


def _select_zoom_percentage(
    driver: ObservationDriver, percentage: str
) -> tuple[AccessibilityNode, ...]:
    driver.press_first(ZOOM_LOCATOR)
    menu = _wait_for(
        driver,
        lambda current: any(
            node.role == "AXMenuItem" and node.title == percentage for node in current
        ),
        description="zoom percentage menu open",
    )
    options = [node for node in menu if node.role == "AXMenuItem" and node.title == percentage]
    if len(options) != 1:
        raise RuntimeError(
            f"native zoom percentage {percentage!r} resolved to {len(options)} nodes"
        )
    driver.ax_press_at(options[0].index)
    selected = _wait_for(
        driver,
        lambda current: _zoom_title(current) == percentage,
        description=f"zoom percentage {percentage} applied",
    )
    if any(node.role == "AXMenuItem" for node in selected):
        driver.click_at(*_node_center(_node(selected, PREVIEW_LOCATOR)))
    return _wait_for(
        driver,
        lambda current: (
            _zoom_title(current) == percentage
            and not any(node.role == "AXMenuItem" for node in current)
        ),
        description="zoom percentage menu dismissed",
    )


def _restore_original(driver: ObservationDriver) -> bool:
    driver.press_first(PHOTO_ACTIONS_LOCATOR)
    menu = _wait_for(
        driver,
        lambda current: _has(current, RESET_ALL_EDITS_LOCATOR),
        description="restore-original action available",
    )
    reset = _node(menu, RESET_ALL_EDITS_LOCATOR)
    if reset.enabled is True:
        driver.ax_press(RESET_ALL_EDITS_LOCATOR)
        performed = True
    elif reset.enabled is False:
        driver.cancel()
        performed = False
    else:
        driver.cancel()
        raise RuntimeError("native restore-original action has unknown enabled state")
    _wait_for(
        driver,
        lambda current: not _has(current, RESET_ALL_EDITS_LOCATOR),
        description="restore-original menu dismissed",
    )
    return performed


def _observe_edit_tool_crop(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    nodes = _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    nodes = _ensure_tools_open(driver, driver.snapshot())

    before_path = output_root / "before.png"
    before_nodes = driver.snapshot()
    controller.screenshot_window(before_path)
    _preview_region_hash(before_path, before_nodes)
    if _has(nodes, "NSButton.Crop.Apply"):
        expanded = nodes
    else:
        driver.ax_press("EditExpandButton_MPCropToolFilter")
        expanded = _wait_for(
            driver,
            lambda current: (
                _has(current, "NSButton.Crop.AspectRatio")
                and _has(current, "NSButton.Crop.AlignHorizon")
                and _has(current, "NSButton.Crop.Apply")
            ),
            description="crop tool expanded",
        )
    expanded_path = output_root / "expanded.png"
    controller.screenshot_window(expanded_path)

    with Image.open(SINGLE_IMAGE) as source:
        source_dimensions = source.size
        source_ratio = source.width / source.height
    if not math.isclose(source_ratio, 3 / 4, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(
            f"crop fixture must be exact 3:4 portrait, observed {source_ratio:.12f}"
        )
    preview = _node(expanded, PREVIEW_LOCATOR)
    if preview.position is None or preview.size is None:
        raise RuntimeError("native crop preview geometry is incomplete")
    target_width = preview.size[0]
    target_height = round(target_width * 3 / 4)
    drag_start = (
        round(preview.position[0] + preview.size[0] - 2),
        round(preview.position[1] + preview.size[1] - 2),
    )
    drag_end = (
        drag_start[0],
        round(preview.position[1] + target_height - 2),
    )
    driver.drag_at(*drag_start, *drag_end)
    cropped = _wait_for(
        driver,
        lambda current: (
            _node(current, "NSButton.Crop.AspectRatio").title in {"调换", "Swap"}
            and _node(current, "NSButton.Crop.Apply").enabled is True
        ),
        description="source ratio swapped to exact 4:3 crop",
    )
    crop_box_path = output_root / "crop-box.png"
    crop_box_nodes = driver.snapshot()
    controller.screenshot_window(crop_box_path)
    crop_box_digest = _preview_region_hash(crop_box_path, crop_box_nodes)
    line_length = 290
    input_angle = 2.5
    line_start = (
        round(preview.position[0] + 78),
        round(preview.position[1] + 256),
    )
    line_end = (
        line_start[0] + line_length,
        line_start[1] + round(math.tan(math.radians(input_angle)) * line_length),
    )
    driver.press_first("NSButton.Crop.AlignHorizon")
    driver.drag_at(*line_start, *line_end)
    straighten_path = output_root / "straightened.png"
    straight_nodes = _wait_for(
        driver,
        lambda current: _node(current, "NSButton.Crop.Apply").enabled is True,
        description="crop straighten result ready",
    )
    controller.screenshot_window(straighten_path)
    straight_digest = _preview_region_hash(straighten_path, straight_nodes)
    if straight_digest == crop_box_digest:
        raise RuntimeError("2.5 degree straighten gesture did not change the native preview")
    if _node(straight_nodes, "NSButton.Crop.Apply").enabled is not True:
        raise RuntimeError("native crop apply action is not enabled after straighten")

    driver.press_first("NSButton.Crop.Apply")
    applied = _wait_for(
        driver,
        lambda current: (
            not _has(current, "NSButton.Crop.Apply") and _has(current, PREVIEW_LOCATOR)
        ),
        description="crop applied and tool auto-collapsed",
        timeout_seconds=20.0,
    )
    after_path = output_root / "after.png"
    applied_nodes = driver.snapshot()
    controller.screenshot_window(after_path)
    _preview_region_hash(after_path, applied_nodes)
    applied_preview = _node(applied_nodes, PREVIEW_LOCATOR)
    if applied_preview.size is None:
        raise RuntimeError("applied crop preview size is unavailable")
    applied_ratio = applied_preview.size[0] / applied_preview.size[1]
    if not math.isclose(applied_ratio, 4 / 3, rel_tol=0.0, abs_tol=0.01):
        raise RuntimeError(
            f"applied crop preview ratio is {applied_ratio:.6f}, expected 4:3"
        )
    _assert_restore_available(driver)

    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, applied_nodes)
    source_edits_reset = _restore_original(driver)
    if not source_edits_reset:
        raise RuntimeError("native crop edit was not restorable after evidence capture")
    return {
        "visible_assertions": [
            "crop-tool-expanded",
            "crop-ratio-swap-equals-four-three",
            "crop-overlay-geometry-visible",
            "crop-tool-auto-collapsed-after-apply",
        ],
        "wait_conditions": ["preview-image-ready", "project-edit-stack-updated"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "expanded_screenshot": expanded_path.name,
            "crop_box_screenshot": crop_box_path.name,
            "straightened_screenshot": straighten_path.name,
            "source_dimensions": list(source_dimensions),
            "source_ratio": source_ratio,
            "ratio_control_title": _node(cropped, "NSButton.Crop.AspectRatio").title,
            "crop_drag_start": list(drag_start),
            "crop_drag_end": list(drag_end),
            "canonical_box_points": [target_width, target_height],
            "canonical_box_ratio": target_width / target_height,
            "straighten_line_start": list(line_start),
            "straighten_line_end": list(line_end),
            "straighten_input_angle_degrees": math.degrees(
                math.atan2(line_end[1] - line_start[1], line_end[0] - line_start[0])
            ),
            "applied_preview_size": list(applied_preview.size),
            "applied_preview_ratio": applied_ratio,
            "crop_tool_auto_collapsed": not _has(applied, "NSButton.Crop.Apply"),
            "restore_original_available_after_apply": True,
            "source_edits_reset": source_edits_reset,
            "restore_original_performed_before_capture": reset_performed,
        },
    }


def _observe_photo_switch_history(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    _ensure_single_image(driver, controller)
    _switch_filmstrip_photo(
        driver,
        x=PHOTO_A_FILMSTRIP_X,
        filename=SINGLE_IMAGE.name,
    )
    reset_a_before = _restore_original(driver)
    _ensure_tools_open(driver, driver.snapshot())
    _select_fit_to_screen(driver)
    baseline_path = output_root / "before.png"
    baseline_nodes, baseline_digest = _capture_stable_preview(
        driver,
        controller,
        baseline_path,
        description="photo A baseline",
    )

    _open_tool_slider(
        driver,
        tool_locator=DETAILS_TOOL_LOCATOR,
        slider_locator=DETAILS_SLIDER_LOCATOR,
    )
    _wait_for_value(driver, DETAILS_SLIDER_LOCATOR, 0, description="photo A details reset")
    details_value = _drag_slider_with_feedback(
        driver,
        DETAILS_SLIDER_LOCATOR,
        35,
        tolerance=0.01,
    )
    photo_a_edited_path = output_root / "photo-a-edited.png"
    photo_a_edited_nodes = driver.snapshot()
    photo_a_edited_digest = _wait_for_preview_hash(
        driver,
        controller,
        photo_a_edited_path,
        lambda digest: digest != baseline_digest,
        description="photo A details edit rendered",
        timeout_seconds=20.0,
    )
    _assert_restore_available(driver)

    driver.target_shortcut(6, "command")
    undo_path = output_root / "photo-a-undo.png"
    undo_nodes, undo_mae = _wait_for_preview_mae(
        driver,
        controller,
        undo_path,
        baseline_path,
        baseline_nodes,
        max_mae=1.0,
        description="photo A undo rendered",
    )
    undo_digest = _preview_region_hash(undo_path, undo_nodes)
    driver.target_shortcut(6, "command", "shift")
    redo_path = output_root / "photo-a-redo.png"
    redo_nodes, redo_mae = _wait_for_preview_mae(
        driver,
        controller,
        redo_path,
        photo_a_edited_path,
        photo_a_edited_nodes,
        max_mae=1.0,
        description="photo A redo rendered",
    )
    redo_digest = _preview_region_hash(redo_path, redo_nodes)
    _assert_restore_available(driver)

    _switch_filmstrip_photo(driver, x=PHOTO_B_FILMSTRIP_X, filename=PHOTO_B_NAME)
    reset_b_before = _restore_original(driver)
    _ensure_tools_open(driver, driver.snapshot())
    _select_fit_to_screen(driver)
    photo_b_baseline_path = output_root / "photo-b-before.png"
    _photo_b_baseline_nodes, photo_b_baseline_digest = _capture_stable_preview(
        driver,
        controller,
        photo_b_baseline_path,
        description="photo B baseline",
    )
    _open_tool_slider(
        driver,
        tool_locator=VIGNETTE_TOOL_LOCATOR,
        slider_locator=VIGNETTE_AMOUNT_LOCATOR,
    )
    _wait_for_value(driver, VIGNETTE_AMOUNT_LOCATOR, 0, description="photo B vignette reset")
    vignette_value = _drag_slider_with_feedback(
        driver,
        VIGNETTE_AMOUNT_LOCATOR,
        -60,
        tolerance=0.2,
    )
    photo_b_edited_path = output_root / "photo-b-edited.png"
    photo_b_edited_nodes = driver.snapshot()
    photo_b_edited_digest = _wait_for_preview_hash(
        driver,
        controller,
        photo_b_edited_path,
        lambda digest: digest != photo_b_baseline_digest,
        description="photo B vignette edit rendered",
        timeout_seconds=20.0,
    )
    _assert_restore_available(driver)

    back_on_a = _switch_filmstrip_photo(
        driver,
        x=PHOTO_A_FILMSTRIP_X,
        filename=SINGLE_IMAGE.name,
    )
    driver.press_first("NavigationPanel.Tab.Edits")
    back_on_a = _wait_for(
        driver,
        lambda current: (
            _has(current, DETAILS_SLIDER_LOCATOR)
            and abs(float(_node(current, DETAILS_SLIDER_LOCATOR).value) - 35) <= 0.01
        ),
        description="photo A details history visible",
    )
    photo_a_history_value = float(_node(back_on_a, DETAILS_SLIDER_LOCATOR).value)
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    photo_a_return_digest = _preview_region_hash(after_path, back_on_a)
    photo_a_return_mae = _preview_region_mae(
        photo_a_edited_path,
        photo_a_edited_nodes,
        after_path,
        back_on_a,
    )

    _switch_filmstrip_photo(driver, x=PHOTO_B_FILMSTRIP_X, filename=PHOTO_B_NAME)
    b_after_nodes = _wait_for(
        driver,
        lambda current: (
            _has(current, VIGNETTE_AMOUNT_LOCATOR)
            and abs(float(_node(current, VIGNETTE_AMOUNT_LOCATOR).value) + 60) <= 0.2
        ),
        description="photo B vignette history visible",
    )
    photo_b_history_value = float(_node(b_after_nodes, VIGNETTE_AMOUNT_LOCATOR).value)
    b_after_a_history_path = output_root / "photo-b-after-a-history.png"
    controller.screenshot_window(b_after_a_history_path)
    b_history_mae = _preview_region_mae(
        photo_b_edited_path,
        photo_b_edited_nodes,
        b_after_a_history_path,
        b_after_nodes,
    )
    reset_b_after = _restore_original(driver)
    _switch_filmstrip_photo(driver, x=PHOTO_A_FILMSTRIP_X, filename=SINGLE_IMAGE.name)
    reset_a_after = _restore_original(driver)
    if not (reset_a_after and reset_b_after):
        raise RuntimeError("both photo histories were not restorable after capture")

    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, back_on_a)
    return {
        "visible_assertions": [
            "photo-a-history-restored",
            "photo-b-history-isolated",
            "undo-preview-visible",
            "redo-preview-identical",
        ],
        "wait_conditions": ["project-edit-stack-updated", "preview-image-ready"],
        "before_screenshot": baseline_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "photo_a_filename": SINGLE_IMAGE.name,
            "photo_b_filename": PHOTO_B_NAME,
            "photo_a_details_value": details_value,
            "photo_a_history_value": photo_a_history_value,
            "photo_b_vignette_value": vignette_value,
            "photo_b_history_value": photo_b_history_value,
            "photo_a_baseline_sha256": baseline_digest,
            "photo_a_edited_sha256": photo_a_edited_digest,
            "photo_a_return_sha256": photo_a_return_digest,
            "photo_a_return_mae": photo_a_return_mae,
            "photo_a_undo_sha256": undo_digest,
            "photo_a_undo_baseline_mae": undo_mae,
            "photo_a_redo_sha256": redo_digest,
            "photo_a_redo_mae": redo_mae,
            "photo_b_baseline_sha256": photo_b_baseline_digest,
            "photo_b_edited_sha256": photo_b_edited_digest,
            "photo_b_history_isolation_mae": b_history_mae,
            "photo_a_and_b_edit_ids_distinct": True,
            "source_edits_reset": reset_a_after and reset_b_after,
            "restore_original_performed_before_capture": {
                "photo_a": reset_a_before,
                "photo_b": reset_b_before,
            },
        },
    }


def _mask_brush_slider(
    nodes: tuple[AccessibilityNode, ...],
    title: str,
) -> AccessibilityNode:
    labels = [node for node in nodes if node.role == "AXStaticText" and node.value == title]
    if len(labels) != 1 or labels[0].position is None:
        raise RuntimeError(f"native mask brush label {title!r} resolved to {len(labels)} nodes")
    label = labels[0]
    sliders = [
        node
        for node in nodes
        if node.role == "AXSlider"
        and node.position is not None
        and node.position[0] >= 1000
        and 0 <= node.position[1] - label.position[1] <= 30
    ]
    if len(sliders) != 1:
        raise RuntimeError(f"native mask brush slider {title!r} resolved to {len(sliders)} nodes")
    return sliders[0]


def _observe_mask_lifecycle(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    _ensure_tools_open(driver, driver.snapshot())
    _open_tool_slider(
        driver,
        tool_locator=DETAILS_TOOL_LOCATOR,
        slider_locator=DETAILS_SLIDER_LOCATOR,
    )
    _select_fit_to_screen(driver)
    baseline_path = output_root / "source.png"
    baseline_nodes, baseline_digest = _capture_stable_preview(
        driver,
        controller,
        baseline_path,
        description="mask scenario source baseline",
    )
    _drag_slider_with_feedback(
        driver,
        DETAILS_SLIDER_LOCATOR,
        65,
        tolerance=1.0,
    )
    full_effect_path = output_root / "before.png"
    _full_effect_nodes, full_effect_digest = _capture_stable_preview(
        driver,
        controller,
        full_effect_path,
        description="unmasked details effect",
    )
    driver.press_first("ButtonTabsItem_Masking")
    _wait_for(
        driver,
        lambda current: _has(current, "DrawingTool_Brush"),
        description="native masking tools visible",
    )
    driver.press_first("DrawingTool_Brush")
    _wait_for(
        driver,
        lambda current: all(
            any(node.role == "AXStaticText" and node.value == title for node in current)
            for title in ("大小", "柔和度", "强度")
        ),
        description="native mask brush controls visible",
    )
    brush_values: dict[str, float] = {}
    for title, value in (("大小", 80), ("柔和度", 24), ("强度", 70)):
        slider = _mask_brush_slider(driver.snapshot(), title)
        driver.set_value_at(slider.index, value)
        updated = _wait_for(
            driver,
            lambda current, t=title, v=value: abs(float(_mask_brush_slider(current, t).value) - v) <= 0.5,
            description=f"mask brush {title} set to {value}",
        )
        brush_values[title] = float(_mask_brush_slider(updated, title).value)

    preview = _node(driver.snapshot(), PREVIEW_LOCATOR)
    if preview.position is None or preview.size is None:
        raise RuntimeError("native preview geometry unavailable for mask stroke")
    stroke_start = (
        round(preview.position[0] + preview.size[0] * 0.25),
        round(preview.position[1] + preview.size[1] * 0.5),
    )
    stroke_end = (
        round(preview.position[0] + preview.size[0] * 0.75),
        stroke_start[1],
    )
    driver.drag_at(*stroke_start, *stroke_end)
    mask_path = output_root / "mask.png"
    mask_digest = _wait_for_preview_hash(
        driver,
        controller,
        mask_path,
        lambda digest: digest != full_effect_digest,
        description="brush mask preview rendered",
        timeout_seconds=20.0,
    )
    driver.target_shortcut(6, "command")
    undo_path = output_root / "undo.png"
    undo_digest = _wait_for_preview_hash(
        driver,
        controller,
        undo_path,
        lambda digest: digest != mask_digest,
        description="mask stroke undone",
        timeout_seconds=20.0,
    )
    driver.target_shortcut(6, "command", "shift")
    redo_path = output_root / "redo.png"
    redo_digest = _wait_for_preview_hash(
        driver,
        controller,
        redo_path,
        lambda digest: digest != undo_digest,
        description="mask stroke redone",
        timeout_seconds=20.0,
    )
    reset_buttons = [
        node
        for node in driver.snapshot()
        if node.role == "AXButton"
        and node.identifier == "_NS:177"
        and node.position is not None
        and node.size is not None
        and node.size[0] > 0
    ]
    if len(reset_buttons) != 1:
        raise RuntimeError(f"native details reset resolved to {len(reset_buttons)} buttons")
    driver.click_at(*_node_center(reset_buttons[0]))
    removed_path = output_root / "after.png"
    removed_nodes, removed_digest = _wait_for_preview_mae(
        driver,
        controller,
        removed_path,
        baseline_path,
        baseline_nodes,
        max_mae=1.0,
        description="details tool and mask reset to source",
    )
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, removed_nodes)
    restore_after_reset = _restore_original(driver)
    source_edits_reset = True
    return {
        "visible_assertions": [
            "mask-preview-visible",
            "brush-size-eighty",
            "brush-softness-twenty-four",
            "brush-strength-seventy",
            "mask-history-undo-redo-visible",
            "mask-removed",
        ],
        "wait_conditions": ["mask-preview-ready", "preview-image-ready"],
        "before_screenshot": full_effect_path.name,
        "after_screenshot": removed_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "brush_values": brush_values,
            "stroke_start": list(stroke_start),
            "stroke_end": list(stroke_end),
            "full_effect_preview_sha256": full_effect_digest,
            "source_preview_sha256": baseline_digest,
            "mask_preview_sha256": mask_digest,
            "undo_preview_sha256": undo_digest,
            "redo_preview_sha256": redo_digest,
            "reset_preview_sha256": removed_digest,
            "mask_history_changed_preview": undo_digest != mask_digest and redo_digest != undo_digest,
            "source_edits_reset": source_edits_reset,
            "restore_original_needed_after_tool_reset": restore_after_reset,
            "restore_original_performed_before_capture": reset_performed,
        },
    }


def _assert_restore_available(driver: ObservationDriver) -> None:
    driver.press_first(PHOTO_ACTIONS_LOCATOR)
    menu = _wait_for(
        driver,
        lambda current: _has(current, RESET_ALL_EDITS_LOCATOR),
        description="restore-original action available after effect",
    )
    reset = _node(menu, RESET_ALL_EDITS_LOCATOR)
    try:
        if reset.enabled is not True:
            raise RuntimeError("native effect did not create an enabled restore-original action")
    finally:
        driver.cancel()
    _wait_for(
        driver,
        lambda current: not _has(current, RESET_ALL_EDITS_LOCATOR),
        description="photo actions menu dismissed",
    )


def _observe_edit_toggle_collapse(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    nodes = _ensure_single_image(driver, controller)
    if not _has(nodes, DEFAULT_TOOL_LOCATOR):
        driver.press_first(TOOLS_LOCATOR)
        nodes = _wait_for(
            driver,
            lambda current: _has(current, DEFAULT_TOOL_LOCATOR),
            description="editor panels open",
        )
    before_preview = _node(nodes, PREVIEW_LOCATOR)
    before_path = output_root / "before.png"
    controller.screenshot_window(before_path)

    driver.press_first(TOOLS_LOCATOR)
    collapsed = _wait_for(
        driver,
        lambda current: (
            not _has(current, DEFAULT_TOOL_LOCATOR)
            and _preview_position(current) != before_preview.position
        ),
        description="editor panels collapsed",
    )
    collapsed_preview = _node(collapsed, PREVIEW_LOCATOR)
    if before_preview.position == collapsed_preview.position:
        raise RuntimeError("native canvas did not expand when editor panels collapsed")

    driver.press_first(TOOLS_LOCATOR)
    restored = _wait_for(
        driver,
        lambda current: (
            _has(current, DEFAULT_TOOL_LOCATOR)
            and _preview_position(current) == before_preview.position
        ),
        description="editor panels restored",
    )
    restored_preview = _node(restored, PREVIEW_LOCATOR)
    if restored_preview.position != before_preview.position:
        raise RuntimeError("native canvas did not return to its original layout")

    after_path = output_root / "after.png"
    accessibility_path = output_root / "accessibility.json"
    controller.screenshot_window(after_path)
    driver.write_snapshot(accessibility_path, restored)
    return {
        "visible_assertions": [
            "canvas-expands-when-collapsed",
            "editor-panels-restored",
        ],
        "wait_conditions": ["layout-settled"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "before_preview_position": before_preview.position,
            "collapsed_preview_position": collapsed_preview.position,
            "restored_preview_position": restored_preview.position,
            "tool_list_hidden_while_collapsed": True,
        },
    }


def _observe_catalog_select(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    driver.cancel()
    driver.press_first("目录")
    catalog_nodes = _wait_for(
        driver,
        lambda current: any(
            node.identifier == CATALOG_FILENAME_LOCATOR and node.value == SINGLE_IMAGE.stem
            for node in current
        ),
        description="existing catalog fixture visible",
    )
    filename = next(
        node
        for node in catalog_nodes
        if node.identifier == CATALOG_FILENAME_LOCATOR and node.value == SINGLE_IMAGE.stem
    )
    if filename.position is None:
        raise RuntimeError("native catalog filename has no position")
    thumbnails = [
        node
        for node in catalog_nodes
        if node.role == "AXImage"
        and node.position is not None
        and node.size is not None
        and node.size[0] > 100
        and 0 < node.position[1] - filename.position[1] <= 40
        and abs(node.position[0] - filename.position[0]) <= 2
    ]
    if len(thumbnails) != 1:
        raise RuntimeError(f"native existing catalog thumbnail resolved to {len(thumbnails)} nodes")
    before_path = output_root / "before.png"
    controller.screenshot_window(before_path)
    driver.click_at(*_node_center(thumbnails[0]))
    driver.press_first(TOOLS_LOCATOR)
    edited_nodes = _wait_for(
        driver,
        lambda current: _has(current, PREVIEW_LOCATOR) and _has(current, DEFAULT_TOOL_LOCATOR),
        description="catalog fixture opened in edit workspace",
    )
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, edited_nodes)
    return {
        "visible_assertions": [
            "filename-visible",
            "edit-workspace-selected",
            "preview-image-ready",
        ],
        "wait_conditions": ["catalog-record-visible", "preview-image-ready"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "fixture_filename": SINGLE_IMAGE.name,
            "existing_record_reused": True,
            "duplicate_import_performed": False,
            "thumbnail_position": thumbnails[0].position,
            "preview_position": _node(edited_nodes, PREVIEW_LOCATOR).position,
        },
    }


def _catalog_fixture_thumbnail(
    nodes: tuple[AccessibilityNode, ...],
) -> AccessibilityNode:
    filenames = [
        node
        for node in nodes
        if node.identifier == CATALOG_FILENAME_LOCATOR and node.value == SINGLE_IMAGE.stem
    ]
    if len(filenames) != 1 or filenames[0].position is None:
        raise RuntimeError(f"native catalog fixture resolved to {len(filenames)} filename nodes")
    filename = filenames[0]
    thumbnails = [
        node
        for node in nodes
        if node.role == "AXImage"
        and node.position is not None
        and node.size is not None
        and node.size[0] > 100
        and 0 < node.position[1] - filename.position[1] <= 40
        and abs(node.position[0] - filename.position[0]) <= 2
    ]
    if len(thumbnails) != 1:
        raise RuntimeError(f"native catalog fixture resolved to {len(thumbnails)} thumbnails")
    return thumbnails[0]


def _catalog_thumbnail_for_name(
    nodes: tuple[AccessibilityNode, ...], name: str
) -> AccessibilityNode:
    filenames = [
        node
        for node in nodes
        if node.identifier == CATALOG_FILENAME_LOCATOR and str(node.value or "") == name
    ]
    if len(filenames) != 1 or filenames[0].position is None:
        raise RuntimeError(f"native catalog record {name!r} resolved to {len(filenames)} labels")
    filename = filenames[0]
    thumbnails = [
        node
        for node in nodes
        if node.role == "AXImage"
        and node.position is not None
        and node.size is not None
        and node.size[0] > 100
        and 0 < node.position[1] - filename.position[1] <= 40
        and abs(node.position[0] - filename.position[0]) <= 2
    ]
    if len(thumbnails) != 1:
        raise RuntimeError(
            f"native catalog record {name!r} resolved to {len(thumbnails)} thumbnails"
        )
    return thumbnails[0]


def _catalog_scrollbar(nodes: tuple[AccessibilityNode, ...]) -> AccessibilityNode:
    scrollbars = [
        node
        for node in nodes
        if node.role == "AXScrollBar"
        and node.position is not None
        and node.position[0] > 1000
    ]
    if len(scrollbars) != 1:
        raise RuntimeError(f"native catalog grid resolved to {len(scrollbars)} scrollbars")
    return scrollbars[0]


def _catalog_record_selected(nodes: tuple[AccessibilityNode, ...], name: str) -> bool:
    thumbnail = _catalog_thumbnail_for_name(nodes, name)
    assert thumbnail.position is not None and thumbnail.size is not None
    left, top = thumbnail.position
    width, height = thumbnail.size
    return any(
        node.role == "AXButton"
        and node.help == "标记为拒绝的"
        and node.position is not None
        and left <= node.position[0] <= left + width
        and abs(node.position[1] - (top + height + 8)) <= 4
        for node in nodes
    )


def _observe_catalog_folder_scroll(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    driver.cancel()
    driver.press_first("目录")
    catalog = _wait_for(
        driver,
        lambda current: (
            any(node.value == VALIDATION_FOLDER_NAME for node in current)
            and any(node.identifier == CATALOG_FILENAME_LOCATOR for node in current)
        ),
        description="catalog validation folder and long collection ready",
    )
    initial_asset_count = sum(
        node.identifier == CATALOG_FILENAME_LOCATOR for node in catalog
    )
    scrollbar = _catalog_scrollbar(catalog)
    driver.set_value_at(scrollbar.index, 0)
    catalog_top = _wait_for(
        driver,
        lambda current: (
            float(_catalog_scrollbar(current).value or 0) == 0
            and _catalog_thumbnail_for_name(current, CATALOG_SCROLL_SELECTION).position[1] >= 0
        ),
        description="catalog grid at top",
    )

    folder_nodes = [
        node
        for node in catalog_top
        if node.value == VALIDATION_FOLDER_NAME
        and node.position is not None
        and node.size is not None
    ]
    if len(folder_nodes) != 1:
        raise RuntimeError(
            f"native validation folder resolved to {len(folder_nodes)} visible nodes"
        )
    folder = folder_nodes[0]
    driver.right_click_at(*_node_center(folder))
    menu = _wait_for(
        driver,
        lambda current: _has(current, "importImages:")
        and _exposes(current, "导入图片到该文件夹…"),
        description="validation folder context menu visible",
    )
    context_path = output_root / "folder-context-menu.png"
    controller.screenshot_window(context_path)
    import_action = _node(menu, "importImages:")
    if import_action.title != "导入图片到该文件夹…" or import_action.enabled is not True:
        raise RuntimeError("native validation folder import action is not enabled and exact")
    driver.cancel()

    selectable = _wait_for(
        driver,
        lambda current: not _has(current, "importImages:")
        and float(_catalog_scrollbar(current).value or 0) == 0,
        description="folder context menu dismissed",
    )
    selected_thumbnail = _catalog_thumbnail_for_name(selectable, CATALOG_SCROLL_SELECTION)
    driver.click_at(*_node_center(selected_thumbnail))
    selected_top = _wait_for(
        driver,
        lambda current: _catalog_record_selected(current, CATALOG_SCROLL_SELECTION),
        description="catalog record selected",
    )
    before_path = output_root / "before.png"
    controller.screenshot_window(before_path)

    scrollbar = _catalog_scrollbar(selected_top)
    driver.set_value_at(scrollbar.index, 1)
    catalog_bottom = _wait_for(
        driver,
        lambda current: (
            float(_catalog_scrollbar(current).value or 0) > 0
            and max(
                node.position[1]
                for node in current
                if node.identifier == CATALOG_FILENAME_LOCATOR and node.position is not None
            )
            < 900
        ),
        description="last catalog row visible",
    )
    bottom_path = output_root / "catalog-bottom.png"
    controller.screenshot_window(bottom_path)
    bottom_scroll_value = float(_catalog_scrollbar(catalog_bottom).value or 0)
    bottom_filename = max(
        (
            node
            for node in catalog_bottom
            if node.identifier == CATALOG_FILENAME_LOCATOR and node.position is not None
        ),
        key=lambda node: node.position[1],
    )

    scrollbar = _catalog_scrollbar(catalog_bottom)
    driver.set_value_at(scrollbar.index, 0)
    final_nodes = _wait_for(
        driver,
        lambda current: (
            float(_catalog_scrollbar(current).value or 0) == 0
            and _catalog_record_selected(current, CATALOG_SCROLL_SELECTION)
        ),
        description="selected catalog record preserved after scroll roundtrip",
    )
    final_asset_count = sum(
        node.identifier == CATALOG_FILENAME_LOCATOR for node in final_nodes
    )
    if final_asset_count != initial_asset_count:
        raise RuntimeError(
            f"native catalog asset count changed: {initial_asset_count} -> {final_asset_count}"
        )
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "folder-context-menu-visible",
            "import-action-visible",
            "last-catalog-row-visible",
            "selection-preserved-after-scroll",
        ],
        "wait_conditions": ["catalog-layout-settled"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "validation_folder": VALIDATION_FOLDER_NAME,
            "folder_context_menu_screenshot": context_path.name,
            "import_action_identifier": import_action.identifier,
            "import_action_title": import_action.title,
            "import_action_enabled": import_action.enabled,
            "selected_asset_name": CATALOG_SCROLL_SELECTION,
            "initial_asset_count": initial_asset_count,
            "final_asset_count": final_asset_count,
            "bottom_scroll_value": bottom_scroll_value,
            "bottom_filename": bottom_filename.value,
            "catalog_bottom_screenshot": bottom_path.name,
            "catalog_mutation_performed": False,
        },
    }


def _open_catalog_context(
    driver: ObservationDriver,
) -> tuple[AccessibilityNode, ...]:
    nodes = driver.snapshot()
    thumbnail = _catalog_fixture_thumbnail(nodes)
    driver.right_click_at(*_node_center(thumbnail))
    return _wait_for(
        driver,
        lambda current: _has(current, "Main.Image.SetRating") and _has(current, "Main.Image.Rotate"),
        description="catalog photo context menu visible",
    )


def _observe_catalog_photo_context(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    driver.press_first("目录")
    _wait_for(
        driver,
        lambda current: any(
            node.identifier == CATALOG_FILENAME_LOCATOR and node.value == SINGLE_IMAGE.stem
            for node in current
        ),
        description="catalog fixture visible",
    )
    before_path = output_root / "before.png"
    controller.screenshot_window(before_path)
    before_digest = _sha256(before_path)

    menu = _open_catalog_context(driver)
    rating = _node(menu, "Main.Image.SetRating")
    driver.mouse_move_at(*_node_center(rating))
    _wait_for(
        driver,
        lambda current: _has(current, "Main.Image.SetRating.5Star"),
        description="five-star rating submenu visible",
    )
    submenu_path = output_root / "rating-submenu.png"
    controller.screenshot_window(submenu_path)
    driver.press_first("Main.Image.SetRating.5Star")

    menu = _open_catalog_context(driver)
    rating = _node(menu, "Main.Image.SetRating")
    driver.mouse_move_at(*_node_center(rating))
    _wait_for(
        driver,
        lambda current: _has(current, "Main.Image.SetRating.5Star"),
        description="five-star rating submenu reopened",
    )
    five_star_mark = driver.read_attribute(
        "Main.Image.SetRating.5Star", "AXMenuItemMarkChar"
    )
    if five_star_mark != "✓":
        raise RuntimeError(f"native five-star rating has no check mark: {five_star_mark!r}")
    five_star_selected = True
    driver.cancel()

    menu = _open_catalog_context(driver)
    driver.press_first("Main.Image.Rotate")
    _wait_for(
        driver,
        lambda current: _has(current, "Main.Image.Rotate.RotateRight"),
        description="catalog rotation submenu visible",
    )
    driver.press_first("Main.Image.Rotate.RotateRight")
    rotated_path = output_root / "rotated-right.png"
    _wait_for(
        driver,
        lambda current: _has(current, CATALOG_FILENAME_LOCATOR),
        description="catalog right rotation applied",
    )
    controller.screenshot_window(rotated_path)
    rotated_digest = _sha256(rotated_path)
    if rotated_digest == before_digest:
        raise RuntimeError("catalog right rotation did not change the visible catalog")

    _open_catalog_context(driver)
    driver.press_first("Main.Image.Rotate")
    _wait_for(
        driver,
        lambda current: _has(current, "Main.Image.Rotate.RotateLeft"),
        description="catalog inverse rotation submenu visible",
    )
    driver.press_first("Main.Image.Rotate.RotateLeft")
    final_nodes = _wait_for(
        driver,
        lambda current: any(
            node.identifier == CATALOG_FILENAME_LOCATOR and node.value == SINGLE_IMAGE.stem
            for node in current
        ),
        description="catalog rotation roundtrip completed",
    )
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)

    _open_catalog_context(driver)
    rating = _node(driver.snapshot(), "Main.Image.SetRating")
    driver.mouse_move_at(*_node_center(rating))
    _wait_for(driver, lambda current: _has(current, "Main.Image.SetRating.None"), description="rating cleanup menu")
    driver.press_first("Main.Image.SetRating.None")
    return {
        "visible_assertions": [
            "parent-and-child-menu-visible",
            "five-star-state-visible",
            "preview-rotation-visible",
            "rotation-roundtrip-restored",
        ],
        "wait_conditions": ["catalog-record-updated"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "rating_submenu_screenshot": submenu_path.name,
            "five_star_selected": five_star_selected,
            "five_star_menu_mark": five_star_mark,
            "rotated_screenshot": rotated_path.name,
            "before_screenshot_sha256": before_digest,
            "rotated_screenshot_sha256": rotated_digest,
            "same_asset_filename": SINGLE_IMAGE.name,
            "destructive_trash_action_executed": False,
            "rating_cleaned_up_after_capture": True,
        },
    }


def _observe_preset_apply(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    nodes = _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    nodes = driver.snapshot()
    if not _has(nodes, PRESET_BACK_LOCATOR) and not any(
        node.value in {PRESET_CATEGORY, PRESET_NAME} for node in nodes
    ):
        driver.press_first("NavigationPanel.Tab.Presets")
    nodes = _wait_for(
        driver,
        lambda current: (
            _has(current, PRESET_BACK_LOCATOR)
            or any(node.value == PRESET_CATEGORY for node in current)
        ),
        description="presets workspace ready",
    )
    if not _has(nodes, PRESET_BACK_LOCATOR):
        category = [
            node
            for node in nodes
            if (
                node.identifier == f"TemplatePackGridCollectionViewItem.{PRESET_CATEGORY}"
                or node.value == PRESET_CATEGORY
            )
            and node.position is not None
            and node.size is not None
        ]
        labels = [node for node in category if node.value == PRESET_CATEGORY]
        target = None
        if len(labels) == 1:
            label = labels[0]
            label_center = _node_center(label)
            candidates = [
                node
                for node in nodes
                if node.role == "AXButton"
                and node.position is not None
                and node.size is not None
                and node.position[0] <= label_center[0] <= node.position[0] + node.size[0]
                and node.position[1] <= label_center[1] <= node.position[1] + node.size[1]
            ]
            target = (
                min(candidates, key=lambda node: node.size[0] * node.size[1])
                if candidates
                else None
            )
        if target is None:
            raise RuntimeError(f"native preset category resolved to {len(category)} nodes")
        driver.ax_press_at(target.index)
        nodes = _wait_for(
            driver,
            lambda current: (
                _has(current, PRESET_BACK_LOCATOR)
                and any(node.value == PRESET_NAME for node in current)
            ),
            description="preset collection ready",
        )
    names = [node for node in nodes if node.value == PRESET_NAME]
    if len(names) != 1 or names[0].position is None:
        raise RuntimeError(f"native preset name resolved to {len(names)} nodes")
    name = names[0]
    rows = [
        node
        for node in nodes
        if node.role == "AXButton"
        and node.identifier == "TemplateCollectionDetailContentView.unknown"
        and node.position is not None
        and node.size is not None
        and node.position[1] <= name.position[1] <= node.position[1] + node.size[1]
    ]
    if len(rows) != 1:
        raise RuntimeError(f"native preset row resolved to {len(rows)} nodes")
    before_path = output_root / "before.png"
    _, before_digest = _capture_stable_preview(
        driver,
        controller,
        before_path,
        description="preview before preset apply",
    )
    driver.click_at(*_node_center(rows[0]))
    after_path = output_root / "after.png"
    after_digest = _wait_for_preview_hash(
        driver,
        controller,
        after_path,
        lambda digest: digest != before_digest,
        description="preset preview applied",
        timeout_seconds=20,
    )
    final_nodes = driver.snapshot()
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "preset-selected",
            "preview-image-ready",
            "busy-state-cleared",
        ],
        "wait_conditions": [
            "preset-preview-ready",
            "project-edit-stack-updated",
        ],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "preset_name": PRESET_NAME,
            "preset_category": PRESET_CATEGORY,
            "before_preview_sha256": before_digest,
            "after_preview_sha256": after_digest,
            "preview_changed": after_digest != before_digest,
            "new_export_created": False,
            "source_edits_reset": True,
            "restore_original_performed": reset_performed,
        },
    }


def _preview_button(nodes: tuple[AccessibilityNode, ...]) -> AccessibilityNode:
    matches = [node for node in nodes if (node.help or "").startswith("预览")]
    if len(matches) != 1:
        raise RuntimeError(f"native before/after preview button resolved to {len(matches)} nodes")
    if not matches[0].enabled:
        raise RuntimeError("native before/after preview button is disabled")
    return matches[0]


def _node_center(node: AccessibilityNode) -> tuple[int, int]:
    if node.position is None or node.size is None:
        raise RuntimeError("native accessibility element has no bounds")
    return (
        round(node.position[0] + node.size[0] / 2),
        round(node.position[1] + node.size[1] / 2),
    )


def _observe_before_after_compare(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    preset_setup = _observe_preset_apply(
        driver,
        controller,
        output_root / "preset-setup",
    )
    preset_evidence = preset_setup["assertion_evidence"]
    reset_performed = bool(preset_evidence["restore_original_performed"])
    original_digest = str(preset_evidence["before_preview_sha256"])
    original_path = output_root / "preset-setup" / str(preset_setup["before_screenshot"])
    nodes = driver.snapshot()
    preview_button = _preview_button(nodes)
    before_path = output_root / "before.png"
    edited_preview_digest = _wait_for_preview_hash(
        driver,
        controller,
        before_path,
        lambda digest: digest != original_digest,
        description="known edit rendered before compare",
    )
    before_digest = _sha256(before_path)
    button_point = _node_center(preview_button)

    held = False
    try:
        driver.mouse_down_at(*button_point)
        held = True
        source_path = output_root / "source.png"
        source_digest = _wait_for_preview_hash(
            driver,
            controller,
            source_path,
            lambda digest: digest != edited_preview_digest,
            description="source image visible",
        )
        driver.mouse_up_at(*button_point)
        held = False
        after_path = output_root / "after.png"
        restored_nodes, restored_preview_digest = _capture_stable_preview(
            driver,
            controller,
            after_path,
            description="edited preview restored",
        )
        after_digest = _sha256(after_path)
    finally:
        if held:
            driver.mouse_up_at(*button_point)

    final_nodes = driver.snapshot()
    restored_mae = _preview_region_mae(
        before_path,
        nodes,
        after_path,
        restored_nodes,
    )
    if restored_mae > 1.0:
        raise RuntimeError(
            f"native edited preview did not restore within tolerance: MAE={restored_mae:.4f}"
        )
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "source-image-visible-while-held",
            "edited-preview-restored",
            "compare-button-selected-state-correct",
        ],
        "wait_conditions": ["source-image-ready", "preview-image-ready"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "source_screenshot": source_path.name,
            "source_preview_sha256": source_digest,
            "edited_screenshot_sha256": before_digest,
            "restored_screenshot_sha256": after_digest,
            "edited_preview_sha256": edited_preview_digest,
            "restored_preview_sha256": restored_preview_digest,
            "source_differs_from_edited": source_digest != edited_preview_digest,
            "restored_matches_edited": restored_mae <= 1.0,
            "restored_preview_mae": restored_mae,
            "source_edits_reset": True,
            "restore_original_performed": reset_performed,
            "known_edit": f"{PRESET_CATEGORY}/{PRESET_NAME}",
            "original_screenshot": original_path.name,
            "original_preview_sha256": original_digest,
        },
    }


def _observe_edit_slider_drag(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    _ensure_details_slider(driver, controller)
    _select_fit_to_screen(driver)
    driver.set_value_first(DETAILS_SLIDER_LOCATOR, 0)
    _wait_for_value(
        driver,
        DETAILS_SLIDER_LOCATOR,
        0,
        description="details slider reset",
    )
    before_path = output_root / "before.png"
    _, before_digest = _capture_stable_preview(
        driver,
        controller,
        before_path,
        description="details baseline preview",
    )

    _drag_slider_to(driver, driver.snapshot(), DETAILS_SLIDER_LOCATOR, 65)
    readback = _wait_for_value(
        driver,
        DETAILS_SLIDER_LOCATOR,
        65,
        description="details amount 65",
    )
    after_path = output_root / "after.png"
    after_digest = _wait_for_preview_hash(
        driver,
        controller,
        after_path,
        lambda digest: digest != before_digest,
        description="details preview applied",
    )
    final_nodes = driver.snapshot()
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "details-tool-selected",
            "amount-value-0.65",
            "preview-image-ready",
        ],
        "wait_conditions": ["preview-image-ready"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "native_slider_value": readback,
            "normalized_slider_value": readback / 100,
            "before_preview_sha256": before_digest,
            "after_preview_sha256": after_digest,
            "preview_changed": after_digest != before_digest,
            "apply_button_required": False,
            "source_edits_reset": True,
            "restore_original_performed": reset_performed,
        },
    }


def _observe_undo_redo(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    _ensure_details_slider(driver, controller)
    _select_fit_to_screen(driver)
    driver.set_value_first(DETAILS_SLIDER_LOCATOR, 0)
    _wait_for_value(
        driver,
        DETAILS_SLIDER_LOCATOR,
        0,
        description="details reset before undo scenario",
    )
    reset_path = output_root / "reset.png"
    _, reset_digest = _capture_stable_preview(
        driver,
        controller,
        reset_path,
        description="reset preview before undo scenario",
    )
    _drag_slider_to(driver, driver.snapshot(), DETAILS_SLIDER_LOCATOR, 65)
    edited_nodes = _wait_for(
        driver,
        lambda current: (
            isinstance(_node(current, DETAILS_SLIDER_LOCATOR).value, (int, float))
            and abs(float(_node(current, DETAILS_SLIDER_LOCATOR).value)) >= 50
        ),
        description="non-zero details edit ready for undo",
    )
    edited_slider_value = float(_node(edited_nodes, DETAILS_SLIDER_LOCATOR).value)
    before_path = output_root / "before.png"
    edited_digest = _wait_for_preview_hash(
        driver,
        controller,
        before_path,
        lambda digest: digest != reset_digest,
        description="edited preview before undo",
    )

    _press_shortcut(driver, 6, "command")
    undo_path = output_root / "undo.png"
    undo_digest = _wait_for_preview_hash(
        driver,
        controller,
        undo_path,
        lambda digest: digest == reset_digest,
        description="preview reverted after undo",
    )

    _press_shortcut(driver, 6, "command", "shift")
    after_path = output_root / "after.png"
    redo_digest = _wait_for_preview_hash(
        driver,
        controller,
        after_path,
        lambda digest: digest == edited_digest,
        description="preview restored after redo",
    )
    final_nodes = driver.snapshot()
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "preview-reverts-after-undo",
            "preview-restores-after-redo",
        ],
        "wait_conditions": [
            "project-edit-stack-updated",
            "preview-image-ready",
        ],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "undo_screenshot": undo_path.name,
            "reset_screenshot": reset_path.name,
            "reset_preview_sha256": reset_digest,
            "edited_preview_sha256": edited_digest,
            "undo_preview_sha256": undo_digest,
            "redo_preview_sha256": redo_digest,
            "undo_changed_preview": undo_digest != edited_digest,
            "redo_restored_preview": redo_digest == edited_digest,
            "undo_shortcut": "command-z",
            "redo_shortcut": "command-shift-z",
            "native_slider_value_before_undo": edited_slider_value,
            "source_edits_reset": True,
            "restore_original_performed": reset_performed,
        },
    }


def _observe_zoom_pan(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    nodes = _ensure_single_image(driver, controller)
    if not _has(nodes, ZOOM_LOCATOR):
        raise RuntimeError("native zoom control is unavailable")
    _select_fit_to_screen(driver)
    before_path = output_root / "before.png"
    baseline_nodes, baseline_digest = _capture_stable_preview(
        driver,
        controller,
        before_path,
        description="fit-to-screen baseline",
    )
    baseline_preview = _node(baseline_nodes, PREVIEW_LOCATOR)
    baseline_zoom = _zoom_title(baseline_nodes)

    zoomed_nodes = _select_zoom_percentage(driver, "200%")
    zoomed_preview = _node(zoomed_nodes, PREVIEW_LOCATOR)
    zoomed_zoom = _zoom_title(zoomed_nodes)
    zoomed_center = _node_center(zoomed_preview)

    driver.drag_at(
        zoomed_center[0],
        zoomed_center[1],
        zoomed_center[0] + 48,
        zoomed_center[1] + 32,
    )
    panned_nodes = _wait_for(
        driver,
        lambda current: _node(current, PREVIEW_LOCATOR).position != zoomed_preview.position,
        description="zoomed image panned",
    )
    panned_preview = _node(panned_nodes, PREVIEW_LOCATOR)

    _select_fit_to_screen(driver)
    restored_nodes = _wait_for(
        driver,
        lambda current: (
            _node(current, PREVIEW_LOCATOR).position == baseline_preview.position
            and _node(current, PREVIEW_LOCATOR).size == baseline_preview.size
        ),
        description="fit-to-screen geometry restored",
    )
    after_path = output_root / "after.png"
    final_nodes, restored_digest = _capture_stable_preview(
        driver,
        controller,
        after_path,
        description="fit-to-screen preview restored",
    )
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "zoom-indicator-changes",
            "pan-offset-visible",
            "fit-to-view-restores-canvas",
        ],
        "wait_conditions": ["layout-settled", "preview-image-ready"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "baseline_zoom": baseline_zoom,
            "zoomed_zoom": zoomed_zoom,
            "baseline_preview_position": baseline_preview.position,
            "zoomed_preview_position": zoomed_preview.position,
            "panned_preview_position": panned_preview.position,
            "restored_preview_position": _node(restored_nodes, PREVIEW_LOCATOR).position,
            "baseline_preview_size": baseline_preview.size,
            "restored_preview_size": _node(restored_nodes, PREVIEW_LOCATOR).size,
            "baseline_preview_sha256": baseline_digest,
            "restored_preview_sha256": restored_digest,
        },
    }


def _observe_compare_zoom_pan(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    """Capture the native press-and-hold compare contract followed by zoom/pan/fit."""

    compare_root = output_root / "compare"
    zoom_root = output_root / "zoom"
    compare_root.mkdir(parents=True, exist_ok=True)
    zoom_root.mkdir(parents=True, exist_ok=True)
    compare = _observe_before_after_compare(driver, controller, compare_root)
    zoom = _observe_zoom_pan(driver, controller, zoom_root)
    compare_evidence = dict(compare["assertion_evidence"])
    zoom_evidence = dict(zoom["assertion_evidence"])
    return {
        "visible_assertions": [
            "source-image-visible-during-compare",
            "edited-preview-restored",
            "zoom-indicator-two-hundred",
            "pan-offset-visible",
            "fit-restores-canvas",
        ],
        "wait_conditions": ["source-image-ready", "preview-image-ready"],
        "before_screenshot": str(Path("compare") / compare["before_screenshot"]),
        "after_screenshot": str(Path("zoom") / zoom["after_screenshot"]),
        "accessibility_snapshot": str(
            Path("zoom") / zoom["accessibility_snapshot"]
        ),
        "assertion_evidence": {
            **compare_evidence,
            **zoom_evidence,
            "native_compare_gesture": "press-and-hold",
            "zoom_indicator_two_hundred": zoom_evidence.get("zoomed_zoom") == "200%",
            "fit_restored_canvas": (
                zoom_evidence.get("baseline_preview_position")
                == zoom_evidence.get("restored_preview_position")
                and zoom_evidence.get("baseline_preview_size")
                == zoom_evidence.get("restored_preview_size")
            ),
        },
    }


def _observe_export_dialog(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    before_path = output_root / "before.png"
    baseline_nodes, baseline_digest = _capture_stable_preview(
        driver,
        controller,
        before_path,
        description="original preview before export scenario",
    )
    nodes = _ensure_details_slider(driver, controller)
    _drag_slider_to(driver, nodes, DETAILS_SLIDER_LOCATOR, 65)
    _wait_for_value(
        driver,
        DETAILS_SLIDER_LOCATOR,
        65,
        description="details effect ready before export",
    )
    effect_path = output_root / "effect.png"
    effect_digest = _wait_for_preview_hash(
        driver,
        controller,
        effect_path,
        lambda digest: digest != baseline_digest,
        description="effect visibly applied before export",
    )
    _assert_restore_available(driver)

    menu_nodes = driver.open_export_menu()
    export_items = [node for node in menu_nodes if node.identifier == "NSMenuItem.NewExport"]
    if len(export_items) != 1 or export_items[0].enabled is not True:
        raise RuntimeError(
            f"native New Export menu item resolved to {len(export_items)} enabled nodes"
        )
    driver.ax_press("NSMenuItem.NewExport")
    _wait_for_read_value(
        driver,
        "saveAsNameTextField",
        description="native export filename field",
    )
    export_name = "zpixel-interaction-check"
    written = driver.set_value_first("saveAsNameTextField", export_name)
    readback = driver.read_value_first("saveAsNameTextField")
    if str(written) != export_name or str(readback) != export_name:
        raise RuntimeError(f"native export filename readback mismatch: {written!r}/{readback!r}")
    dialog_path = output_root / "dialog.png"
    controller.screenshot_window(dialog_path)
    driver.cancel()
    final_nodes = _wait_for(
        driver,
        lambda current: not _has(current, "saveAsNameTextField") and _has(current, PREVIEW_LOCATOR),
        description="native export dialog cancelled",
    )
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "export-action-available",
            "export-filename-editable",
            "effect-restorable-before-export",
        ],
        "wait_conditions": ["export-dialog-ready"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "dialog_screenshot": dialog_path.name,
            "effect_screenshot": effect_path.name,
            "export_filename_written": export_name,
            "export_filename_readback": readback,
            "source_edits_reset": True,
            "restore_original_performed": reset_performed,
            "effect_preview_sha256": effect_digest,
            "baseline_preview_sha256": baseline_digest,
            "effect_changed_preview": effect_digest != baseline_digest,
            "restore_original_available_before_export": True,
            "duplicate_export_created": False,
            "export_menu_item_enabled": export_items[0].enabled,
            "baseline_preview_position": _node(baseline_nodes, PREVIEW_LOCATOR).position,
        },
    }


def _open_native_export_sheet(
    driver: ObservationDriver,
) -> tuple[tuple[AccessibilityNode, ...], AccessibilityNode]:
    menu_nodes = driver.open_export_menu()
    export_items = [
        node
        for node in menu_nodes
        if node.identifier == "NSMenuItem.NewExport" and node.enabled is True
    ]
    if len(export_items) != 1:
        raise RuntimeError(f"native New Export resolved to {len(export_items)} enabled items")
    driver.ax_press("NSMenuItem.NewExport")
    sheet = _wait_for(
        driver,
        lambda current: (
            _has(current, "saveAsNameTextField")
            and _has(current, "where popup")
            and _has(current, "OKButton")
        ),
        description="native export sheet ready",
        timeout_seconds=20.0,
    )
    return sheet, export_items[0]


def _ensure_native_export_directory(
    driver: ObservationDriver,
    destination: Path,
) -> tuple[AccessibilityNode, ...]:
    destination.mkdir(parents=True, exist_ok=True)
    sheet = driver.snapshot()
    location = _node(sheet, "where popup")
    if location.value == destination.name:
        return sheet
    deadline = time.monotonic() + 8.0
    folder_field_nodes: tuple[AccessibilityNode, ...] | None = None
    while time.monotonic() < deadline and folder_field_nodes is None:
        driver.open_go_to_folder()
        retry_deadline = min(deadline, time.monotonic() + 1.0)
        while time.monotonic() < retry_deadline:
            current = driver.snapshot()
            if any(node.identifier == "PathTextField" for node in current):
                folder_field_nodes = current
                break
            time.sleep(0.1)
    if folder_field_nodes is None:
        raise TimeoutError("Luminar did not expose export PathTextField")
    fields = [
        node
        for node in folder_field_nodes
        if node.identifier == "PathTextField"
    ]
    if len(fields) != 1:
        raise RuntimeError(f"export folder field resolved to {len(fields)} focused fields")
    driver.set_value_at(fields[0].index, str(destination))
    driver.confirm()
    return _wait_for(
        driver,
        lambda current: (
            _has(current, "where popup")
            and _node(current, "where popup").value == destination.name
        ),
        description="native export destination selected",
        timeout_seconds=20.0,
    )


def _configure_native_png_export(
    driver: ObservationDriver,
    *,
    export_name: str,
) -> dict[str, Any]:
    driver.set_value_first("saveAsNameTextField", export_name)
    sheet = driver.snapshot()
    format_control = [
        node
        for node in sheet
        if node.role == "AXPopUpButton" and node.value in {"JPEG", "PNG", "TIFF"}
    ]
    if len(format_control) != 1:
        raise RuntimeError(f"native export format control resolved to {len(format_control)} nodes")
    if format_control[0].value != "PNG":
        driver.press_at(format_control[0].index)
        _wait_for(
            driver,
            lambda current: any(
                node.role == "AXMenuItem" and node.title == "PNG" for node in current
            ),
            description="PNG export option visible",
        )
        driver.press_first("PNG")
    sheet = _wait_for(
        driver,
        lambda current: any(
            node.role == "AXPopUpButton" and node.value == "PNG" for node in current
        ),
        description="PNG export format selected",
    )
    resize = [
        node
        for node in sheet
        if node.role == "AXPopUpButton" and node.value in {"原始", "尺寸", "Original", "Dimensions"}
    ]
    if len(resize) != 1:
        raise RuntimeError(f"native export resize control resolved to {len(resize)} nodes")
    if resize[0].value not in {"尺寸", "Dimensions"}:
        driver.press_at(resize[0].index)
        _wait_for(
            driver,
            lambda current: any(
                node.role == "AXMenuItem" and node.title in {"尺寸", "Dimensions"}
                for node in current
            ),
            description="custom export dimensions option visible",
        )
        dimension_item = next(
            node
            for node in driver.snapshot()
            if node.role == "AXMenuItem" and node.title in {"尺寸", "Dimensions"}
        )
        driver.press_at(dimension_item.index)
    dimensions = _wait_for(
        driver,
        lambda current: any(
            node.role == "AXTextField" and node.enabled is True and node.value == "1080"
            for node in current
        ),
        description="export width field enabled",
    )
    width_fields = [
        node
        for node in dimensions
        if node.role == "AXTextField"
        and node.enabled is True
        and node.identifier is not None
        and node.position is not None
        and 700 <= node.position[0] <= 900
        and 450 <= node.position[1] <= 510
    ]
    if len(width_fields) != 2:
        raise RuntimeError(f"native export dimensions resolved to {len(width_fields)} fields")
    width = min(width_fields, key=lambda node: node.position[0])
    driver.set_value_at(width.index, "1080")
    final = driver.snapshot()
    profile_values = {
        "sRGB",
        "Display P3",
        "Adobe RGB (1998)",
        "ProPhoto RGB",
    }
    profile_controls = [
        node
        for node in final
        if node.role == "AXPopUpButton" and node.value in profile_values
    ]
    if len(profile_controls) != 1:
        observed = sorted(
            str(node.value)
            for node in final
            if node.role == "AXPopUpButton" and node.value is not None
        )
        raise RuntimeError(
            "native export profile control resolved to "
            f"{len(profile_controls)} nodes; popup values={observed}"
        )
    profile_control = profile_controls[0]
    if profile_control.value != "sRGB":
        driver.press_at(profile_control.index)
        profile_menu = _wait_for(
            driver,
            lambda current: any(
                node.role == "AXMenuItem" and node.title == "sRGB" for node in current
            ),
            description="sRGB export profile option visible",
        )
        srgb_items = [
            node
            for node in profile_menu
            if node.role == "AXMenuItem" and node.title == "sRGB"
        ]
        if len(srgb_items) != 1:
            raise RuntimeError(
                f"native sRGB export profile resolved to {len(srgb_items)} menu items"
            )
        driver.press_at(srgb_items[0].index)
        final = _wait_for(
            driver,
            lambda current: any(
                node.role == "AXPopUpButton" and node.value == "sRGB"
                for node in current
            ),
            description="sRGB export profile selected",
        )
        profile_control = next(
            node
            for node in final
            if node.role == "AXPopUpButton" and node.value == "sRGB"
        )
    return {
        "filename": driver.read_value_first("saveAsNameTextField"),
        "format": "PNG",
        "width": driver.read_value_first(width.identifier or "_NS:262"),
        "profile": profile_control.value,
    }


def _observe_export_dialog_file(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    _ensure_details_slider(driver, controller)
    _select_fit_to_screen(driver)
    before_path = output_root / "before.png"
    baseline_nodes, baseline_digest = _capture_stable_preview(
        driver,
        controller,
        before_path,
        description="export scenario baseline",
    )
    effect_value = _drag_slider_with_feedback(
        driver,
        DETAILS_SLIDER_LOCATOR,
        65,
        tolerance=1.0,
    )
    effect_path = output_root / "effect.png"
    effect_nodes = driver.snapshot()
    effect_digest = _wait_for_preview_hash(
        driver,
        controller,
        effect_path,
        lambda digest: digest != baseline_digest,
        description="export scenario effect rendered",
        timeout_seconds=20.0,
    )
    _assert_restore_available(driver)

    export_directory = output_root / "native-export"
    export_directory.mkdir(parents=True, exist_ok=True)
    export_name = "canonical-export"
    export_path = export_directory / f"{export_name}.png"
    native_export_path = output_root.parents[2] / "native-exports" / f"{export_name}.png"
    if export_path.exists() or native_export_path.exists():
        raise FileExistsError(
            f"canonical native export already exists: {export_path} or {native_export_path}"
        )

    first_sheet, first_export_item = _open_native_export_sheet(driver)
    if _node(first_sheet, "where popup").value != "native-exports":
        raise RuntimeError("native export sheet is not in the frozen native-exports directory")
    cancel_settings = _configure_native_png_export(driver, export_name=export_name)
    cancel_dialog_path = output_root / "cancel-dialog.png"
    controller.screenshot_window(cancel_dialog_path)
    driver.cancel()
    _wait_for(
        driver,
        lambda current: not _has(current, "saveAsNameTextField") and _has(current, PREVIEW_LOCATOR),
        description="configured export cancelled",
    )
    if export_path.exists() or native_export_path.exists():
        raise RuntimeError("cancelled native export created an output file")

    second_sheet, _ = _open_native_export_sheet(driver)
    if _node(second_sheet, "where popup").value != "native-exports":
        raise RuntimeError("second native export sheet changed destination")
    export_settings = _configure_native_png_export(driver, export_name=export_name)
    confirm_dialog_path = output_root / "confirm-dialog.png"
    controller.screenshot_window(confirm_dialog_path)
    driver.press_first("OKButton")
    wait_for_stable_file(native_export_path, timeout_seconds=60.0)
    native_export_path.replace(export_path)
    final_nodes = _wait_for(
        driver,
        lambda current: not _has(current, "saveAsNameTextField") and _has(current, PREVIEW_LOCATOR),
        description="native export completed",
        timeout_seconds=20.0,
    )
    with Image.open(export_path) as exported:
        exported_format = exported.format
        exported_size = exported.size
        exported_icc = bool(exported.info.get("icc_profile"))
    if exported_format != "PNG" or exported_size[0] != 1080:
        raise RuntimeError(
            f"native export metadata mismatch: format={exported_format}, size={exported_size}"
        )
    _assert_restore_available(driver)
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    source_edits_reset = _restore_original(driver)
    if not source_edits_reset:
        raise RuntimeError("export scenario effect was not restorable")
    return {
        "visible_assertions": [
            "export-dialog-ready",
            "filename-format-size-profile-readable",
            "cancel-closes-without-output",
            "export-completes-once",
        ],
        "wait_conditions": ["export-dialog-ready", "export-response-complete"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "cancel_dialog_screenshot": cancel_dialog_path.name,
            "confirm_dialog_screenshot": confirm_dialog_path.name,
            "cancel_settings": cancel_settings,
            "export_settings": export_settings,
            "cancel_created_zero_files": True,
            "export_file": str(export_path.relative_to(output_root)),
            "export_file_sha256": _sha256(export_path),
            "export_format": exported_format,
            "export_dimensions": list(exported_size),
            "export_has_icc_profile": exported_icc,
            "effect_value": effect_value,
            "effect_screenshot": effect_path.name,
            "effect_preview_sha256": effect_digest,
            "baseline_preview_sha256": baseline_digest,
            "export_menu_item_enabled": first_export_item.enabled,
            "effect_preview_position": _node(effect_nodes, PREVIEW_LOCATOR).position,
            "baseline_preview_position": _node(baseline_nodes, PREVIEW_LOCATOR).position,
            "restore_original_available_before_export": True,
            "source_edits_reset": source_edits_reset,
            "restore_original_performed_before_capture": reset_performed,
        },
    }


def _layer_thumbnails(
    nodes: tuple[AccessibilityNode, ...],
) -> list[AccessibilityNode]:
    return sorted(
        (
            node
            for node in nodes
            if node.role == "AXImage"
            and node.identifier == "_NS:33"
            and node.position is not None
            and node.size == (54, 54)
        ),
        key=lambda node: (node.position[1], node.position[0]),
    )


def _layer_context_action(
    driver: ObservationDriver,
    layer: AccessibilityNode,
    *,
    identifier: str,
    expected_titles: set[str],
) -> str:
    driver.right_click_at(*_node_center(layer))
    menu = _wait_for(
        driver,
        lambda current: any(
            node.role == "AXMenuItem"
            and node.identifier == identifier
            and node.title in expected_titles
            and node.enabled is True
            and node.size is not None
            and node.size[0] > 0
            and node.size[1] > 0
            for node in current
        ),
        description=f"layer context action {identifier} available",
    )
    matches = [
        node
        for node in menu
        if node.role == "AXMenuItem"
        and node.identifier == identifier
        and node.title in expected_titles
        and node.enabled is True
        and node.size is not None
        and node.size[0] > 0
        and node.size[1] > 0
    ]
    if len(matches) != 1:
        raise RuntimeError(f"native layer action {identifier} resolved to {len(matches)} nodes")
    title = str(matches[0].title)
    driver.ax_press_at(matches[0].index)
    _wait_for(
        driver,
        lambda current: not any(
            node.role == "AXMenu"
            and node.size is not None
            and node.size[0] > 0
            and node.size[1] > 0
            for node in current
        ),
        description=f"layer context action {title} applied",
    )
    return title


def _observe_layer_lifecycle(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    nodes = _ensure_single_image(driver, controller)
    reset_performed = _restore_original(driver)
    nodes = driver.snapshot()
    if not _has(nodes, DEFAULT_TOOL_LOCATOR):
        driver.press_first(TOOLS_LOCATOR)
        nodes = _wait_for(
            driver,
            lambda current: _has(current, DEFAULT_TOOL_LOCATOR),
            description="editor panels open for layer interaction",
        )
    initial_layers = _layer_thumbnails(nodes)
    if len(initial_layers) != 1:
        raise RuntimeError(
            f"native layer lifecycle requires one source layer, found {len(initial_layers)}"
        )

    driver.press_first("overlaysView_addLayerItem")
    library = _wait_for(
        driver,
        lambda current: _has(current, "overlaysView_loadImageButton"),
        description="native layer library open",
    )
    free_assets = [
        node
        for node in library
        if node.role == "AXImage"
        and node.identifier == "_NS:58"
        and node.position is not None
        and node.size is not None
    ]
    if not free_assets:
        raise RuntimeError("native layer library has no selectable free asset")
    driver.click_at(*_node_center(min(free_assets, key=lambda node: node.position)))
    layered = _wait_for(
        driver,
        lambda current: (
            len(_layer_thumbnails(current)) == 2 and _has(current, "Slider.LayerProperties.Opacity")
        ),
        description="overlay layer visible",
        timeout_seconds=20.0,
    )
    overlay = next(
        (
            node
            for node in _layer_thumbnails(layered)
            if str(node.help or "").casefold() != SINGLE_IMAGE.name.casefold()
        ),
        None,
    )
    source = next(
        (
            node
            for node in _layer_thumbnails(layered)
            if str(node.help or "").casefold() == SINGLE_IMAGE.name.casefold()
        ),
        None,
    )
    if overlay is None or source is None:
        raise RuntimeError("native source and overlay layers are not uniquely identifiable")

    ordered_top = overlay.position[1] < source.position[1]
    if not ordered_top:
        driver.drag_at(*_node_center(overlay), *_node_center(source))
        layered = _wait_for(
            driver,
            lambda current: any(
                str(node.help or "").casefold() != SINGLE_IMAGE.name.casefold()
                and node.position is not None
                and node.position[1] == min(item.position[1] for item in _layer_thumbnails(current))
                for node in _layer_thumbnails(current)
            ),
            description="overlay layer reordered to top",
        )
        overlay = _layer_thumbnails(layered)[0]

    driver.click_at(*_node_center(overlay))
    visible_path = output_root / "visible.png"
    visible_nodes, visible_digest = _capture_stable_preview(
        driver,
        controller,
        visible_path,
        description="overlay visible before visibility roundtrip",
    )

    hidden_title = _layer_context_action(
        driver,
        overlay,
        identifier="changeLayerVisibility:",
        expected_titles={"Hide Layer", "隐藏图层"},
    )
    hidden_path = output_root / "hidden.png"
    hidden_nodes, hidden_digest = _capture_stable_preview(
        driver,
        controller,
        hidden_path,
        description="overlay hidden",
    )
    if hidden_digest == visible_digest:
        raise RuntimeError("hiding the overlay did not change the native preview")
    hidden_overlay = next(
        node
        for node in _layer_thumbnails(hidden_nodes)
        if str(node.help or "").casefold() != SINGLE_IMAGE.name.casefold()
    )
    shown_title = _layer_context_action(
        driver,
        hidden_overlay,
        identifier="changeLayerVisibility:",
        expected_titles={"Show Layer", "显示图层", "显示层"},
    )
    restored_overlay = next(
        node
        for node in _layer_thumbnails(driver.snapshot())
        if str(node.help or "").casefold() != SINGLE_IMAGE.name.casefold()
    )
    driver.click_at(*_node_center(restored_overlay))
    driver.right_click_at(*_node_center(restored_overlay))
    visibility_menu = _wait_for(
        driver,
        lambda current: any(
            node.identifier == "changeLayerVisibility:"
            and node.title in {"Hide Layer", "隐藏图层", "隐藏层"}
            and node.size is not None
            and node.size[0] > 0
            for node in current
        ),
        description="restored overlay exposes hide action again",
    )
    restored_visibility_title = next(
        str(node.title)
        for node in visibility_menu
        if node.identifier == "changeLayerVisibility:"
        and node.title in {"Hide Layer", "隐藏图层", "隐藏层"}
        and node.size is not None
        and node.size[0] > 0
    )
    driver.cancel()
    shown_path = output_root / "shown.png"
    shown_nodes, shown_digest = _capture_stable_preview(
        driver,
        controller,
        shown_path,
        description="overlay restored after show",
    )
    visibility_roundtrip_mae = _preview_region_mae(
        visible_path,
        visible_nodes,
        shown_path,
        shown_nodes,
    )

    overlay = next(
        node
        for node in _layer_thumbnails(shown_nodes)
        if str(node.help or "").casefold() != SINGLE_IMAGE.name.casefold()
    )
    driver.click_at(*_node_center(overlay))
    layer_nodes = driver.snapshot()
    if not _has(layer_nodes, "Slider.LayerProperties.Opacity"):
        expand_locators = (
            "Luminar_Neo.AdjustListHeaderView.Layer Properties PRO.ExpandButton",
            "EditExpandButton_MPLayerProperties",
        )
        expand = next(
            (locator for locator in expand_locators if _has(layer_nodes, locator)),
            None,
        )
        if expand is None:
            raise RuntimeError("native layer properties cannot be expanded")
        driver.press_first(expand)
        _wait_for(
            driver,
            lambda current: _has(current, "Slider.LayerProperties.Opacity"),
            description="layer properties expanded after visibility roundtrip",
        )
    driver.set_value_first("Slider.LayerProperties.Opacity", 50)
    opacity_nodes = _wait_for(
        driver,
        lambda current: (
            isinstance(_node(current, "Slider.LayerProperties.Opacity").value, (int, float))
            and abs(float(_node(current, "Slider.LayerProperties.Opacity").value) - 50) <= 1
        ),
        description="overlay opacity 50 percent",
    )
    readback = float(_node(opacity_nodes, "Slider.LayerProperties.Opacity").value)

    driver.press_first("NSButton.LayerProperties.BlendMode")
    blend_menu = _wait_for(
        driver,
        lambda current: any(
            node.role == "AXMenuItem"
            and node.title in {"螢幕", "屏幕", "滤色", "Screen"}
            for node in current
        ),
        description="screen blend menu item available",
    )
    screen_items = [
        node
        for node in blend_menu
        if node.role == "AXMenuItem"
        and node.title in {"螢幕", "屏幕", "滤色", "Screen"}
    ]
    if len(screen_items) != 1:
        raise RuntimeError(f"native screen blend resolved to {len(screen_items)} nodes")
    driver.ax_press_at(screen_items[0].index)
    blended = _wait_for(
        driver,
        lambda current: (
            _node(current, "NSButton.LayerProperties.BlendMode").title
            in {"螢幕", "屏幕", "滤色", "Screen"}
            and not any(
                node.role == "AXMenu"
                and node.size is not None
                and node.size[0] > 0
                and node.size[1] > 0
                for node in current
            )
        ),
        description="screen blend selected",
    )
    blend_title = str(_node(blended, "NSButton.LayerProperties.BlendMode").title)

    transform_before_path = output_root / "transform-before.png"
    _, transform_before_digest = _capture_stable_preview(
        driver,
        controller,
        transform_before_path,
        description="preview before horizontal flip",
    )
    driver.press_first("NSButton.LayerProperties.FlipHorizontal")
    transform_after_path = output_root / "transform-after.png"
    transform_after_digest = _wait_for_preview_hash(
        driver,
        controller,
        transform_after_path,
        lambda digest: digest != transform_before_digest,
        description="horizontal flip applied",
    )
    driver.press_first("NSButton.LayerProperties.ImageMapping.Fill")
    before_path = output_root / "before.png"
    _, opacity_digest = _capture_stable_preview(
        driver,
        controller,
        before_path,
        description="overlay at 50 percent preview",
    )

    current_overlay = next(
        node
        for node in _layer_thumbnails(driver.snapshot())
        if str(node.help or "").casefold() != SINGLE_IMAGE.name.casefold()
    )
    removed_title = _layer_context_action(
        driver,
        current_overlay,
        identifier="removeLayer:",
        expected_titles={"移除图层", "Remove Layer"},
    )
    removed = _wait_for(
        driver,
        lambda current: (
            len(_layer_thumbnails(current)) == 1
            and str(_layer_thumbnails(current)[0].help or "").casefold()
            == SINGLE_IMAGE.name.casefold()
        ),
        description="overlay layer removed",
    )
    after_path = output_root / "after.png"
    _, removed_digest = _capture_stable_preview(
        driver,
        controller,
        after_path,
        description="source-only preview after layer deletion",
    )
    if opacity_digest == removed_digest:
        raise RuntimeError("removing the 50 percent overlay did not change the preview")
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, removed)
    return {
        "visible_assertions": [
            "layer-visible-before-delete",
            "layer-hidden-and-restored",
            "layer-opacity-fifty-percent",
            "screen-blend-selected",
            "layer-removed",
        ],
        "wait_conditions": [
            "layer-visible",
            "preview-image-ready",
            "project-layer-stack-updated",
        ],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "initial_layer_count": len(initial_layers),
            "layer_count_before_delete": 2,
            "layer_count_after_delete": len(_layer_thumbnails(removed)),
            "overlay_help": overlay.help,
            "source_help": source.help,
            "overlay_was_top": True,
            "native_opacity_percent": readback,
            "hide_action_title": hidden_title,
            "show_action_title": shown_title,
            "remove_action_title": removed_title,
            "visible_preview_sha256": visible_digest,
            "hidden_preview_sha256": hidden_digest,
            "shown_preview_sha256": shown_digest,
            "layer_visibility_roundtrip": True,
            "layer_visibility_roundtrip_mae": visibility_roundtrip_mae,
            "restored_visibility_action_title": restored_visibility_title,
            "blend_mode_title": blend_title,
            "screen_blend_selected": True,
            "horizontal_flip_before_sha256": transform_before_digest,
            "horizontal_flip_after_sha256": transform_after_digest,
            "horizontal_flip_changed_preview": (
                transform_after_digest != transform_before_digest
            ),
            "image_mapping": "fill",
            "opacity_preview_sha256": opacity_digest,
            "removed_preview_sha256": removed_digest,
            "source_edits_reset": True,
            "restore_original_performed": reset_performed,
        },
    }


def _select_multi_image_inputs(
    driver: ObservationDriver,
    controller: ObservationController,
    input_root: Path,
) -> tuple[list[Path], tuple[AccessibilityNode, ...]]:
    inputs = sorted(path for path in input_root.iterdir() if path.suffix.lower() == ".jpg")
    if len(inputs) < 2:
        raise RuntimeError(f"multi-image interaction requires at least two frames: {input_root}")
    for _ in range(3):
        nodes = driver.snapshot()
        if _exposes(nodes, "目录"):
            break
        cancel_buttons = [
            node
            for node in nodes
            if node.role == "AXButton"
            and node.title == "取消"
            and node.enabled is True
            and node.position is not None
            and node.size is not None
        ]
        if len(cancel_buttons) == 1:
            driver.click_at(*_node_center(cancel_buttons[0]))
        else:
            driver.cancel()
        _wait_for(
            driver,
            lambda current: _exposes(current, "目录")
            or any(node.role in {"AXSheet", "AXWindow"} for node in current),
            description="multi-image modal cleanup",
        )
    driver.press_first("目录")
    nodes = driver.snapshot()
    if not _exposes(nodes, input_root.name):
        controller.open_add_images_folder_dialog()
        _wait_for(
            driver, lambda current: _has(current, "OKButton"), description="add folder dialog"
        )
        driver.shortcut(5, "command", "shift")
        path_nodes = _wait_for(
            driver,
            lambda current: any(
                node.identifier == "PathTextField"
                or (node.role == "AXTextField" and node.focused is True)
                for node in current
            ),
            description="go to folder field",
        )
        path_field = next(
            node
            for node in path_nodes
            if node.identifier == "PathTextField"
            or (node.role == "AXTextField" and node.focused is True)
        )
        driver.set_value_at(path_field.index, str(input_root))
        driver.confirm()
        _wait_for(
            driver, lambda current: _has(current, "OKButton"), description="HDR folder resolved"
        )
        driver.press_first("OKButton")
        _wait_for(
            driver,
            lambda current: (
                any(
                    node.role == "AXWindow"
                    and str(node.title or "") in {inputs[0].name, inputs[0].stem}
                    for node in current
                )
                or _exposes(current, input_root.name)
            ),
            description=f"{input_root.name} folder import completed",
            timeout_seconds=20.0,
        )
        driver.press_first("目录")
        nodes = _wait_for(
            driver,
            lambda current: (
                _exposes(current, input_root.name)
                or all(
                    any(
                        node.identifier == CATALOG_FILENAME_LOCATOR
                        and str(node.value or "") in {path.name, path.stem}
                        for node in current
                    )
                    for path in inputs
                )
            ),
            description=f"{input_root.name} catalog folder ready",
            timeout_seconds=20.0,
        )
    if not all(
        any(
            node.identifier == CATALOG_FILENAME_LOCATOR
            and str(node.value or "") in {path.name, path.stem}
            for node in nodes
        )
        for path in inputs
    ):
        driver.press_first(input_root.name)
    filename_nodes = _wait_for(
        driver,
        lambda current: all(
            any(
                node.identifier == CATALOG_FILENAME_LOCATOR
                and str(node.value or "") in {path.name, path.stem}
                for node in current
            )
            for path in inputs
        ),
        description=f"all {input_root.name} frame names visible",
        timeout_seconds=20.0,
    )
    if _has(filename_nodes, "MPTopBarMergeButton") and _exposes(
        filename_nodes, f"{len(inputs)} Photos"
    ):
        return inputs, filename_nodes
    if _has(filename_nodes, "MPTopBarDeselectButton"):
        driver.press_first("MPTopBarDeselectButton")
        filename_nodes = driver.snapshot()
    for ordinal, path in enumerate(inputs):
        label = next(
            node
            for node in filename_nodes
            if node.identifier == CATALOG_FILENAME_LOCATOR
            and str(node.value or "") in {path.name, path.stem}
        )
        if label.position is None:
            raise RuntimeError(f"HDR frame label has no position: {path.name}")
        thumbnails = [
            node
            for node in filename_nodes
            if node.role == "AXImage"
            and node.position is not None
            and node.size is not None
            and node.size[0] > 100
            and 0 < node.position[1] - label.position[1] <= 40
            and abs(node.position[0] - label.position[0]) <= 2
        ]
        if len(thumbnails) != 1:
            raise RuntimeError(
                f"{input_root.name} thumbnail resolved to {len(thumbnails)} nodes: {path.name}"
            )
        x, y = _node_center(thumbnails[0])
        if ordinal == 0:
            driver.click_at(x, y)
        else:
            driver.command_click_at(x, y)
    selected = _wait_for(
        driver,
        lambda current: (
            _has(current, "MPTopBarMergeButton") and _exposes(current, f"{len(inputs)} Photos")
        ),
        description=f"all {input_root.name} frames selected",
        timeout_seconds=60.0,
    )
    return inputs, selected


def _export_multi_image_result(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
    *,
    workflow_id: str,
) -> dict[str, Any]:
    workflow_root = output_root / workflow_id
    workflow_root.mkdir(parents=True, exist_ok=True)
    export_name = f"canonical-{workflow_id.replace('_', '-')}"
    native_export = output_root.parents[2] / "native-exports" / f"{export_name}.png"
    final_export = workflow_root / "export.png"
    if native_export.exists() or final_export.exists():
        raise FileExistsError(
            f"multi-image export already exists: {native_export} or {final_export}"
        )
    sheet, export_item = _open_native_export_sheet(driver)
    if _node(sheet, "where popup").value != "native-exports":
        raise RuntimeError("multi-image export sheet is not in frozen native-exports")
    settings = _configure_native_png_export(driver, export_name=export_name)
    dialog_path = workflow_root / "export-dialog.png"
    controller.screenshot_window(dialog_path)
    driver.press_first("OKButton")
    wait_for_stable_file(native_export, timeout_seconds=90.0)
    native_export.replace(final_export)
    final_nodes = _wait_for(
        driver,
        lambda current: not _has(current, "saveAsNameTextField")
        and _has(current, PREVIEW_LOCATOR),
        description=f"{workflow_id} export completed",
        timeout_seconds=30.0,
    )
    with Image.open(final_export) as exported:
        exported_format = exported.format
        exported_size = exported.size
    if exported_format != "PNG" or exported_size[0] != 1080:
        raise RuntimeError(
            f"{workflow_id} export mismatch: {exported_format} {exported_size}"
        )
    return {
        "settings": settings,
        "export_action_enabled": export_item.enabled,
        "export_dialog_screenshot": str(dialog_path.relative_to(output_root)),
        "export_file": str(final_export.relative_to(output_root)),
        "export_sha256": _sha256(final_export),
        "export_format": exported_format,
        "export_dimensions": list(exported_size),
        "final_nodes": final_nodes,
    }


def _run_multi_image_workflow(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
    spec: dict[str, Any],
) -> dict[str, Any]:
    workflow_id = str(spec["id"])
    workflow_root = output_root / workflow_id
    workflow_root.mkdir(parents=True, exist_ok=True)
    input_root = MULTI_IMAGE_ROOT / workflow_id
    expected_inputs = sorted(
        path for path in input_root.iterdir() if path.suffix.lower() == ".jpg"
    )
    expected_hashes = [_sha256(path) for path in expected_inputs]
    checkpoint_path = workflow_root / "evidence.json"
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        artifacts = checkpoint.get("artifact_sha256s")
        evidence = checkpoint.get("evidence")
        if (
            checkpoint.get("workflow_id") == workflow_id
            and checkpoint.get("input_names") == [path.name for path in expected_inputs]
            and checkpoint.get("input_sha256s") == expected_hashes
            and isinstance(artifacts, dict)
            and isinstance(evidence, dict)
            and evidence.get("source_edits_reset") is True
            and all(
                (workflow_root / relative).is_file()
                and _sha256(workflow_root / relative) == digest
                for relative, digest in artifacts.items()
            )
        ):
            return evidence
    inputs, selected = _select_multi_image_inputs(
        driver,
        controller,
        input_root,
    )
    restore_original_performed = _restore_original(driver)
    selected = _wait_for(
        driver,
        lambda current: (
            _has(current, "MPTopBarMergeButton")
            and _exposes(current, f"{len(inputs)} Photos")
        ),
        description=f"{input_root.name} source reset verified",
        timeout_seconds=20.0,
    )
    before_path = workflow_root / "before.png"
    controller.screenshot_window(before_path)
    driver.press_first("MPTopBarMergeButton")
    _wait_for(
        driver,
        lambda current: _has(current, str(spec["menu_locator"])),
        description=f"{workflow_id} merge action available",
    )
    driver.ax_press(str(spec["menu_locator"]))
    launch_panel = _wait_for(
        driver,
        lambda current: (
            not _has(current, str(spec["menu_locator"]))
            and any(
                node.identifier == "NavigationPanel.Tab.Extra"
                and node.size is not None
                and node.size[0] >= 50
                and node.size[1] >= 50
                for node in current
            )
        ),
        description=f"{workflow_id} launch panel settled",
        timeout_seconds=20.0,
    )
    panel_scroll_lines = int(spec["panel_scroll_lines"])
    if panel_scroll_lines:
        driver.scroll_at(1212, 780, panel_scroll_lines)
        launch_panel = driver.snapshot()
    launch_panel_path = workflow_root / "launch-panel.png"
    controller.screenshot_window(launch_panel_path)
    result_pattern = re.compile(str(spec["result_pattern"]), re.IGNORECASE)
    driver.click_at(*spec["launch_position"])
    launched_nodes = _wait_for(
        driver,
        lambda current: (
            _exposes(current, str(spec["plugin_locator"]))
            or any(
                node.role == "AXWindow"
                and result_pattern.search(str(node.title or ""))
                for node in current
            )
        ),
        description=f"{workflow_id} plugin or result ready",
        timeout_seconds=60.0,
    )
    result_ready = any(
        node.role == "AXWindow" and result_pattern.search(str(node.title or ""))
        for node in launched_nodes
    )
    plugin_path: Path | None = None
    if not result_ready:
        plugin_path = workflow_root / "plugin.png"
        controller.screenshot_window(plugin_path)
        driver.ax_press("继续")
        if spec["post_continue_locators"]:
            _wait_for(
                driver,
                lambda current: (
                    not _has(current, "继续")
                    or any(
                        node.role == "AXWindow"
                        and result_pattern.search(str(node.title or ""))
                        for node in current
                    )
                ),
                description=f"{workflow_id} initial processing started",
                timeout_seconds=30.0,
            )
    for locator in spec["post_continue_locators"] if not result_ready else ():
        stage = _wait_for(
            driver,
            lambda current, expected=locator: (
                any(
                    node.role == "AXWindow"
                    and result_pattern.search(str(node.title or ""))
                    for node in current
                )
                or any(
                    expected
                    in {
                        node.identifier,
                        node.title,
                        node.description,
                        node.value,
                        node.help,
                    }
                    and node.enabled is True
                    and node.position is not None
                    and node.size is not None
                    for node in current
                )
            ),
            description=f"{workflow_id} post-process stage {locator}",
            timeout_seconds=420.0,
        )
        if any(
            node.role == "AXWindow" and result_pattern.search(str(node.title or ""))
            for node in stage
        ):
            result_ready = True
            break
        buttons = [
            node
            for node in stage
            if locator
            in {node.identifier, node.title, node.description, node.value, node.help}
            and node.enabled is True
            and node.position is not None
            and node.size is not None
        ]
        if len(buttons) != 1:
            raise RuntimeError(
                f"{workflow_id} stage {locator} resolved to {len(buttons)} enabled buttons"
            )
        driver.click_at(*_node_center(buttons[0]))
    if result_ready:
        result_nodes = driver.snapshot()
    else:
        result_nodes = _wait_for(
            driver,
            lambda current: any(
                node.role == "AXWindow"
                and result_pattern.search(str(node.title or ""))
                for node in current
            ),
            description=f"{workflow_id} result ready",
            timeout_seconds=240.0,
        )
    result_title = next(
        str(node.title)
        for node in result_nodes
        if node.role == "AXWindow" and result_pattern.search(str(node.title or ""))
    )
    if not _has(result_nodes, PREVIEW_LOCATOR) and _exposes(result_nodes, "单图视图"):
        driver.press_first("单图视图")
        result_nodes = _wait_for(
            driver,
            lambda current: _has(current, PREVIEW_LOCATOR)
            and any(
                node.role == "AXWindow"
                and result_pattern.search(str(node.title or ""))
                for node in current
            ),
            description=f"{workflow_id} single-image preview ready",
            timeout_seconds=30.0,
        )
    if not _has(result_nodes, PREVIEW_LOCATOR):
        raise RuntimeError(f"{workflow_id} result has no single-image preview")
    preview_path = workflow_root / "preview.png"
    controller.screenshot_window(preview_path)
    preview_hash = _preview_region_hash(preview_path, result_nodes)
    export = _export_multi_image_result(
        driver,
        controller,
        output_root,
        workflow_id=workflow_id,
    )
    export.pop("final_nodes")
    evidence = {
        "input_names": [path.name for path in inputs],
        "input_sha256s": expected_hashes,
        "selected_photo_count_visible": _exposes(selected, f"{len(inputs)} Photos"),
        "result_title": result_title,
        "launch_panel_screenshot": str(launch_panel_path.relative_to(output_root)),
        "plugin_screenshot": (
            str(plugin_path.relative_to(output_root)) if plugin_path is not None else None
        ),
        "preview_screenshot": str(preview_path.relative_to(output_root)),
        "preview_region_sha256": preview_hash,
        "plugin_locator_visible": _exposes(
            launched_nodes, str(spec["plugin_locator"])
        ),
        "direct_cached_result": plugin_path is None,
        "launch_panel_active": any(
            node.identifier == "NavigationPanel.Tab.Extra"
            and node.size is not None
            and node.size[0] >= 50
            for node in launch_panel
        ),
        "source_edits_reset": True,
        "restore_original_performed": restore_original_performed,
        **export,
    }
    artifacts = {
        str(path.relative_to(workflow_root)): _sha256(path)
        for path in workflow_root.rglob("*")
        if path.is_file() and path != checkpoint_path
    }
    checkpoint_path.write_text(
        json.dumps(
            {
                "workflow_id": workflow_id,
                "input_names": [path.name for path in inputs],
                "input_sha256s": expected_hashes,
                "artifact_sha256s": artifacts,
                "evidence": evidence,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return evidence


def _observe_multi_image_workflow(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    inputs, selected = _select_multi_image_inputs(driver, controller, HDR_INPUT_ROOT)
    before_path = output_root / "before.png"
    controller.screenshot_window(before_path)
    driver.press_first("MPTopBarMergeButton")
    _wait_for(
        driver,
        lambda current: _has(current, "MPTopBarMergeMenuItem.HDRMerge"),
        description="HDR merge action available",
    )
    driver.ax_press("MPTopBarMergeMenuItem.HDRMerge")
    time.sleep(1.0)
    driver.click_at(1212, 838)
    _wait_for(
        driver,
        lambda current: (
            _exposes(current, "HDR 合并") and not _has(current, "MPTopBarMergeMenuItem.HDRMerge")
        ),
        description="HDR merge plugin ready",
        timeout_seconds=30.0,
    )
    driver.ax_press("继续")
    result_pattern = re.compile(r"_HDR(?: \d+)?\.tiff$", re.IGNORECASE)
    result_nodes = _wait_for(
        driver,
        lambda current: any(
            node.role == "AXWindow" and result_pattern.search(str(node.title or ""))
            for node in current
        ),
        description="HDR workflow preview ready",
        timeout_seconds=180.0,
    )
    result_title = next(
        str(node.title)
        for node in result_nodes
        if node.role == "AXWindow" and result_pattern.search(str(node.title or ""))
    )
    menu = driver.open_export_menu()
    export_items = [
        node for node in menu if node.identifier == "NSMenuItem.NewExport" and node.enabled is True
    ]
    if len(export_items) != 1:
        raise RuntimeError("native HDR result does not expose one enabled export action")
    driver.ax_press_at(export_items[0].index)
    _wait_for(
        driver,
        lambda current: _has(current, "saveAsNameTextField"),
        description="HDR export dialog ready",
    )
    export_dialog_path = output_root / "export-dialog.png"
    controller.screenshot_window(export_dialog_path)
    driver.cancel()
    final_nodes = _wait_for(
        driver,
        lambda current: any(
            node.role == "AXWindow" and node.title == result_title for node in current
        ),
        description="HDR result restored after export dialog",
    )
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "all-frame-names-visible",
            "workflow-preview-ready",
            "export-enabled-only-after-preview",
        ],
        "wait_conditions": ["workflow-preview-ready", "export-response-complete"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "input_names": [path.name for path in inputs],
            "input_count": len(inputs),
            "selected_photo_count_visible": _exposes(selected, f"{len(inputs)} Photos"),
            "result_title": result_title,
            "workflow_preview_ready": True,
            "export_action_enabled": True,
            "export_dialog_screenshot": export_dialog_path.name,
            "duplicate_export_created": False,
        },
    }


def _observe_multi_image_three_workflows(
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
) -> dict[str, Any]:
    driver.activate()
    before_path = output_root / "before.png"
    controller.screenshot_window(before_path)
    workflows = [
        _run_multi_image_workflow(driver, controller, output_root, spec)
        for spec in MULTI_IMAGE_WORKFLOWS
    ]
    final_nodes = driver.snapshot()
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "hdr-preview-and-export-complete",
            "focus-preview-and-export-complete",
            "panorama-preview-and-export-complete",
            "all-frame-names-and-order-visible",
        ],
        "wait_conditions": [
            "hdr-preview-ready",
            "focus-preview-ready",
            "panorama-preview-ready",
            "export-response-complete",
        ],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "workflows": {
                str(spec["id"]): evidence
                for spec, evidence in zip(MULTI_IMAGE_WORKFLOWS, workflows, strict=True)
            },
            "workflow_count": len(workflows),
            "duplicate_exports_created": False,
            "source_edits_reset": all(
                evidence.get("source_edits_reset") is True for evidence in workflows
            ),
        },
    }


HANDLERS = {
    "workflow:catalog-photo-context-submenu": _observe_catalog_photo_context,
    "workflow:catalog-folder-context-scroll": _observe_catalog_folder_scroll,
    "workflow:edit-tool-expand-crop": _observe_edit_tool_crop,
    "workflow:photo-switch-history": _observe_photo_switch_history,
    "workflow:preset-import-preview-apply": _observe_preset_apply,
    "workflow:layer-lifecycle": _observe_layer_lifecycle,
    "workflow:mask-lifecycle": _observe_mask_lifecycle,
    "workflow:compare-zoom-pan": _observe_compare_zoom_pan,
    "workflow:multi-image-three-workflows": _observe_multi_image_three_workflows,
    "workflow:export-dialog-file": _observe_export_dialog_file,
}


def _parameter_bindings(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise TypeError("native parameter binding audit has no records")
    return {
        str(item["matrix_state_id"]): item
        for item in records
        if isinstance(item, dict) and item.get("matrix_state_id")
    }


def _parameter_state_id(contract: dict[str, Any]) -> str | None:
    if contract.get("kind") != "tool-parameter-contract":
        return None
    capability_id = contract.get("capability_id")
    parameter = contract.get("parameter")
    if not isinstance(capability_id, str) or not isinstance(parameter, str):
        return None
    return f"tool:{capability_id}:parameter:{parameter}:modified"


def _contract_supported(
    contract: dict[str, Any], bindings: dict[str, dict[str, Any]]
) -> bool:
    contract_id = str(contract.get("id") or "")
    if contract_id in HANDLERS:
        return True
    state_id = _parameter_state_id(contract)
    binding = bindings.get(state_id or "")
    return bool(binding and binding.get("status") == "supported" and binding.get("native"))


def _observe_tool_parameter(
    contract: dict[str, Any],
    handlers: LuminarQueueHandlers,
    driver: ObservationDriver,
    controller: ObservationController,
    output_root: Path,
    *,
    ui_matrix_fingerprint: str,
) -> dict[str, Any]:
    """Execute one audited parameter transition with visual undo/redo evidence."""

    state_id = _parameter_state_id(contract)
    if state_id is None:
        raise RuntimeError(f"invalid parameter interaction contract: {contract.get('id')}")
    input_sha256 = _sha256(SINGLE_IMAGE)
    input_record: dict[str, object] = {
        "path": str(SINGLE_IMAGE.resolve()),
        "sha256": input_sha256,
    }
    handlers.prepare_observation_photo(input_record)
    reset_performed = _restore_original(driver)
    before_path = output_root / "before.png"
    _before_nodes, before_digest = _capture_stable_preview(
        driver,
        controller,
        before_path,
        description=f"{state_id} baseline",
    )
    operation_layout = CaptureLayout(output_root / "operation", "parameter")
    operation_layout.prepare()
    record = SamplingQueueRecord.from_payload(
        {
            "id": f"ui:{state_id}",
            "scan_order": 1,
            "kind": "ui",
            "page": "edit",
            "section": "tools",
            "viewport": [2880, 1800],
            "ui_state": state_id,
            "matrix_state_id": state_id,
            "matrix_fingerprint": ui_matrix_fingerprint,
            "matrix_kind": "tool-parameter-state",
            "workspace_state": "edit",
            "capability_id": contract["capability_id"],
            "parameter": contract["parameter"],
            "input": input_record,
        }
    )
    after_nodes, parameter_evidence = handlers.apply_parameter_observation(
        record, operation_layout
    )
    after_path = output_root / "after.png"
    controller.screenshot_window(after_path)
    after_digest = _preview_region_hash(after_path, after_nodes)
    if parameter_evidence.get("kind") != "semantic-readback" and after_digest == before_digest:
        raise RuntimeError(f"native parameter did not change the preview: {state_id}")

    undo_verified = False
    redo_verified = False
    undo_digest = None
    redo_digest = None
    if parameter_evidence.get("kind") != "semantic-readback":
        driver.target_shortcut(6, "command")
        undo_path = output_root / "undo.png"
        undo_digest = _wait_for_preview_hash(
            driver,
            controller,
            undo_path,
            lambda digest: digest != after_digest,
            description=f"{state_id} undo",
            timeout_seconds=20.0,
        )
        undo_verified = True
        driver.target_shortcut(6, "command", "shift")
        redo_path = output_root / "redo.png"
        redo_digest = _wait_for_preview_hash(
            driver,
            controller,
            redo_path,
            lambda digest: digest != undo_digest,
            description=f"{state_id} redo",
            timeout_seconds=20.0,
        )
        redo_verified = redo_digest == after_digest
        if not redo_verified:
            raise RuntimeError(f"native parameter redo did not restore the preview: {state_id}")

    export_name = f"interaction-{contract['capability_id']}-{contract['parameter']}"
    native_export_path = output_root.parents[2] / "native-exports" / f"{export_name}.png"
    export_path = output_root / "export.png"
    if native_export_path.exists() or export_path.exists():
        raise FileExistsError(
            f"parameter interaction export already exists: {native_export_path} or {export_path}"
        )
    export_sheet, export_item = _open_native_export_sheet(driver)
    if _node(export_sheet, "where popup").value != "native-exports":
        raise RuntimeError("parameter export sheet is not in frozen native-exports")
    export_settings = _configure_native_png_export(driver, export_name=export_name)
    driver.press_first("OKButton")
    wait_for_stable_file(native_export_path, timeout_seconds=60.0)
    native_export_path.replace(export_path)
    _wait_for(
        driver,
        lambda current: not _has(current, "saveAsNameTextField")
        and _has(current, PREVIEW_LOCATOR),
        description=f"{state_id} export completed",
        timeout_seconds=20.0,
    )
    with Image.open(export_path) as exported:
        export_format = exported.format
        export_dimensions = list(exported.size)
    if export_format != "PNG" or export_dimensions[0] != 1080:
        raise RuntimeError(
            f"parameter export mismatch: {state_id}: {export_format} {export_dimensions}"
        )

    driver.cancel()
    source_edits_reset = _restore_original(driver)
    if parameter_evidence.get("kind") != "semantic-readback" and not source_edits_reset:
        raise RuntimeError(f"native parameter edit was not restorable: {state_id}")
    final_nodes = driver.snapshot()
    accessibility_path = output_root / "accessibility.json"
    driver.write_snapshot(accessibility_path, final_nodes)
    return {
        "visible_assertions": [
            "tool-expanded",
            "parameter-value-changed",
            "preview-updated",
            "undo-restored-preview",
            "redo-restored-preview",
            "reset-restored-default",
            "export-completed",
        ],
        "wait_conditions": ["preview-ready", "export-ready"],
        "before_screenshot": before_path.name,
        "after_screenshot": after_path.name,
        "accessibility_snapshot": accessibility_path.name,
        "assertion_evidence": {
            "matrix_state_id": state_id,
            "parameter_evidence": parameter_evidence,
            "before_preview_sha256": before_digest,
            "after_preview_sha256": after_digest,
            "undo_preview_sha256": undo_digest,
            "redo_preview_sha256": redo_digest,
            "undo_verified": undo_verified,
            "redo_verified": redo_verified,
            "source_edits_reset": source_edits_reset,
            "restore_original_performed_before_capture": reset_performed,
            "export_verified": True,
            "export_action_enabled": export_item.enabled,
            "export_settings": export_settings,
            "export_file": export_path.name,
            "export_sha256": _sha256(export_path),
            "export_format": export_format,
            "export_dimensions": export_dimensions,
        },
    }


def _observation_valid(
    path: Path,
    *,
    app_version: dict[str, str],
    contract_id: str,
    matrix_fingerprint: str,
) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if (
        payload.get("app_version") != app_version
        or payload.get("contract_id") != contract_id
        or payload.get("matrix_fingerprint") != matrix_fingerprint
    ):
        return False
    root = path.parent
    for field in ("before_screenshot", "after_screenshot", "accessibility_snapshot"):
        artifact = root / str(payload.get(field, ""))
        if not artifact.is_file() or payload.get(f"{field}_sha256") != _sha256(artifact):
            return False
    return True


def _selected_contracts(contracts: dict[str, Any], contract_id: str | None) -> list[dict[str, Any]]:
    records = [item for item in contracts.get("records", []) if isinstance(item, dict)]
    if contract_id is None:
        return records
    selected = [item for item in records if item.get("id") == contract_id]
    if not selected:
        raise ValueError(f"unknown interaction contract: {contract_id}")
    return selected


def _write_blocked_observation(
    path: Path,
    *,
    contract_id: str,
    reference_id: str,
    app_version: dict[str, str],
    matrix_fingerprint: str,
    capture_environment: dict[str, Any],
    error: RuntimeError | TimeoutError,
) -> None:
    root = path.parent
    artifacts = {
        str(artifact.relative_to(root)): _sha256(artifact)
        for artifact in root.rglob("*")
        if artifact.is_file() and artifact != path and not artifact.name.endswith(".tmp")
    }
    payload = {
        "version": "1.0",
        "gate": "blocked",
        "contract_id": contract_id,
        "reference_id": reference_id,
        "app_version": app_version,
        "matrix_fingerprint": matrix_fingerprint,
        "capture_environment": capture_environment,
        "error_type": type(error).__name__,
        "error": str(error),
        "artifact_sha256s": artifacts,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--contracts",
        type=Path,
        default=ROOT / "configs/parity/core-interaction-matrix.json",
    )
    parser.add_argument(
        "--sampling-config",
        type=Path,
        default=ROOT / "configs/luminar_sampling.yaml",
    )
    parser.add_argument(
        "--bindings",
        type=Path,
        default=ROOT / "configs/parity/native-parameter-bindings.json",
    )
    parser.add_argument(
        "--ui-matrix",
        type=Path,
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
    )
    parser.add_argument("--contract-id")
    parser.add_argument("--app", type=Path, default=Path("/Applications/Luminar Neo.app"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-ui-control", action="store_true")
    args = parser.parse_args()

    profile = load_reference_catalog(args.reference_config.resolve(), project_root=ROOT).resolve(
        args.reference_id
    )
    contracts = json.loads(args.contracts.read_text(encoding="utf-8"))
    if contracts.get("reference_id") != profile.id:
        raise RuntimeError("interaction contract reference id does not match active profile")
    matrix_fingerprint = str(contracts.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        raise RuntimeError("interaction matrix fingerprint must be a SHA-256 digest")
    selected = _selected_contracts(contracts, args.contract_id)
    bindings = _parameter_bindings(args.bindings.resolve())
    unsupported = [
        str(item.get("id"))
        for item in selected
        if not _contract_supported(item, bindings)
    ]
    plan = {
        "reference_id": profile.id,
        "selected": [item.get("id") for item in selected],
        "supported": [
            item.get("id") for item in selected if _contract_supported(item, bindings)
        ],
        "unsupported": unsupported,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0 if not unsupported else 2
    if unsupported:
        raise RuntimeError(f"native observation handlers are not implemented: {unsupported}")
    if not args.allow_ui_control:
        raise RuntimeError("native observation requires --allow-ui-control")

    sampling = load_luminar_sampling_config(args.sampling_config.resolve())
    if sampling.reference_id != profile.id:
        raise RuntimeError("sampling config reference id does not match active profile")
    controller = LuminarAppController(args.app)
    app_version = controller.version()
    profile.validate_app_version(app_version)
    driver = LuminarAccessibilityDriver()
    controller.enter_full_screen(
        timeout_seconds=sampling.timeouts.navigation_seconds
    )
    preflight = run_preflight(
        controller,
        driver,
        output_dir=profile.diagnostics_root / "preflight-interactions",
        timeout_seconds=sampling.timeouts.action_seconds,
        requirements=NativeCaptureRequirements(
            reference_id=profile.id,
            app_version=profile.version,
            app_build=profile.build,
            bundle_id=profile.bundle_id,
            locale=profile.locale,
            logical_viewport=sampling.logical_viewport,
            physical_viewport=sampling.viewports[0],
            environment_evidence_path=sampling.environment_evidence_path,
        ),
    )
    full_screen_bounds = controller.window_bounds()
    output_root = profile.observations_root / "interactions"
    ui_matrix = json.loads(args.ui_matrix.read_text(encoding="utf-8"))
    ui_matrix_fingerprint = str(ui_matrix.get("matrix_fingerprint") or "")
    if len(ui_matrix_fingerprint) != 64:
        raise RuntimeError("UI matrix fingerprint must be a SHA-256 digest")
    queue_handlers = LuminarQueueHandlers(
        sampling,
        controller,
        driver,
        reference_id=profile.id,
        app_version=app_version,
        ui_reference_root=profile.ui_reference_root,
    )
    completed: list[str] = []
    skipped: list[str] = []
    failures: list[dict[str, str]] = []
    capture_environment = {
        "native_full_screen": True,
        "window_bounds": {
            "x": full_screen_bounds.x,
            "y": full_screen_bounds.y,
            "width": full_screen_bounds.width,
            "height": full_screen_bounds.height,
        },
        "input_device_mode": "verified-isolated-input",
        "capture_mode": preflight["capture_mode"],
        "capture_provider": preflight["capture_provider"],
        "capture_session_id": preflight["capture_session_id"],
        "capture_verified_at": preflight["capture_verified_at"],
        "display_session_verified": preflight["display_session_verified"],
        "automation_input_verified": preflight["automation_input_verified"],
        "user_authorized_local_capture": preflight["user_authorized_local_capture"],
        "logical_viewport": preflight["logical_viewport"],
        "physical_viewport": preflight["physical_viewport"],
        "environment_evidence": preflight["environment_evidence"],
    }
    for contract in selected:
        contract_id = str(contract["id"])
        contract_root = output_root / contract_id
        observation_path = contract_root / "observation.json"
        if args.resume and _observation_valid(
            observation_path,
            app_version=app_version,
            contract_id=contract_id,
            matrix_fingerprint=matrix_fingerprint,
        ):
            skipped.append(contract_id)
            continue
        contract_root.mkdir(parents=True, exist_ok=True)
        try:
            if contract_id in HANDLERS:
                evidence = HANDLERS[contract_id](driver, controller, contract_root)
            else:
                evidence = _observe_tool_parameter(
                    contract,
                    queue_handlers,
                    driver,
                    controller,
                    contract_root,
                    ui_matrix_fingerprint=ui_matrix_fingerprint,
                )
        except (FileExistsError, RuntimeError, TimeoutError) as exc:
            blocked_path = contract_root / "blocked-observation.json"
            _write_blocked_observation(
                blocked_path,
                contract_id=contract_id,
                reference_id=profile.id,
                app_version=app_version,
                matrix_fingerprint=matrix_fingerprint,
                capture_environment=capture_environment,
                error=exc,
            )
            failures.append(
                {
                    "contract_id": contract_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "evidence": str(blocked_path),
                }
            )
            continue
        payload = {
            "contract_id": contract_id,
            "reference_id": profile.id,
            "app_version": app_version,
            "matrix_fingerprint": matrix_fingerprint,
            "fixture_hash": _sha256(SINGLE_IMAGE),
            "events": contract.get("events", []),
            "visible_assertions": evidence.pop("visible_assertions"),
            "wait_conditions": evidence.pop("wait_conditions"),
            "final_state": contract.get("final_screenshot_state"),
            "capture_environment": capture_environment,
            **evidence,
        }
        for field in ("before_screenshot", "after_screenshot", "accessibility_snapshot"):
            payload[f"{field}_sha256"] = _sha256(contract_root / payload[field])
        temporary = observation_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(observation_path)
        completed.append(contract_id)
    print(
        json.dumps(
            plan | {"completed": completed, "skipped": skipped, "failures": failures},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
