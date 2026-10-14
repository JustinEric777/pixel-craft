"""Resumable semantic tool-panel sampling for the installed Luminar app."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageOps, ImageStat

from configs.luminar_sampling import LuminarSamplingConfig, SamplingRecipe

from .accessibility_driver import AccessibilityNode, LuminarAccessibilityDriver
from .app_controller import LuminarAppController, WindowBounds
from .capture_runner import finalize_case
from .case_reader import CaptureCase
from .export_watcher import snapshot_export_files, wait_for_new_stable_export
from .layout import CaptureLayout
from .stability import (
    normalized_image_change_metrics,
    normalized_image_mae,
    stable_screenshot_sequence,
)
from .state_machine import CaptureJournal, CaptureStatus

PARAMETER_ROLES = {
    "AXSlider",
    "AXCheckBox",
    "AXPopUpButton",
    "AXTextField",
    "AXRadioButton",
}
VALUE_STRATEGIES = {"primary_slider", "subject_aware", "positioned_effect"}
WORKSPACE_LOCATORS = {
    "catalog": "目录",
    "presets": "NavigationPanel.Tab.Presets",
    "edit": "NavigationPanel.Tab.Tools",
}
REPLACEMENT_LOCATORS = ("替换", "Replace")
RESET_ALL_EDITS_LOCATOR = "ResetAllEdits"


class NonRetryableCaptureError(RuntimeError):
    """A complete native attempt produced invalid evidence deterministically."""


class AdvanceActivationCaptureError(RuntimeError):
    """The current explicit activation is stable but ineffective."""


def _export_slug(value: object, *, limit: int) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").lower()
    return (normalized or "default")[:limit].rstrip("-")


def build_native_export_stem(case: CaptureCase, attempt_id: str) -> str:
    """Return a readable, collision-resistant filename for one native export."""

    parameter_tokens = [
        f"{_export_slug(key, limit=18)}-{_export_slug(value, limit=24)}"
        for key, value in sorted(case.parameters.items())
    ]
    parameters = "__".join(parameter_tokens[:3]) or "default"
    identity_payload = {
        "case_id": case.case_id,
        "capability_id": case.capability_id,
        "input_sha256": case.input_sha256,
        "parameters": case.parameters,
        "asset_id": case.asset_id,
        "asset_sha256": case.asset_sha256,
    }
    identity = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:10]
    attempt = _export_slug(attempt_id.split("+")[0], limit=22)
    return "__".join(
        (
            "luminar-neo",
            _export_slug(case.capability_id, limit=32),
            _export_slug(case.input_path.stem, limit=36),
            parameters[:72].rstrip("-"),
            identity,
            attempt,
        )
    )


@dataclass(frozen=True)
class ToolProbeResult:
    case_id: str
    capability_id: str
    locator_id: str
    status: str
    capture_level: str
    discovered_controls: tuple[dict[str, Any], ...]
    effective_control: str | None = None
    effective_value: Any = None
    stable_samples: int = 0
    export_path: str | None = None
    error: str | None = None


def _serializable_control(node: AccessibilityNode) -> dict[str, Any]:
    return {
        "role": node.role,
        "identifier": node.identifier,
        "title": node.title,
        "value": node.value,
        "min_value": node.min_value,
        "max_value": node.max_value,
        "enabled": node.enabled,
        "position": node.position,
        "size": node.size,
    }


def select_replacement_locator(
    nodes: tuple[AccessibilityNode, ...],
) -> str | None:
    """Return the exact localized locator for an enabled overwrite button."""

    for locator in REPLACEMENT_LOCATORS:
        for node in nodes:
            if node.enabled is False or node.role != "AXButton":
                continue
            if locator in {
                node.identifier,
                node.title,
                node.description,
                node.help,
                node.value,
            }:
                return locator
    return None


def export_signature_changed(
    directory: Path,
    *,
    stem: str,
    before: dict[Path, tuple[int, int]],
) -> bool:
    current = snapshot_export_files(directory)
    return any(
        path.stem == stem and signature != before.get(path)
        for path, signature in current.items()
    )


def render_change_required(capture_level: str, recipe: SamplingRecipe) -> bool:
    """Decide whether native evidence must visibly differ from the source.

    Exact matrices include a neutral amount anchor. A real native slider set
    to zero is valid evidence even though the render stays unchanged. Every
    non-zero or non-amount effect remains fail-closed when no change appears.
    """

    if capture_level != "effect":
        return False
    explicit = recipe.effective.get("export_source_change_required")
    if explicit is False:
        return False
    if explicit is True:
        return True
    binding = recipe.effective.get("parameter_binding")
    return not (
        isinstance(binding, dict)
        and binding.get("parameter") == "amount"
        and isinstance(binding.get("value"), (int, float))
        and math.isclose(float(binding["value"]), 0.0, abs_tol=1e-9)
    )


def normalized_preview_stroke(
    preview: AccessibilityNode, raw_stroke: Any
) -> tuple[int, int, int, int]:
    """Map one normalized recipe stroke into the current preview canvas."""

    if (
        not isinstance(raw_stroke, list)
        or len(raw_stroke) != 4
        or not all(isinstance(value, (int, float)) for value in raw_stroke)
        or not all(0 <= float(value) <= 1 for value in raw_stroke)
    ):
        raise ValueError("stroke coordinates must be four normalized numbers")
    if preview.position is None or preview.size is None:
        raise ValueError("preview canvas has no geometry")
    x, y = preview.position
    width, height = preview.size
    return (
        round(x + width * float(raw_stroke[0])),
        round(y + height * float(raw_stroke[1])),
        round(x + width * float(raw_stroke[2])),
        round(y + height * float(raw_stroke[3])),
    )


def rendered_source_matches(
    source: Path,
    preview: Path,
    *,
    size: int,
    rgb_mae_max: float,
    luma_mae_max: float,
) -> tuple[bool, dict[str, float]]:
    """Verify that a native preview represents the requested capture input."""

    metrics = {
        "rgb_mae": normalized_image_mae(source, preview, size=size),
        "luma_mae": normalized_image_mae(source, preview, size=size, mode="L"),
    }
    return (
        metrics["rgb_mae"] <= rgb_mae_max
        and metrics["luma_mae"] <= luma_mae_max,
        metrics,
    )


def discover_new_controls(
    before: tuple[AccessibilityNode, ...], after: tuple[AccessibilityNode, ...]
) -> tuple[AccessibilityNode, ...]:
    before_keys = {node.stable_key for node in before}
    return tuple(
        node
        for node in after
        if (
            node.role in PARAMETER_ROLES
            or (
                node.role == "AXButton"
                and bool(node.identifier)
                and (
                    node.identifier.startswith("AdvancedSlider.")
                    or node.identifier.startswith("NSButton.TextureButton")
                )
            )
        )
        and node.stable_key not in before_keys
        and node.enabled is not False
    )


def select_primary_slider(nodes: tuple[AccessibilityNode, ...]) -> AccessibilityNode | None:
    sliders = [node for node in nodes if node.role == "AXSlider" and node.enabled is not False]
    return min(
        sliders,
        key=lambda node: (
            node.enabled is not True,
            (node.position or (10**9, 10**9))[1],
        ),
        default=None,
    )


def select_recipe_slider(
    nodes: tuple[AccessibilityNode, ...], locator_id: str
) -> AccessibilityNode:
    """Resolve an explicitly configured slider without a fuzzy fallback."""

    matches = [
        node
        for node in nodes
        if node.role == "AXSlider" and node.identifier == locator_id
    ]
    writable = [node for node in matches if node.enabled is True]
    if len(writable) == 1:
        return writable[0]
    if len(matches) == 1:
        return matches[0]
    raise RuntimeError(
        f"configured slider {locator_id!r} resolved to {len(matches)} controls "
        f"({len(writable)} writable)"
    )


def select_unique_control(
    nodes: tuple[AccessibilityNode, ...], locator_id: str
) -> AccessibilityNode:
    """Resolve one exact AX control for post-commit readback."""

    matches = [node for node in nodes if node.identifier == locator_id]
    if len(matches) != 1:
        raise RuntimeError(
            f"configured control {locator_id!r} resolved to {len(matches)} controls"
        )
    return matches[0]


def control_readback_matches(node: AccessibilityNode, expected: Any) -> bool:
    """Return whether a native control exposes the committed semantic value."""

    if isinstance(expected, (int, float)):
        try:
            return abs(float(node.value) - float(expected)) <= 1e-6
        except (TypeError, ValueError):
            return False
    normalized = str(expected).strip().casefold()
    if not normalized:
        return False
    return any(
        normalized == str(value).strip().casefold()
        for value in (
            node.value,
            node.title,
            node.description,
            node.help,
        )
        if value is not None
    )


def normalize_recipe_value(
    node: AccessibilityNode,
    requested: float,
    *,
    value_space: str | None = None,
) -> float:
    minimum = node.min_value if node.min_value is not None else 0.0
    maximum = node.max_value if node.max_value is not None else 100.0
    if maximum <= minimum:
        raise ValueError(f"invalid slider range for {node.identifier}: {minimum}..{maximum}")
    if value_space == "normalized-signed":
        if not -1.0 <= requested <= 1.0:
            raise ValueError(f"normalized signed value is outside [-1, 1]: {requested}")
        if requested < 0:
            if minimum >= 0:
                raise ValueError(
                    f"negative product amount cannot be represented by slider "
                    f"{node.identifier}: {minimum}..{maximum}"
                )
            return abs(requested) * minimum
        return requested * maximum
    if value_space is not None:
        raise ValueError(f"unsupported recipe value space: {value_space}")
    if minimum <= requested <= maximum:
        return requested
    if 0.0 <= requested <= 100.0:
        return minimum + (maximum - minimum) * requested / 100.0
    raise ValueError(
        f"recipe value {requested} is outside slider range {minimum}..{maximum}"
    )


def slider_click_position(
    node: AccessibilityNode, value: float
) -> tuple[int, int]:
    """Map a native slider value onto the visible track of an AX wrapper."""

    if node.position is None or node.size is None:
        raise ValueError(f"slider {node.identifier} has no visible bounds")
    minimum = node.min_value if node.min_value is not None else 0.0
    maximum = node.max_value if node.max_value is not None else 100.0
    if maximum <= minimum:
        raise ValueError(f"invalid slider range for {node.identifier}: {minimum}..{maximum}")
    ratio = max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    x, y = node.position
    width, height = node.size
    track_left = x + 1
    track_right = x + max(1, width - 3)
    track_y = y + max(1, round(height * 0.72))
    return round(track_left + (track_right - track_left) * ratio), track_y


def _asset_terms(asset_id: str) -> set[str]:
    path = Path(asset_id)
    values = {asset_id, path.name, path.stem}
    if path.parent.name:
        values.add(f"{path.parent.name}/{path.name}")
    return {
        re.sub(r"[^0-9a-z]+", "", value.casefold())
        for value in values
        if value
    }


def select_asset_thumbnail(
    nodes: tuple[AccessibilityNode, ...],
    *,
    asset_id: str | None,
) -> AccessibilityNode:
    """Resolve an asset semantically; never substitute a different requested asset."""

    if not nodes:
        raise RuntimeError("asset picker exposed no thumbnail")
    if not asset_id:
        return min(nodes, key=lambda node: (node.position or (10**9, 10**9))[::-1])
    terms = _asset_terms(asset_id)
    matches = []
    for node in nodes:
        searchable = " ".join(
            str(value)
            for value in (
                node.identifier,
                node.title,
                node.description,
                node.help,
                node.value,
            )
            if value is not None and value != ""
        )
        normalized = re.sub(r"[^0-9a-z]+", "", searchable.casefold())
        if normalized and any(term and term in normalized for term in terms):
            matches.append(node)
    if not matches:
        raise RuntimeError(f"requested asset is not exposed by the picker: {asset_id}")
    if len(matches) > 1:
        identifiers = [node.identifier or node.title or str(node.index) for node in matches]
        raise RuntimeError(
            f"requested asset locator is ambiguous: {asset_id}: {identifiers}"
        )
    return matches[0]


def select_preview_node(
    nodes: tuple[AccessibilityNode, ...], bounds: WindowBounds
) -> AccessibilityNode:
    """Select the largest native image inside the main Luminar window."""

    candidates = []
    minimum_area = bounds.width * bounds.height * 0.08
    for node in nodes:
        if node.role != "AXImage" or node.position is None or node.size is None:
            continue
        x, y = node.position
        width, height = node.size
        if width <= 0 or height <= 0 or width * height < minimum_area:
            continue
        if (
            x < bounds.x
            or y < bounds.y
            or x + width > bounds.x + bounds.width
            or y + height > bounds.y + bounds.height
        ):
            continue
        candidates.append(node)
    if not candidates:
        raise RuntimeError(
            "Luminar did not expose the main preview as a native AXImage; "
            "refusing to reuse the exported file as preview evidence"
        )
    return max(candidates, key=lambda node: node.size[0] * node.size[1])  # type: ignore[index]


def visible_export_item_center(
    nodes: tuple[AccessibilityNode, ...], bounds: WindowBounds
) -> tuple[int, int]:
    items = [
        node
        for node in nodes
        if node.identifier == "NSMenuItem.NewExport"
        and node.position is not None
        and node.size is not None
        and node.size[0] > 0
        and node.size[1] > 0
        and bounds.x <= node.position[0] < bounds.x + bounds.width
        and bounds.y <= node.position[1] < bounds.y + bounds.height
    ]
    if len(items) != 1:
        raise RuntimeError(
            f"Luminar exposed {len(items)} visible New Export menu items"
        )
    item = items[0]
    return (
        item.position[0] + item.size[0] // 2,
        item.position[1] + item.size[1] // 2,
    )


def crop_native_preview(
    screenshot: Path,
    destination: Path,
    *,
    node: AccessibilityNode,
    bounds: WindowBounds,
) -> None:
    if node.position is None or node.size is None:
        raise ValueError("preview node has no accessibility bounds")
    with Image.open(screenshot) as image:
        scale_x = image.width / bounds.width
        scale_y = image.height / bounds.height
        left = round((node.position[0] - bounds.x) * scale_x)
        top = round((node.position[1] - bounds.y) * scale_y)
        right = round(left + node.size[0] * scale_x)
        bottom = round(top + node.size[1] * scale_y)
        if left < 0 or top < 0 or right > image.width or bottom > image.height:
            raise RuntimeError("native preview bounds fall outside the Luminar screenshot")
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.crop((left, top, right, bottom)).convert("RGB").save(
            destination, format="PNG"
        )


def select_preset_category_node(
    nodes: tuple[AccessibilityNode, ...], localized_name: str
) -> AccessibilityNode | None:
    candidates = [
        node
        for node in nodes
        if node.identifier == "_NS:59"
        and node.value == localized_name
        and node.position is not None
        and node.size is not None
        and node.size[0] <= 130
    ]
    return max(candidates, key=lambda node: node.position[1], default=None)


def _square_thumbnail(image: Image.Image, size: int = 64) -> Image.Image:
    rgb = image.convert("RGB")
    edge = min(rgb.size)
    left = (rgb.width - edge) // 2
    top = (rgb.height - edge) // 2
    return rgb.crop((left, top, left + edge, top + edge)).resize((size, size))


def thumbnail_mae(
    screenshot: Image.Image,
    target: Image.Image,
    *,
    node: AccessibilityNode,
    bounds: WindowBounds,
) -> float:
    if node.position is None or node.size is None:
        raise ValueError("asset thumbnail has no accessibility bounds")
    scale_x = screenshot.width / bounds.width
    scale_y = screenshot.height / bounds.height
    left = round((node.position[0] - bounds.x) * scale_x)
    top = round((node.position[1] - bounds.y) * scale_y)
    right = round(left + node.size[0] * scale_x)
    bottom = round(top + node.size[1] * scale_y)
    if left < 0 or top < 0 or right > screenshot.width or bottom > screenshot.height:
        raise ValueError("asset thumbnail is outside the visible Luminar window")
    candidate = screenshot.crop((left, top, right, bottom)).resize((64, 64))
    difference = ImageChops.difference(candidate.convert("RGB"), _square_thumbnail(target))
    return sum(ImageStat.Stat(difference).mean) / 3.0


def embedded_category_thumbnails(
    nodes: tuple[AccessibilityNode, ...],
    *,
    category: str,
    bounds: WindowBounds,
) -> tuple[AccessibilityNode, ...]:
    """Return visible thumbnails belonging to an inline asset collection."""

    headings = sorted(
        (
            node
            for node in nodes
            if node.identifier == "_NS:13"
            and node.position is not None
            and bounds.x <= node.position[0] < bounds.x + 230
        ),
        key=lambda node: node.position[1],  # type: ignore[index]
    )
    heading = next((node for node in headings if node.value == category), None)
    if heading is None or heading.position is None:
        return ()
    next_heading_y = min(
        (
            node.position[1]
            for node in headings
            if node.position is not None and node.position[1] > heading.position[1]
        ),
        default=bounds.y + bounds.height,
    )
    return tuple(
        node
        for node in nodes
        if node.role == "AXImage"
        and node.identifier == "_NS:58"
        and node.position is not None
        and node.size is not None
        and bounds.x <= node.position[0] < bounds.x + 230
        and heading.position[1] + 20 <= node.position[1] < next_heading_y
        and bounds.y + 90 <= node.position[1] < bounds.y + bounds.height - 90
        and 45 <= node.size[0] <= 70
        and 45 <= node.size[1] <= 70
    )


def thumbnail_match_is_confident(
    *,
    best_score: float,
    second_score: float,
    normal_maximum: float,
    hard_maximum: float,
    minimum_margin: float,
) -> bool:
    """Accept exact previews or clearly separated high-compression previews."""

    if best_score <= normal_maximum:
        return True
    return (
        best_score <= hard_maximum
        and second_score - best_score >= minimum_margin
    )


def asset_picker_scroll_value(
    *,
    asset_index: int,
    asset_count: int,
    columns: int,
    visible_rows: int,
) -> float:
    """Map a row-major asset index onto a normalized picker scrollbar value."""

    if asset_index < 0 or asset_index >= asset_count:
        raise ValueError(f"asset index is outside picker inventory: {asset_index}")
    if asset_count <= 0 or columns <= 0 or visible_rows <= 0:
        raise ValueError("asset picker dimensions must be positive")
    total_rows = math.ceil(asset_count / columns)
    maximum_start_row = max(total_rows - visible_rows, 0)
    if maximum_start_row == 0:
        return 0.0
    target_row = asset_index // columns
    if target_row < visible_rows:
        return 0.0
    start_row = min(max(target_row - 1, 0), maximum_start_row)
    return start_row / maximum_start_row


class LuminarAutoSampler:
    def __init__(
        self,
        config: LuminarSamplingConfig,
        controller: LuminarAppController,
        driver: LuminarAccessibilityDriver,
        *,
        reference_build: str,
        app_version: dict[str, str],
    ) -> None:
        self.config = config
        self.controller = controller
        self.driver = driver
        self.reference_build = reference_build
        self.app_version = app_version

    def probe(self, case: CaptureCase, layout: CaptureLayout, recipe: SamplingRecipe) -> ToolProbeResult:
        journal = CaptureJournal(layout)
        layout.prepare()
        result: ToolProbeResult | None = None
        activation_controls = recipe.effective.get("activation_locator_ids")
        activation_count = (
            len(activation_controls)
            if isinstance(activation_controls, list) and activation_controls
            else 1
        )
        activation_index = 0
        maximum_attempts = self.config.retries + activation_count
        for attempt in range(maximum_attempts):
            try:
                result = self._probe_once(
                    case,
                    layout,
                    recipe,
                    journal,
                    activation_index,
                )
                break
            except Exception as exc:  # noqa: BLE001 - native app boundary
                export_completed = any(
                    event.get("status") == str(CaptureStatus.EXPORTED)
                    for event in journal.events()
                )
                if export_completed and not isinstance(
                    exc, NonRetryableCaptureError
                ):
                    exc = NonRetryableCaptureError(
                        "Luminar export completed; post-export validation failed and "
                        f"will not repeat the export: {exc}"
                    )
                if isinstance(exc, AdvanceActivationCaptureError):
                    activation_index += 1
                can_retry = (
                    attempt < maximum_attempts - 1
                    and activation_index < activation_count
                    and not isinstance(exc, NonRetryableCaptureError)
                )
                if can_retry:
                    journal.transition(
                        CaptureStatus.PREPARING,
                        automation="macos-accessibility",
                        retry=attempt + 1,
                        activation_index=activation_index,
                        error=str(exc),
                    )
                    time.sleep(0.75)
                    continue
                journal.fail(
                    exc,
                    automation="macos-accessibility",
                    locator_id=recipe.locator_id,
                    attempts=attempt + 1,
                )
                result = self._failed_probe_result(
                    case=case,
                    recipe=recipe,
                    journal=journal,
                    error=exc,
                )
                break
        assert result is not None
        self._write_result(layout, result)
        return result

    @staticmethod
    def _failed_probe_result(
        *,
        case: CaptureCase,
        recipe: SamplingRecipe,
        journal: CaptureJournal,
        error: BaseException,
    ) -> ToolProbeResult:
        """Preserve the last useful controls when a native capture fails late."""

        attempt_events = journal.events()
        controls: tuple[dict[str, Any], ...] = ()
        effective_control = None
        effective_value: Any = None
        stable_samples = 0
        capture_level = "none"
        for event in attempt_events:
            status = event.get("status")
            if status == str(CaptureStatus.DEFAULT_CAPTURED):
                discovered = event.get("controls")
                if isinstance(discovered, list):
                    controls = tuple(
                        item for item in discovered if isinstance(item, dict)
                    )
                    capture_level = "panel"
            elif status == str(CaptureStatus.EFFECT_APPLIED):
                effective_control = event.get("control")
                effective_value = event.get("value")
                capture_level = "effect"
            elif status == str(CaptureStatus.AFTER_CAPTURED):
                stable_samples = int(event.get("stable_samples") or 0)
        return ToolProbeResult(
            case_id=case.case_id,
            capability_id=case.capability_id,
            locator_id=recipe.locator_id,
            status="failed",
            capture_level=capture_level,
            discovered_controls=controls,
            effective_control=(
                str(effective_control) if effective_control is not None else None
            ),
            effective_value=effective_value,
            stable_samples=stable_samples,
            error=str(error),
        )

    def finalize_current_result(
        self,
        case: CaptureCase,
        layout: CaptureLayout,
        journal: CaptureJournal,
    ) -> Path:
        """Capture and export a result already selected in Luminar's single view."""

        baseline_preview = layout.staging_dir / "workflow-baseline-preview.png"
        baseline_nodes = self.driver.snapshot()
        self._screenshot(layout.staging_before_path)
        self.driver.write_snapshot(layout.staging_before_ax_path, baseline_nodes)
        baseline_bounds = self._window_bounds()
        crop_native_preview(
            layout.staging_before_path,
            baseline_preview,
            node=select_preview_node(baseline_nodes, baseline_bounds),
            bounds=baseline_bounds,
        )
        stable_paths, stable_preview = self._wait_for_stable_preview(
            layout,
            baseline_preview=baseline_preview,
            require_change=False,
        )
        after_nodes = self.driver.snapshot()
        self.driver.write_snapshot(layout.staging_after_ax_path, after_nodes)
        stable_paths[-1].replace(layout.staging_after_path)
        stable_preview.replace(layout.staging_preview_path)
        journal.transition(
            CaptureStatus.AFTER_CAPTURED,
            stable_samples=len(stable_paths),
            screenshot=str(layout.staging_after_path),
        )
        export_path = self._export_case(case, layout, journal)
        self._validate_rendered_effect(
            case,
            layout=layout,
            preview_path=layout.staging_preview_path,
            export_path=export_path,
            require_change=True,
        )
        finalize_case(
            case,
            layout,
            preview_source=layout.staging_preview_path,
            export_source=export_path,
            reference_build=self.reference_build,
            operator_mode="macos-accessibility",
            app_version=self.app_version,
            preview_evidence="native-window-preview",
            export_evidence="native-export",
        )
        return export_path

    def _probe_once(
        self,
        case: CaptureCase,
        layout: CaptureLayout,
        recipe: SamplingRecipe,
        journal: CaptureJournal,
        attempt: int,
    ) -> ToolProbeResult:
        self.controller.launch(timeout_seconds=self.config.timeouts.action_seconds)
        # A previous attempt can be interrupted after the native Save sheet opens.
        # Dismiss modal UI before asking LaunchServices to open the next image;
        # otherwise `open -a` waits behind the sheet and eventually returns -1712.
        self._reset_transient_ui()
        # A running Luminar process may legitimately have no catalog window (for
        # example after a previous native export closes the document window).  The
        # capture input is the authoritative way to restore that window, so open it
        # before asking the controller to enter full screen.
        self._prepare_case(case, layout, journal, attempt)
        self.driver.activate()
        self.controller.enter_full_screen(
            timeout_seconds=self.config.timeouts.navigation_seconds
        )
        self._wait_for_accessibility_window()
        self._reset_transient_ui()
        reset_evidence = self.reset_photo_edits()
        before = self._ensure_workspace(recipe)
        self.driver.write_snapshot(layout.staging_before_ax_path, before)
        self._screenshot(layout.staging_before_path)
        baseline_preview = layout.staging_dir / "baseline-preview.png"
        before_bounds = self._window_bounds()
        crop_native_preview(
            layout.staging_before_path,
            baseline_preview,
            node=select_preview_node(before, before_bounds),
            bounds=before_bounds,
        )
        journal.transition(
            CaptureStatus.BASELINE_VERIFIED,
            automation="macos-accessibility",
            locator_id=recipe.locator_id,
            strategy=recipe.strategy,
            source_edits_reset=True,
            reset_evidence=reset_evidence,
        )

        self.driver.press(recipe.locator_id)
        journal.transition(CaptureStatus.TOOL_OPENED, locator_id=recipe.locator_id)
        after_open = self.driver.snapshot()
        activation_controls = recipe.effective.get("activation_locator_ids")
        if isinstance(activation_controls, list) and activation_controls:
            if not all(
                isinstance(locator, str) and locator for locator in activation_controls
            ):
                raise NonRetryableCaptureError(
                    f"{case.capability_id} has invalid activation locator sequence"
                )
            activation_control = activation_controls[
                min(attempt, len(activation_controls) - 1)
            ]
        else:
            activation_control = recipe.effective.get("activation_locator_id")
        if isinstance(activation_control, str) and activation_control:
            if not self.driver.has_locator(activation_control, after_open):
                raise RuntimeError(
                    f"{case.capability_id} did not expose required activation control: "
                    f"{activation_control}"
                )
            self.driver.ax_press(activation_control)
            time.sleep(0.2)
            after_open = self.driver.snapshot()
        controls = discover_new_controls(before, after_open)
        journal.transition(
            CaptureStatus.DEFAULT_CAPTURED,
            controls=[_serializable_control(node) for node in controls],
            activation_control=activation_control,
        )

        effective_control = None
        effective_value: Any = None
        capture_level = "panel"
        requested = recipe.effective.get("value")
        if recipe.strategy in VALUE_STRATEGIES and isinstance(requested, (int, float)):
            configured_slider = recipe.effective.get("control_locator_id")
            slider = (
                select_recipe_slider(controls, configured_slider)
                if isinstance(configured_slider, str) and configured_slider
                else select_primary_slider(controls)
            )
            if slider is None:
                self.driver.write_snapshot(
                    layout.staging_dir / "tool-open.ax.json", after_open
                )
                self._screenshot(layout.staging_dir / "tool-open.png")
                raise RuntimeError(f"{case.capability_id} did not expose a primary slider")
            duplicate_identifiers = sum(
                node.identifier == slider.identifier for node in after_open
            )
            effective_control = (
                slider.identifier
                if slider.identifier and duplicate_identifiers == 1
                else f"index:{slider.index}"
            )
            effective_value = normalize_recipe_value(
                slider,
                float(requested),
                value_space=(
                    str(recipe.effective["value_space"])
                    if recipe.effective.get("value_space") is not None
                    else None
                ),
            )
            if slider.enabled is not True:
                click_x, click_y = slider_click_position(slider, effective_value)
                self.driver.click_at(click_x, click_y)
                time.sleep(0.2)
                refreshed = self.driver.snapshot()
                observed = [
                    node.value
                    for node in refreshed
                    if node.role == "AXSlider"
                    and node.identifier == slider.identifier
                    and isinstance(node.value, (int, float))
                ]
                if not any(
                    math.isclose(float(value), effective_value, abs_tol=0.5)
                    for value in observed
                ):
                    raise RuntimeError(
                        f"slider click did not commit {effective_control!r}="
                        f"{effective_value}; observed={observed}"
                    )
            elif effective_control.startswith("index:"):
                observed_value = self.driver.set_value_at(slider.index, effective_value)
                if not isinstance(observed_value, (int, float)) or not math.isclose(
                    float(observed_value), effective_value, abs_tol=0.5
                ):
                    raise RuntimeError(
                        f"slider index write did not commit {effective_control!r}="
                        f"{effective_value}; observed={observed_value!r}"
                    )
            else:
                self.driver.set_value(effective_control, effective_value)
            control_readback = None
            if slider.identifier and duplicate_identifiers == 1:
                readback_nodes = self._wait_for_control_readback(
                    slider.identifier,
                    effective_value,
                )
                committed = select_unique_control(readback_nodes, slider.identifier)
                control_readback = _serializable_control(committed)
            preview_stroke = None
            raw_stroke = recipe.effective.get("stroke")
            if raw_stroke is not None:
                stroke_snapshot = self.driver.snapshot()
                preview = select_preview_node(stroke_snapshot, self._window_bounds())
                if preview is None:
                    raise RuntimeError(
                        f"{case.capability_id} preview canvas is unavailable"
                    )
                preview_stroke = normalized_preview_stroke(preview, raw_stroke)
                self.driver.drag_at(*preview_stroke)
                time.sleep(0.2)
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=effective_control,
                value=effective_value,
                parameter_binding=recipe.effective.get("parameter_binding"),
                activation_control=activation_control,
                control_readback=control_readback,
                preview_stroke=preview_stroke,
            )
            capture_level = "effect"
        elif recipe.strategy == "asset_picker":
            asset_control, asset_value = self._select_asset(
                case, recipe, after_open, layout
            )
            parameter_locator = recipe.effective.get("parameter_control_locator_id")
            if isinstance(parameter_locator, str) and parameter_locator:
                section_locator = recipe.effective.get("parameter_section_locator_id")
                time.sleep(2.0)
                parameter_nodes = self.driver.snapshot()
                if (
                    isinstance(section_locator, str)
                    and section_locator
                    and not self.driver.has_locator(parameter_locator, parameter_nodes)
                ):
                    if not self.driver.has_locator(section_locator, parameter_nodes):
                        raise RuntimeError(
                            f"{case.capability_id} did not expose parameter section: "
                            f"{section_locator}"
                        )
                    self.driver.press(section_locator)
                    time.sleep(0.2)
                    parameter_nodes = self.driver.snapshot()
                parameter_node = select_unique_control(
                    parameter_nodes, parameter_locator
                )
                requested_parameter = recipe.effective.get("parameter_value")
                if not isinstance(requested_parameter, (int, float)):
                    raise RuntimeError(
                        f"{case.capability_id} parameter recipe has no numeric value"
                    )
                parameter_value = normalize_recipe_value(
                    parameter_node, float(requested_parameter)
                )
                # Luminar reports these nested sky sliders with AXEnabled
                # unset even though AXValue is writable. Write the exact node
                # by index, then independently verify the persisted value.
                observed_value = self.driver.set_value_at(
                    parameter_node.index, parameter_value
                )
                if not isinstance(observed_value, (int, float)) or not math.isclose(
                    float(observed_value), parameter_value, abs_tol=0.5
                ):
                    click_x, click_y = slider_click_position(
                        parameter_node, parameter_value
                    )
                    self.driver.click_at(click_x, click_y)
                readback_nodes = self._wait_for_control_readback(
                    parameter_locator, parameter_value
                )
                readback = select_unique_control(readback_nodes, parameter_locator)
                effective_control = parameter_locator
                effective_value = parameter_value
                parameter_readback = _serializable_control(readback)
            else:
                effective_control = asset_control
                effective_value = asset_value
                parameter_readback = None
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=effective_control,
                value=effective_value,
                asset_control=asset_control,
                asset_value=asset_value,
                parameter_binding=recipe.effective.get("parameter_binding"),
                control_readback=parameter_readback,
            )
            capture_level = "effect"
        elif recipe.strategy == "inline_asset_picker":
            effective_control, effective_value = self._select_inline_asset(
                case, recipe, after_open, layout
            )
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=effective_control,
                value=effective_value,
            )
            capture_level = "effect"
        elif recipe.strategy == "button_choice":
            control_locator = recipe.effective.get("control_locator_id")
            if not isinstance(control_locator, str) or not control_locator:
                raise RuntimeError(
                    f"{case.capability_id} button recipe is missing control_locator_id"
                )
            if not self.driver.has_locator(control_locator, after_open):
                raise RuntimeError(
                    f"{case.capability_id} did not expose required button: "
                    f"{control_locator}"
                )
            self.driver.press(control_locator)
            effective_control = control_locator
            effective_value = recipe.effective.get("value", control_locator)
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=effective_control,
                value=effective_value,
            )
            capture_level = "effect"
        elif recipe.strategy == "menu_choice":
            control_locator = recipe.effective.get("control_locator_id")
            choice_locator = recipe.effective.get("choice_locator_id")
            if not isinstance(control_locator, str) or not control_locator:
                raise RuntimeError(
                    f"{case.capability_id} menu recipe is missing control_locator_id"
                )
            if not isinstance(choice_locator, str) or not choice_locator:
                raise RuntimeError(
                    f"{case.capability_id} menu recipe is missing choice_locator_id"
                )
            if not self.driver.has_locator(control_locator, after_open):
                raise RuntimeError(
                    f"{case.capability_id} did not expose required menu: "
                    f"{control_locator}"
                )
            before_control = select_unique_control(after_open, control_locator)
            self.driver.press(control_locator)
            menu_nodes = self.driver.snapshot()
            choice_parent = recipe.effective.get("choice_parent_locator_id")
            if isinstance(choice_parent, str) and choice_parent:
                if not self.driver.has_locator(choice_parent, menu_nodes):
                    raise RuntimeError(
                        f"{case.capability_id} did not expose required menu parent: "
                        f"{choice_parent}"
                    )
                self.driver.press(choice_parent)
                time.sleep(0.2)
                menu_nodes = self.driver.snapshot()
            if not self.driver.has_locator(choice_locator, menu_nodes):
                raise RuntimeError(
                    f"{case.capability_id} did not expose required menu choice: "
                    f"{choice_locator}"
                )
            self.driver.press(choice_locator)
            effective_control = control_locator
            effective_value = recipe.effective.get("value", choice_locator)
            if recipe.effective.get("control_readback") == "edit_state":
                readback_nodes = self.driver.snapshot()
            else:
                readback_nodes = self._wait_for_control_readback(
                    control_locator, effective_value
                )
            committed_control = select_unique_control(readback_nodes, control_locator)
            control_readback: dict[str, Any] = {
                "before": _serializable_control(before_control),
                "after": _serializable_control(committed_control),
                "choice_parent": choice_parent,
                "verification": recipe.effective.get(
                    "control_readback", "control-value"
                ),
            }
            slider_locator = recipe.effective.get("slider_locator_id")
            slider_value = recipe.effective.get("slider_value")
            if isinstance(slider_locator, str) and isinstance(
                slider_value, (int, float)
            ):
                slider = select_recipe_slider(controls, slider_locator)
                normalized_value = normalize_recipe_value(slider, float(slider_value))
                if slider.identifier is None:
                    self.driver.set_value_at(slider.index, normalized_value)
                else:
                    self.driver.set_value(slider.identifier, normalized_value)
                slider_nodes = self._wait_for_control_readback(
                    slider_locator, normalized_value
                )
                committed_slider = select_unique_control(slider_nodes, slider_locator)
                control_readback["slider"] = _serializable_control(committed_slider)
                effective_control = f"{control_locator}+{slider_locator}"
                effective_value = {
                    "choice": recipe.effective.get("value", choice_locator),
                    "slider": normalized_value,
                }
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=effective_control,
                value=effective_value,
                choice=choice_locator,
                control_readback=control_readback,
            )
            capture_level = "effect"
        elif recipe.strategy == "deterministic_stroke":
            raw_stroke = recipe.effective.get("stroke")
            raw_source = recipe.effective.get("source")
            apply_locator = recipe.effective.get("apply_locator_id")
            if (
                not isinstance(raw_stroke, list)
                or len(raw_stroke) != 4
                or not all(isinstance(value, (int, float)) for value in raw_stroke)
                or (
                    apply_locator is not None
                    and (not isinstance(apply_locator, str) or not apply_locator)
                )
                or (
                    raw_source is not None
                    and (
                        not isinstance(raw_source, list)
                        or len(raw_source) != 2
                        or not all(
                            isinstance(value, (int, float)) for value in raw_source
                        )
                    )
                )
            ):
                self.driver.write_snapshot(
                    layout.staging_dir / "tool-open.ax.json", after_open
                )
                self._screenshot(layout.staging_dir / "tool-open.png")
                raise RuntimeError(
                    f"{case.capability_id} deterministic stroke recipe is incomplete"
                )
            if not all(0 <= float(value) <= 1 for value in raw_stroke):
                raise RuntimeError(
                    f"{case.capability_id} stroke coordinates must be normalized"
                )
            if raw_source is not None and not all(
                0 <= float(value) <= 1 for value in raw_source
            ):
                raise RuntimeError(
                    f"{case.capability_id} source coordinates must be normalized"
                )
            bounds = self._window_bounds()
            preview = select_preview_node(after_open, bounds)
            if preview is None or preview.position is None or preview.size is None:
                raise RuntimeError(f"{case.capability_id} preview canvas is unavailable")
            start_x, start_y, end_x, end_y = normalized_preview_stroke(
                preview, raw_stroke
            )
            x, y = preview.position
            width, height = preview.size
            source_point = None
            if raw_source is not None:
                source_point = [
                    round(x + width * float(raw_source[0])),
                    round(y + height * float(raw_source[1])),
                ]
                self.driver.click_at(*source_point)
                time.sleep(0.2)
            self.driver.drag_at(start_x, start_y, end_x, end_y)
            time.sleep(0.2)
            if apply_locator is not None:
                if not self.driver.has_locator(apply_locator):
                    raise RuntimeError(
                        f"{case.capability_id} did not expose apply button: "
                        f"{apply_locator}"
                    )
                self.driver.press(apply_locator)
            effective_control = apply_locator or "preview-canvas"
            effective_value = {
                "stroke": [start_x, start_y, end_x, end_y],
                "normalized_stroke": raw_stroke,
                "source": source_point,
                "normalized_source": raw_source,
            }
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=effective_control,
                value=effective_value,
            )
            capture_level = "effect"
        elif recipe.strategy == "layer_asset_picker":
            effective_control, effective_value = self._select_layer_asset(
                case, recipe, after_open, layout
            )
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=effective_control,
                value=effective_value,
            )
            capture_level = "effect"
        elif recipe.strategy == "preset":
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                control=recipe.locator_id,
                value=recipe.effective.get("name", recipe.locator_id),
            )
            effective_control = recipe.locator_id
            effective_value = recipe.effective.get("name", recipe.locator_id)
            capture_level = "effect"

        require_render_change = render_change_required(capture_level, recipe)
        edit_state = (
            self._verify_photo_has_edits()
            if require_render_change
            else {"required": False, "verified": False}
        )
        stable_paths, stable_preview = self._wait_for_stable_preview(
            layout,
            baseline_preview=baseline_preview,
            # Luminar's enabled restore-original action is the authoritative
            # signal that an edit was committed.  Requiring a separate preview
            # delta here made AI tools sit idle until the inference timeout even
            # though their edit graph was already ready for export.
            require_change=False if edit_state["verified"] else require_render_change,
            required_samples=1 if edit_state["verified"] else None,
            timeout_seconds=(
                self.config.timeouts.heavy_inference_seconds
                if recipe.effective.get("heavy_inference") is True
                else self.config.timeouts.inference_seconds
            ),
            change_mae_min=(
                float(recipe.effective["preview_change_mae_min"])
                if recipe.effective.get("preview_change_mae_min") is not None
                else None
            ),
        )
        after = self.driver.snapshot()
        self.driver.write_snapshot(layout.staging_after_ax_path, after)
        stable_paths[-1].replace(layout.staging_after_path)
        stable_preview.replace(layout.staging_preview_path)
        journal.transition(
            CaptureStatus.AFTER_CAPTURED,
            stable_samples=len(stable_paths),
            screenshot=str(layout.staging_after_path),
            edit_state=edit_state,
        )
        export_path = self._export_case(case, layout, journal)
        if edit_state["verified"]:
            # Export starts as soon as Luminar exposes a committed edit.  The
            # native export blocks until its full render is written, so capture
            # the final preview afterwards instead of idling before export.
            rendered_paths, rendered_preview = self._wait_for_stable_preview(
                layout,
                baseline_preview=baseline_preview,
                require_change=False,
                required_samples=1,
            )
            rendered_after = rendered_paths[-1]
            rendered_after.replace(layout.staging_after_path)
            rendered_preview.replace(layout.staging_preview_path)
            self.driver.write_snapshot(
                layout.staging_after_ax_path,
                self.driver.snapshot(),
            )
        self._validate_rendered_effect(
            case,
            layout=layout,
            preview_path=layout.staging_preview_path,
            export_path=export_path,
            require_change=require_render_change,
            recipe=recipe,
            attempt=attempt,
            require_preview_export_match=not edit_state["verified"],
        )
        finalize_case(
            case,
            layout,
            preview_source=layout.staging_preview_path,
            export_source=export_path,
            reference_build=self.reference_build,
            operator_mode="macos-accessibility",
            app_version=self.app_version,
            preview_evidence="native-window-preview",
            export_evidence="native-export",
        )
        return ToolProbeResult(
            case_id=case.case_id,
            capability_id=case.capability_id,
            locator_id=recipe.locator_id,
            status="ready",
            capture_level=capture_level,
            discovered_controls=tuple(_serializable_control(node) for node in controls),
            effective_control=effective_control,
            effective_value=effective_value,
            stable_samples=len(stable_paths),
            export_path=str(export_path),
        )

    def _export_case(
        self,
        case: CaptureCase,
        layout: CaptureLayout,
        journal: CaptureJournal,
    ) -> Path:
        export_started = time.monotonic()
        self.config.native_export_root.mkdir(parents=True, exist_ok=True)
        state = journal.read()
        attempt_id = str(state.get("active_attempt_id") or "missing-attempt")
        export_stem = build_native_export_stem(case, attempt_id)
        before_exports = snapshot_export_files(self.config.native_export_root)
        collisions = [path for path in before_exports if path.stem == export_stem]
        if collisions:
            raise FileExistsError(
                f"unique native export already exists: {collisions[0]}"
            )

        # Luminar's tracking NSMenu cannot be traversed reliably by the same
        # AX process that opened it.  The helper performs one idle-gated click
        # on the measured New Export row and restores the cursor immediately.
        self.driver.open_export_dialog()
        journal.transition(
            CaptureStatus.PREVIEW_STABLE,
            export_menu_item="NSMenuItem.NewExport",
            export_menu_selection="guarded-global-popup",
        )
        dialog_started = time.monotonic()
        location = self._wait_for_first_value("where popup")
        if str(location) != self.config.native_export_root.name:
            self._ensure_export_directory()
        export_dimensions = self._ensure_original_export_dimensions(case)
        written_name = self._wait_for_first_value(
            "saveAsNameTextField",
            value=export_stem,
        )
        if str(written_name) != export_stem:
            raise RuntimeError(
                f"Luminar export filename was not accepted: {written_name!r}"
            )
        self.driver.press_first("OKButton")
        file_stable_started = time.monotonic()
        export_path = wait_for_new_stable_export(
            self.config.native_export_root,
            stem=export_stem,
            before=before_exports,
            timeout_seconds=self.config.timeouts.export_seconds,
        )
        journal.transition(
            CaptureStatus.EXPORTED,
            export_path=str(export_path),
            export_seconds=round(time.monotonic() - export_started, 6),
            export_dialog_seconds=round(file_stable_started - dialog_started, 6),
            file_stable_seconds=round(time.monotonic() - file_stable_started, 6),
            export_dimensions=export_dimensions,
        )
        return export_path

    def _ensure_original_export_dimensions(
        self, case: CaptureCase
    ) -> dict[str, list[int]]:
        """Force the Save sheet back to the oriented source dimensions."""

        with Image.open(case.input_path) as source:
            target = list(ImageOps.exif_transpose(source).size)
        locators = ("_NS:262", "_NS:254")
        before = [int(self._wait_for_first_value(locator)) for locator in locators]
        if before != target:
            for locator, value in zip(locators, target, strict=True):
                self._wait_for_first_value(locator, value=str(value))
        after = [int(self._wait_for_first_value(locator)) for locator in locators]
        if after != target:
            raise RuntimeError(
                f"Luminar export dimensions were not restored: {after} != {target}"
            )
        return {"before": before, "target": target, "after": after}

    def _wait_for_first_value(
        self,
        locator: str,
        *,
        value: str | None = None,
    ) -> Any:
        """Read or write a unique Save-sheet control without serializing its tree."""

        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        last_error: RuntimeError | TimeoutError | None = None
        while time.monotonic() < deadline:
            try:
                if value is None:
                    return self.driver.read_value_first(locator)
                return self.driver.set_value_first(locator, value)
            except (RuntimeError, TimeoutError) as exc:
                last_error = exc
                time.sleep(0.2)
        raise TimeoutError(
            f"Luminar did not expose Save-sheet locator {locator}: {last_error}"
        )

    def _confirm_export_replacement(
        self,
        *,
        stem: str,
        exports_before: dict[Path, tuple[int, int]],
    ) -> None:
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        while time.monotonic() < deadline:
            if export_signature_changed(
                self.config.native_export_root,
                stem=stem,
                before=exports_before,
            ):
                return
            nodes = self.driver.snapshot()
            locator = select_replacement_locator(nodes)
            if locator is not None:
                self.driver.ax_press(locator)
                return
            time.sleep(0.2)
        raise TimeoutError(
            "Luminar did not expose an overwrite confirmation and the existing "
            f"export did not change: {stem}"
        )

    def _ensure_export_directory(
        self,
        panel_nodes: tuple[AccessibilityNode, ...] | None = None,
    ) -> None:
        # The native Save sheet exposes every file in the current directory.
        # Reuse the snapshot that found the filename field; taking an identical
        # second snapshot in a large archive used to add roughly 30 seconds before
        # the filename was visibly changed.
        panel_nodes = panel_nodes or self._wait_for_locator("where popup")
        current_location = next(
            (node for node in panel_nodes if node.identifier == "where popup"), None
        )
        if (
            current_location is not None
            and current_location.value == self.config.native_export_root.name
        ):
            return
        self.driver.open_go_to_folder()
        folder_nodes = self._wait_for_focused_text_field()
        field = next(
            node
            for node in folder_nodes
            if node.role == "AXTextField" and node.focused is True
        )
        self.driver.set_value_at(field.index, str(self.config.native_export_root))
        self.driver.confirm()
        panel_nodes = self._wait_for_locator("where popup")
        location = next(
            node for node in panel_nodes if node.identifier == "where popup"
        )
        if location.value != self.config.native_export_root.name:
            raise RuntimeError(
                "Luminar export directory does not match configured native_export_root: "
                f"{location.value!r} != {self.config.native_export_root.name!r}"
            )

    def _wait_for_focused_text_field(self) -> tuple[AccessibilityNode, ...]:
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        last_snapshot_error: TimeoutError | None = None
        while time.monotonic() < deadline:
            try:
                nodes = self.driver.snapshot()
            except TimeoutError as exc:
                last_snapshot_error = exc
                continue
            if any(
                node.role == "AXTextField" and node.focused is True for node in nodes
            ):
                return nodes
            time.sleep(0.2)
        detail = (
            f"; last accessibility error: {last_snapshot_error}"
            if last_snapshot_error is not None
            else ""
        )
        raise TimeoutError(f"Luminar Go to Folder field did not become focused{detail}")

    def _wait_for_locator(
        self,
        locator: str,
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[AccessibilityNode, ...]:
        deadline = time.monotonic() + (
            self.config.timeouts.navigation_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        last_snapshot_error: TimeoutError | None = None
        while time.monotonic() < deadline:
            try:
                nodes = self.driver.snapshot()
            except TimeoutError as exc:
                last_snapshot_error = exc
                continue
            if self.driver.has_locator(locator, nodes):
                return nodes
            time.sleep(0.2)
        detail = (
            f"; last accessibility error: {last_snapshot_error}"
            if last_snapshot_error is not None
            else ""
        )
        raise TimeoutError(
            f"Luminar did not expose required locator: {locator}{detail}"
        )

    def _wait_for_control_readback(
        self, locator: str, expected: Any
    ) -> tuple[AccessibilityNode, ...]:
        deadline = time.monotonic() + self.config.timeouts.action_seconds
        last_value: Any = None
        while time.monotonic() < deadline:
            nodes = self.driver.snapshot()
            matches = [node for node in nodes if node.identifier == locator]
            if len(matches) == 1:
                last_value = matches[0].value
                if control_readback_matches(matches[0], expected):
                    return nodes
            time.sleep(0.2)
        raise NonRetryableCaptureError(
            f"Luminar control did not persist committed value: {locator}: "
            f"expected={expected!r}, observed={last_value!r}"
        )

    def _prepare_case(
        self,
        case: CaptureCase,
        layout: CaptureLayout,
        journal: CaptureJournal,
        attempt: int,
    ) -> None:
        hasher = hashlib.sha256()
        with case.input_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != case.input_sha256:
            raise RuntimeError(
                f"capture input hash mismatch for {case.case_id}: "
                f"{digest} != {case.input_sha256}"
            )
        source = case.input_path.resolve()
        already_selected = False
        try:
            already_selected = self._snapshot_mentions_file(
                self.driver.snapshot(), source.name
            )
        except (RuntimeError, TimeoutError):
            # A closed, importing, or temporarily unresponsive native window is
            # handled by the normal open-and-wait path below.
            pass
        if not already_selected:
            self.controller.request_open_image(source)
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        last_snapshot_error: TimeoutError | None = None
        input_verification = "filename"
        input_metrics: dict[str, float] | None = None
        while time.monotonic() < deadline:
            try:
                nodes = self.driver.snapshot()
            except TimeoutError as exc:
                # Luminar can temporarily stop answering Accessibility while it
                # imports or renders a newly opened image.  Keep the existing
                # navigation deadline as the total budget instead of turning one
                # helper timeout into a failed capture attempt.
                last_snapshot_error = exc
                continue
            if self._snapshot_mentions_file(nodes, source.name):
                break
            bounds = self._window_bounds()
            preview = select_preview_node(nodes, bounds)
            if preview is not None:
                window_path = layout.staging_dir / "input-open-window.png"
                preview_path = layout.staging_dir / "input-open-preview.png"
                try:
                    self._screenshot(window_path)
                    crop_native_preview(
                        window_path,
                        preview_path,
                        node=preview,
                        bounds=bounds,
                    )
                    matched, input_metrics = rendered_source_matches(
                        source,
                        preview_path,
                        size=self.config.preview_export_comparison_size,
                        rgb_mae_max=self.config.preview_export_rgb_mae_max,
                        luma_mae_max=self.config.preview_export_luma_mae_max,
                    )
                    if matched:
                        input_verification = "rendered-source"
                        break
                except (OSError, RuntimeError, ValueError):
                    pass
            time.sleep(0.25)
        else:
            detail = (
                f"; last accessibility error: {last_snapshot_error}"
                if last_snapshot_error is not None
                else ""
            )
            raise TimeoutError(
                f"Luminar did not select capture input {source.name!r}; "
                f"the filename was absent from its accessibility tree{detail}"
            )
        journal.transition(
            CaptureStatus.PHOTO_SELECTED,
            input_path=str(source),
            input_sha256=case.input_sha256,
            input_verification=input_verification,
            input_metrics=input_metrics,
            attempt=attempt,
        )
        time.sleep(min(0.5, self.config.timeouts.stable_seconds))

    def _reset_transient_ui(self) -> None:
        for _ in range(3):
            self.driver.cancel()
            time.sleep(0.1)

    def reset_photo_edits(self) -> dict[str, Any]:
        reset_action_count = self._clear_photo_edits(
            timeout_seconds=self.config.timeouts.navigation_seconds
        )
        if reset_action_count is None:
            raise NonRetryableCaptureError(
                "Luminar restore-original action left a non-empty edit stack"
            )
        return {
            "strategy": (
                "reset-action" if reset_action_count else "disabled-reset-action"
            ),
            "reset_performed": reset_action_count > 0,
            "reset_action_count": reset_action_count,
            "reset_control_disabled_after": True,
            "source_match": None,
            "source_metrics": None,
            "source_verification": "selected-input+disabled-reset-action",
        }

    def _clear_photo_edits(self, *, timeout_seconds: float) -> int | None:
        """Repeat the atomic native reset action until it reports disabled."""

        deadline = time.monotonic() + (
            timeout_seconds
        )
        reset_action_count = 0
        while time.monotonic() < deadline:
            try:
                result = self.driver.reset_all_edits(perform=True)
            except RuntimeError:
                time.sleep(0.2)
                continue
            if result.get("enabled") is False:
                return reset_action_count
            if result.get("performed") is True:
                reset_action_count += 1
            time.sleep(0.2)
        return None

    def _wait_for_locator_absent(
        self,
        locator: str,
        *,
        timeout_seconds: float,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if not self.driver.has_locator(locator, self.driver.snapshot()):
                    return True
            except TimeoutError:
                pass
            time.sleep(0.1)
        return False

    def _verify_photo_has_edits(self) -> dict[str, Any]:
        """Wait for Luminar's restore-original action to prove an edit exists."""

        deadline = time.monotonic() + self.config.timeouts.action_seconds
        last_enabled: bool | None = None
        while time.monotonic() < deadline:
            try:
                result = self.driver.reset_all_edits(perform=False)
                last_enabled = bool(result.get("enabled"))
                if last_enabled:
                    return {
                        "required": True,
                        "verified": True,
                        "locator_id": RESET_ALL_EDITS_LOCATOR,
                        "enabled": True,
                    }
            except RuntimeError:
                pass
            time.sleep(0.1)
        raise NonRetryableCaptureError(
            "Luminar did not create an enabled restore-original state; "
            f"last_enabled={last_enabled!r}; refusing to export an unapplied effect"
        )

    @staticmethod
    def _snapshot_mentions_file(
        nodes: tuple[AccessibilityNode, ...], filename: str
    ) -> bool:
        expected = filename.casefold()
        for node in nodes:
            for value in (node.identifier, node.title, node.description, node.help, node.value):
                if isinstance(value, str) and expected in value.casefold():
                    return True
        return False

    def _wait_for_accessibility_window(self) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = self.driver.state()
            if int(last_state.get("window_count", 0)) > 0:
                return last_state
            time.sleep(0.25)
        raise RuntimeError(
            "Luminar accessibility window is unavailable: "
            + json.dumps(last_state, ensure_ascii=False)
        )

    def _select_asset(
        self,
        case: CaptureCase,
        recipe: SamplingRecipe,
        panel_nodes: tuple[AccessibilityNode, ...],
        layout: CaptureLayout,
    ) -> tuple[str, str]:
        picker_locator = recipe.effective.get("picker_locator_id")
        if not isinstance(picker_locator, str) or not picker_locator:
            self.driver.write_snapshot(
                layout.staging_dir / "tool-open.ax.json", panel_nodes
            )
            self._screenshot(layout.staging_dir / "tool-open.png")
            raise RuntimeError(
                f"{case.capability_id} asset recipe is missing picker_locator_id"
            )
        panel_keys = {node.stable_key for node in panel_nodes}
        picker_thumbnail_identifier = recipe.effective.get(
            "picker_thumbnail_identifier"
        )
        picker_scrollbar_identifier = recipe.effective.get(
            "picker_scrollbar_identifier"
        )

        def picker_scrollbar(
            nodes: tuple[AccessibilityNode, ...],
        ) -> AccessibilityNode | None:
            if isinstance(picker_scrollbar_identifier, str):
                return next(
                    (
                        node
                        for node in nodes
                        if node.role == "AXScrollBar"
                        and node.identifier == picker_scrollbar_identifier
                    ),
                    None,
                )
            return None

        def is_picker_thumbnail(
            node: AccessibilityNode,
            scrollbar: AccessibilityNode | None,
        ) -> bool:
            if (
                isinstance(picker_thumbnail_identifier, str)
                and picker_thumbnail_identifier
                and node.identifier != picker_thumbnail_identifier
            ):
                return False
            matches = (
                node.role == "AXButton"
                and node.enabled is not False
                and node.stable_key not in panel_keys
                and node.position is not None
                and node.size is not None
                and 48 <= node.size[0] <= 180
                and 48 <= node.size[1] <= 180
                and 0.65 <= node.size[0] / node.size[1] <= 1.5
            )
            if (
                not matches
                or scrollbar is None
                or scrollbar.position is None
                or scrollbar.size is None
                or node.position is None
                or node.size is None
            ):
                return matches
            viewport_top = scrollbar.position[1]
            viewport_bottom = viewport_top + scrollbar.size[1]
            return (
                node.position[0] + node.size[0] <= scrollbar.position[0]
                and viewport_top <= node.position[1]
                and node.position[1] + node.size[1] <= viewport_bottom
            )

        picker_nodes: tuple[AccessibilityNode, ...] = ()
        for _ in range(3):
            self.driver.press(picker_locator)
            time.sleep(0.8)
            picker_nodes = self.driver.snapshot()
            if self.driver.has_locator("所有天空", picker_nodes):
                break
        else:
            raise TimeoutError("Luminar did not expose required locator: 所有天空")
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        thumbnails: list[AccessibilityNode] = []
        while time.monotonic() < deadline:
            scrollbar = picker_scrollbar(picker_nodes)
            thumbnails = [
                node
                for node in picker_nodes
                if is_picker_thumbnail(node, scrollbar)
            ]
            if thumbnails:
                break
            time.sleep(0.2)
            picker_nodes = self.driver.snapshot()
        asset_index = recipe.effective.get("asset_index")
        asset_count = recipe.effective.get("asset_count")
        if isinstance(asset_index, int) and isinstance(asset_count, int):
            positions = {
                node.position
                for node in thumbnails
                if node.position is not None
            }
            columns = len({position[0] for position in positions})
            visible_rows = len({position[1] for position in positions})
            scroll_value = asset_picker_scroll_value(
                asset_index=asset_index,
                asset_count=asset_count,
                columns=columns,
                visible_rows=visible_rows,
            )
            active_scrollbar = scrollbar or next(
                (
                    node
                    for node in picker_nodes
                    if node.role == "AXScrollBar"
                    and node.orientation == "AXVerticalOrientation"
                    and node.position is not None
                    and node.size is not None
                    and node.position[0] >= min(position[0] for position in positions)
                    and node.size[1] <= 500
                ),
                None,
            )
            if active_scrollbar is None:
                raise RuntimeError("Luminar sky picker has no dedicated scrollbar")
            self.driver.set_value_at(active_scrollbar.index, scroll_value)
            time.sleep(0.2)
            picker_nodes = self.driver.snapshot()
            scrollbar = picker_scrollbar(picker_nodes)
            thumbnails = [
                node
                for node in picker_nodes
                if is_picker_thumbnail(node, scrollbar)
            ]
        if asset_index == 0 and case.asset_path is not None:
            anchor = min(
                thumbnails,
                key=lambda node: (
                    node.position[1] if node.position is not None else math.inf,
                    node.position[0] if node.position is not None else math.inf,
                ),
            )
            siblings = [
                node
                for node in picker_nodes
                if node.role == "AXButton"
                and node.enabled is not False
                and node.position == anchor.position
                and node.size == anchor.size
                and node.stable_key not in panel_keys
            ]
            # Each native sky cell exposes two overlaid buttons.  The earlier
            # sibling selects the catalog asset; the later _NS:65 overlay is a
            # secondary cell action.  Choosing the latter produced Blue Sky 3
            # even though the first catalog cell is Blue Sky 1.
            thumbnail = min(siblings, key=lambda node: node.index)
            self.driver.press_at(thumbnail.index)
            expected_name = case.asset_path.stem.casefold()
            deadline = time.monotonic() + self.config.timeouts.action_seconds
            while time.monotonic() < deadline:
                selected_nodes = self.driver.snapshot()
                picker = next(
                    (
                        node
                        for node in selected_nodes
                        if node.identifier == picker_locator
                    ),
                    None,
                )
                if picker is not None and any(
                    expected_name == str(value).strip().casefold()
                    for value in (
                        picker.title,
                        picker.value,
                        picker.description,
                        picker.help,
                    )
                    if value is not None
                ):
                    return f"index:{thumbnail.index}", case.asset_id or expected_name
                time.sleep(0.1)
            raise RuntimeError(
                f"{case.capability_id}: first catalog asset did not read back as "
                f"{case.asset_path.stem!r}"
            )
        if case.asset_path is not None:
            thumbnail = self._select_visible_asset_by_image(
                case, recipe, thumbnails, layout
            )
        else:
            try:
                thumbnail = select_asset_thumbnail(thumbnails, asset_id=case.asset_id)
            except RuntimeError as exc:
                raise RuntimeError(f"{case.capability_id}: {exc}") from exc
        self.driver.press_at(thumbnail.index)
        return f"index:{thumbnail.index}", case.asset_id or str(
            recipe.effective.get("asset_policy", "first")
        )

    def _select_inline_asset(
        self,
        case: CaptureCase,
        recipe: SamplingRecipe,
        panel_nodes: tuple[AccessibilityNode, ...],
        layout: CaptureLayout,
    ) -> tuple[str, str]:
        picker_locator = recipe.effective.get("picker_locator_id")
        thumbnail_identifier = recipe.effective.get("picker_thumbnail_identifier")
        if not isinstance(picker_locator, str) or not picker_locator:
            raise RuntimeError(
                f"{case.capability_id} inline recipe is missing picker_locator_id"
            )
        if not isinstance(thumbnail_identifier, str) or not thumbnail_identifier:
            raise RuntimeError(
                f"{case.capability_id} inline recipe is missing "
                "picker_thumbnail_identifier"
            )
        if not self.driver.has_locator(picker_locator, panel_nodes):
            raise RuntimeError(
                f"{case.capability_id} did not expose inline picker: {picker_locator}"
            )
        self.driver.press(picker_locator)
        time.sleep(0.5)
        picker_nodes = self.driver.snapshot()
        thumbnails = [
            node
            for node in picker_nodes
            if node.role == "AXButton"
            and node.identifier == thumbnail_identifier
            and node.enabled is not False
            and node.position is not None
            and node.size is not None
            and node.position[0] >= 1000
            and 48 <= node.size[0] <= 180
            and 48 <= node.size[1] <= 180
        ]
        thumbnail = self._select_visible_asset_by_image(
            case, recipe, thumbnails, layout
        )
        self.driver.press_at(thumbnail.index)
        return f"index:{thumbnail.index}", case.asset_id or thumbnail_identifier

    def _select_layer_asset(
        self,
        case: CaptureCase,
        recipe: SamplingRecipe,
        panel_nodes: tuple[AccessibilityNode, ...],
        layout: CaptureLayout,
    ) -> tuple[str, str]:
        category = recipe.effective.get("category")
        if not isinstance(category, str) or not category:
            raise RuntimeError("layer asset recipe requires a localized category")
        if case.asset_path is None or not case.asset_path.is_file():
            raise FileNotFoundError(
                f"layer asset does not exist: {case.asset_path or case.asset_id}"
            )
        digest = hashlib.sha256(case.asset_path.read_bytes()).hexdigest()
        if case.asset_sha256 and digest != case.asset_sha256:
            raise RuntimeError(
                f"layer asset hash mismatch: {digest} != {case.asset_sha256}"
            )

        nodes = panel_nodes
        if not any(
            node.identifier == "_NS:13" and node.value == category for node in nodes
        ) and any(node.identifier == "_NS:61" for node in nodes):
            self.driver.ax_press("_NS:16")
            nodes = self.driver.snapshot()

        bounds = self._window_bounds()
        thumbnails: tuple[AccessibilityNode, ...] | None = None
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        while time.monotonic() < deadline:
            heading = next(
                (
                    node
                    for node in nodes
                    if node.identifier == "_NS:13"
                    and node.value == category
                    and node.position is not None
                ),
                None,
            )
            if heading is None or heading.position is None:
                raise RuntimeError(f"Luminar layer category is absent: {category}")
            links = [
                node
                for node in nodes
                if node.role == "AXCheckBox"
                and node.title == "查看全部"
                and node.position is not None
                and abs(node.position[1] - heading.position[1]) <= 30
            ]
            visible = (
                bounds.y + 100 <= heading.position[1] <= bounds.y + bounds.height - 180
            )
            if visible and len(links) == 1:
                link = links[0]
                assert link.position is not None and link.size is not None
                self.driver.click_at(
                    link.position[0] + link.size[0] // 2,
                    link.position[1] + link.size[1] // 2,
                )
                break
            if visible and not links:
                scrollbar = next(
                    (
                        node
                        for node in nodes
                        if node.role == "AXScrollBar"
                        and node.orientation == "AXVerticalOrientation"
                        and node.position is not None
                        and bounds.x <= node.position[0] < bounds.x + 230
                    ),
                    None,
                )
                if scrollbar is not None and scrollbar.value != 1:
                    self.driver.set_value_at(scrollbar.index, 1.0)
                    time.sleep(0.2)
                    nodes = self.driver.snapshot()
                thumbnails = embedded_category_thumbnails(
                    nodes, category=category, bounds=bounds
                )
                if thumbnails:
                    break
            lines = (
                -self.config.panel_scroll_lines
                if heading.position[1] > bounds.y + bounds.height - 180
                else self.config.panel_scroll_lines
            )
            self.driver.scroll_at(bounds.x + 180, bounds.y + bounds.height - 200, lines)
            time.sleep(0.2)
            nodes = self.driver.snapshot()
        else:
            raise TimeoutError(f"Luminar layer category is unavailable: {category}")

        if thumbnails is None:
            deadline = time.monotonic() + self.config.timeouts.navigation_seconds
            while time.monotonic() < deadline:
                nodes = self.driver.snapshot()
                thumbnails = tuple(
                    node
                    for node in nodes
                    if node.role == "AXImage"
                    and node.identifier == "_NS:58"
                    and node.position is not None
                    and node.size is not None
                    and bounds.x <= node.position[0] < bounds.x + 230
                    and bounds.y + 90
                    <= node.position[1]
                    < bounds.y + bounds.height - 140
                    and 45 <= node.size[0] <= 70
                    and 45 <= node.size[1] <= 70
                )
                if thumbnails and any(
                    node.identifier == "_NS:61" and node.value == category
                    for node in nodes
                ):
                    break
                thumbnails = None
                time.sleep(0.2)
            else:
                raise TimeoutError(f"Luminar did not open layer category: {category}")

        assert thumbnails

        screenshot_path = layout.staging_dir / "layer-picker.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._screenshot(screenshot_path)
        with Image.open(screenshot_path) as screenshot, Image.open(
            case.asset_path
        ) as target:
            scores = sorted(
                [
                    (
                        thumbnail_mae(screenshot, target, node=node, bounds=bounds),
                        node,
                    )
                    for node in thumbnails
                ],
                key=lambda item: item[0],
            )
        best_score, best = scores[0]
        second_score = scores[1][0] if len(scores) > 1 else float("inf")
        maximum = float(recipe.effective.get("thumbnail_mae_max", 12.0))
        hard_maximum = float(
            recipe.effective.get("thumbnail_mae_hard_max", maximum)
        )
        minimum_margin = float(recipe.effective.get("thumbnail_margin_min", 0.0))
        if not thumbnail_match_is_confident(
            best_score=best_score,
            second_score=second_score,
            normal_maximum=maximum,
            hard_maximum=hard_maximum,
            minimum_margin=minimum_margin,
        ):
            raise RuntimeError(
                f"layer asset has no exact visual match in its declared collection: "
                f"best={best_score:.2f}, second={second_score:.2f}, declared_index="
                f"{recipe.effective['asset_index']}, asset={case.asset_id}"
            )
        screenshot_path.unlink(missing_ok=True)
        self.driver.press_at(best.index)
        return f"index:{best.index}", case.asset_id or digest

    def _select_visible_asset_by_image(
        self,
        case: CaptureCase,
        recipe: SamplingRecipe,
        nodes: list[AccessibilityNode],
        layout: CaptureLayout,
        *,
        require_confident: bool = True,
    ) -> AccessibilityNode:
        assert case.asset_path is not None
        if not case.asset_path.is_file():
            raise FileNotFoundError(f"capture asset does not exist: {case.asset_path}")
        if case.asset_sha256:
            digest = hashlib.sha256(case.asset_path.read_bytes()).hexdigest()
            if digest != case.asset_sha256:
                raise RuntimeError(
                    f"capture asset hash mismatch: {digest} != {case.asset_sha256}"
                )
        unique: dict[tuple[tuple[int, int], tuple[int, int]], AccessibilityNode] = {}
        bounds = self._window_bounds()
        for node in nodes:
            if node.position is None or node.size is None:
                continue
            x, y = node.position
            width, height = node.size
            if (
                x < bounds.x
                or y < bounds.y
                or x + width > bounds.x + bounds.width
                or y + height > bounds.y + bounds.height
            ):
                continue
            unique.setdefault((node.position, node.size), node)
        screenshot_path = layout.staging_dir / "asset-picker.png"
        self._screenshot(screenshot_path)
        with Image.open(screenshot_path) as screenshot, Image.open(
            case.asset_path
        ) as target:
            scores = sorted(
                [
                    (
                        thumbnail_mae(
                            screenshot,
                            target,
                            node=node,
                            bounds=bounds,
                        ),
                        node,
                    )
                    for node in unique.values()
                ],
                key=lambda item: item[0],
            )
        if not scores:
            raise RuntimeError(f"{case.capability_id}: picker has no visible thumbnails")
        best_score, best = scores[0]
        second_score = scores[1][0] if len(scores) > 1 else 255.0
        maximum = float(recipe.effective.get("thumbnail_mae_max", 24.0))
        margin = float(recipe.effective.get("thumbnail_margin_min", 3.0))
        if require_confident and (
            best_score > maximum or second_score - best_score < margin
        ):
            raise RuntimeError(
                f"{case.capability_id}: requested asset image match is not exact enough: "
                f"best={best_score:.2f}, second={second_score:.2f}, asset={case.asset_id}"
            )
        screenshot_path.unlink(missing_ok=True)
        return best

    def _ensure_workspace(self, recipe: SamplingRecipe) -> tuple[AccessibilityNode, ...]:
        if recipe.strategy == "preset":
            return self._ensure_preset_collection(recipe)
        current = self.driver.snapshot()
        if recipe.strategy == "layer_asset_picker":
            current = self.ensure_layer_stack(current)
        tool_panel_open = any(
            node.identifier in {"ButtonTabsItem_Adjustments", "ButtonTabsItem_Masking"}
            for node in current
        )
        if self.driver.has_locator(recipe.locator_id, current) and not tool_panel_open:
            return current
        try:
            workspace_locator = WORKSPACE_LOCATORS[recipe.workspace]
        except KeyError as exc:
            raise RuntimeError(f"unsupported Luminar workspace: {recipe.workspace}") from exc
        if tool_panel_open and recipe.workspace != "catalog":
            self.driver.press(WORKSPACE_LOCATORS["catalog"])
            time.sleep(0.4)
        self.driver.press(workspace_locator)
        deadline = time.monotonic() + self.config.timeouts.action_seconds
        while time.monotonic() < deadline:
            current = self.driver.snapshot()
            if self.driver.has_locator(recipe.locator_id, current):
                return current
            time.sleep(0.25)
        current = self._find_tool_by_scrolling(recipe.locator_id)
        if current is not None:
            return current
        raise TimeoutError(
            f"Luminar workspace {recipe.workspace} did not expose {recipe.locator_id}"
        )

    def ensure_layer_stack(
        self, nodes: tuple[AccessibilityNode, ...]
    ) -> tuple[AccessibilityNode, ...]:
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        current = nodes
        while time.monotonic() < deadline:
            if self.driver.has_locator("overlaysView_addLayerItem", current):
                return current
            back = next(
                (
                    node
                    for node in current
                    if node.role == "AXButton"
                    and node.identifier in {"_NS:11", "_NS:16"}
                    and node.position is not None
                    and node.position[0] < 60
                    and node.position[1] < 110
                ),
                None,
            )
            if back is None:
                self.driver.press(WORKSPACE_LOCATORS["edit"])
            else:
                self.driver.press_at(back.index)
            time.sleep(0.25)
            current = self.driver.snapshot()
        raise TimeoutError("Luminar layer panel did not return to the layer stack")

    def _ensure_preset_collection(
        self, recipe: SamplingRecipe
    ) -> tuple[AccessibilityNode, ...]:
        category = recipe.effective.get("category")
        if not isinstance(category, str) or not category:
            raise RuntimeError("preset recipe requires a localized category")
        back = "NSButton.TemplateCollectionDetailViewController.BackButton"
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        retry_at = 0.0
        current = self.driver.snapshot()
        while time.monotonic() < deadline:
            if time.monotonic() >= retry_at:
                self.driver.press(WORKSPACE_LOCATORS["presets"])
                retry_at = time.monotonic() + 1.0
            current = self.driver.snapshot()
            if self.driver.has_locator("对于这张照片", current) or self.driver.has_locator(
                back, current
            ):
                break
            time.sleep(0.15)
        else:
            raise TimeoutError("Luminar did not open the presets workspace")
        if self.driver.has_locator(back, current):
            self.driver.ax_press(back)
            time.sleep(0.2)
        state = self.driver.state()
        raw_bounds = state.get("bounds")
        if not (
            isinstance(raw_bounds, list)
            and len(raw_bounds) == 4
            and all(isinstance(value, (int, float)) for value in raw_bounds)
        ):
            raise RuntimeError("Luminar preset workspace has no usable window bounds")
        x, y, width, height = (int(value) for value in raw_bounds)
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        while time.monotonic() < deadline:
            current = self.driver.snapshot()
            node = select_preset_category_node(current, category)
            if node is None or node.position is None:
                raise RuntimeError(f"Luminar preset category is absent: {category}")
            if y + 180 <= node.position[1] <= y + height - 140:
                self.driver.click_at(
                    node.position[0] + 55,
                    node.position[1] - 55,
                )
                break
            lines = (
                -self.config.panel_scroll_lines
                if node.position[1] > y + height - 140
                else self.config.panel_scroll_lines
            )
            self.driver.scroll_at(x + width - 228, y + height - 200, lines)
            time.sleep(0.15)
        else:
            raise TimeoutError(f"Luminar preset category is unavailable: {category}")
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        while time.monotonic() < deadline:
            current = self.driver.snapshot()
            if self.driver.has_locator(recipe.locator_id, current):
                return current
            time.sleep(0.2)
        raise TimeoutError(
            f"Luminar preset is unavailable: {category}/{recipe.locator_id}"
        )

    def _find_tool_by_scrolling(
        self, locator_id: str
    ) -> tuple[AccessibilityNode, ...] | None:
        state = self.driver.state()
        bounds = state.get("bounds")
        if not (
            isinstance(bounds, list)
            and len(bounds) == 4
            and all(isinstance(value, (int, float)) for value in bounds)
        ):
            return None
        x, y, width, height = (int(value) for value in bounds)
        panel_x = x + max(1, width - 140)
        panel_y = y + max(1, height // 2)
        directions = (1, -1)
        deadline = time.monotonic() + self.config.timeouts.action_seconds
        for direction in directions:
            for _ in range(self.config.panel_scroll_attempts):
                if time.monotonic() >= deadline:
                    return None
                self.driver.scroll_at(
                    panel_x,
                    panel_y,
                    direction * self.config.panel_scroll_lines,
                )
                time.sleep(0.1)
                current = self.driver.snapshot()
                if self.driver.has_locator(locator_id, current):
                    return current
        return None

    def _wait_for_stable_preview(
        self,
        layout: CaptureLayout,
        *,
        baseline_preview: Path,
        require_change: bool,
        change_mae_min: float | None = None,
        timeout_seconds: float | None = None,
        required_samples: int | None = None,
    ) -> tuple[list[Path], Path]:
        sample_requirement = (
            self.config.stable_samples
            if required_samples is None
            else required_samples
        )
        if sample_requirement < 1:
            raise ValueError("stable preview sample requirement must be positive")
        samples: deque[Path] = deque()
        preview_samples: deque[Path] = deque()
        sample_index = 0
        preview_available_deadline: float | None = None
        deadline = time.monotonic() + (
            self.config.timeouts.inference_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        while time.monotonic() < deadline:
            path = layout.staging_dir / f"stable-{sample_index:03d}.png"
            preview_path = layout.staging_dir / f"stable-preview-{sample_index:03d}.png"
            sample_index += 1
            try:
                self._screenshot(path)
                nodes = self.driver.snapshot()
                bounds = self._window_bounds()
                crop_native_preview(
                    path,
                    preview_path,
                    node=select_preview_node(nodes, bounds),
                    bounds=bounds,
                )
            except (RuntimeError, TimeoutError):
                path.unlink(missing_ok=True)
                preview_path.unlink(missing_ok=True)
                time.sleep(0.25)
                continue
            samples.append(path)
            preview_samples.append(preview_path)
            if preview_available_deadline is None:
                preview_available_deadline = min(
                    deadline,
                    time.monotonic() + self.config.timeouts.inference_seconds,
                )
            while len(samples) > sample_requirement:
                samples.popleft().unlink(missing_ok=True)
            while len(preview_samples) > sample_requirement:
                preview_samples.popleft().unlink(missing_ok=True)
            change_metrics = normalized_image_change_metrics(
                baseline_preview,
                preview_path,
                pixel_delta=self.config.change_pixel_delta_min,
            )
            changed = not require_change or (
                change_metrics["mae"]
                >= (
                    change_mae_min
                    if change_mae_min is not None
                    else self.config.preview_change_mae_min
                )
                or change_metrics["strong_changed_pixel_fraction"]
                >= self.config.change_pixel_fraction_min
            )
            stable = sample_requirement == 1 or stable_screenshot_sequence(
                preview_samples,
                required=sample_requirement,
                mae_max=self.config.screenshot_mae_max,
            )
            if stable and changed:
                kept_samples = list(samples)
                final_preview = preview_samples[-1]
                for stale in kept_samples[:-1]:
                    stale.unlink(missing_ok=True)
                for stale in list(preview_samples)[:-1]:
                    stale.unlink(missing_ok=True)
                return kept_samples, final_preview
            if (
                preview_available_deadline is not None
                and time.monotonic() >= preview_available_deadline
            ):
                raise AdvanceActivationCaptureError(
                    "Luminar preview is stable but the current activation did not "
                    "produce a measurable change"
                )
            time.sleep(min(0.75, self.config.timeouts.stable_seconds))
        raise TimeoutError("Luminar preview did not become available and stable")

    def _validate_rendered_effect(
        self,
        case: CaptureCase,
        *,
        layout: CaptureLayout,
        preview_path: Path,
        export_path: Path,
        require_change: bool,
        recipe: SamplingRecipe | None = None,
        attempt: int = 0,
        require_preview_export_match: bool = True,
    ) -> None:
        try:
            comparison_size = self.config.preview_export_comparison_size
            effective = recipe.effective if recipe is not None else {}
            preview_rgb_max = float(
                effective.get(
                    "preview_export_rgb_mae_max",
                    self.config.preview_export_rgb_mae_max,
                )
            )
            preview_luma_max = float(
                effective.get(
                    "preview_export_luma_mae_max",
                    self.config.preview_export_luma_mae_max,
                )
            )
            preview_export_rgb_mae = normalized_image_mae(
                preview_path,
                export_path,
                size=comparison_size,
            )
            preview_export_luma_mae = normalized_image_mae(
                preview_path,
                export_path,
                size=comparison_size,
                mode="L",
            )
            if require_preview_export_match and (
                preview_export_rgb_mae > preview_rgb_max
                or preview_export_luma_mae > preview_luma_max
            ):
                raise RuntimeError(
                    "Luminar native preview and export do not represent the same rendered "
                    f"effect: rgb_mae={preview_export_rgb_mae:.6f}, "
                    f"luma_mae={preview_export_luma_mae:.6f}, size={comparison_size}"
                )
            if not require_change:
                return
            change_metrics = normalized_image_change_metrics(
                case.input_path,
                export_path,
                pixel_delta=self.config.change_pixel_delta_min,
            )
            export_source_mae_min = float(
                effective.get(
                    "export_source_mae_min", self.config.export_source_mae_min
                )
            )
            change_pixel_fraction_min = float(
                effective.get(
                    "change_pixel_fraction_min",
                    self.config.change_pixel_fraction_min,
                )
            )
            if (
                change_metrics["mae"] < export_source_mae_min
                and change_metrics["strong_changed_pixel_fraction"]
                < change_pixel_fraction_min
            ):
                activation_controls = effective.get("activation_locator_ids")
                has_untried_activation = (
                    isinstance(activation_controls, list)
                    and attempt < len(activation_controls) - 1
                )
                error_type = (
                    AdvanceActivationCaptureError
                    if has_untried_activation
                    else NonRetryableCaptureError
                )
                raise error_type(
                    "Luminar exported the unchanged source for an effective sampling case: "
                    f"mae={change_metrics['mae']:.6f}, "
                    "strong_changed_pixel_fraction="
                    f"{change_metrics['strong_changed_pixel_fraction']:.6f}"
                )
        except Exception:
            rejected = layout.staging_dir / (
                f"rejected-export-attempt-{attempt}{export_path.suffix.lower()}"
            )
            export_path.replace(rejected)
            raise

    def _screenshot(self, path: Path) -> None:
        state = self.driver.state()
        window_id = state.get("window_id")
        bounds = self._window_bounds(state)
        self.controller.screenshot_window(
            path,
            window_id=window_id if isinstance(window_id, int) else None,
            bounds=bounds,
        )

    def _window_bounds(self, state: dict[str, Any] | None = None) -> WindowBounds:
        current = state or self.driver.state()
        raw_bounds = current.get("bounds")
        if not (
            isinstance(raw_bounds, list)
            and len(raw_bounds) == 4
            and all(isinstance(value, (int, float)) for value in raw_bounds)
        ):
            raise RuntimeError("Luminar accessibility state has no usable window bounds")
        return WindowBounds(*(int(value) for value in raw_bounds))

    @staticmethod
    def _write_result(layout: CaptureLayout, result: ToolProbeResult) -> None:
        path = layout.staging_dir / "auto-probe.json"
        path.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
