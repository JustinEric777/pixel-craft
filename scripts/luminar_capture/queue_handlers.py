"""Native handlers for every complete-queue sampling kind."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from configs.luminar_sampling import LuminarSamplingConfig, SamplingRecipe

from .accessibility_driver import LuminarAccessibilityDriver
from .app_controller import LuminarAppController, WindowBounds
from .auto_sampler import (
    WORKSPACE_LOCATORS,
    LuminarAutoSampler,
    NonRetryableCaptureError,
    ToolProbeResult,
    control_readback_matches,
    normalize_recipe_value,
    normalized_preview_stroke,
    select_preview_node,
    select_unique_control,
    slider_click_position,
)
from .case_reader import CaptureCase
from .layout import CaptureLayout
from .sampling_queue import SamplingKind, SamplingQueueRecord
from .stability import normalized_image_mae
from .state_machine import CaptureJournal, CaptureStatus
from .ui_evidence import sha256_file, ui_fixture_identity


@dataclass(frozen=True)
class MergeWorkflowSpec:
    capability_id: str
    menu_locator: str
    plugin_locator: str
    result_pattern: str
    launch_position: tuple[int, int]
    panel_scroll_lines: int = 0
    post_continue_locators: tuple[str, ...] = ()


MERGE_WORKFLOWS = {
    "hdr_merge": MergeWorkflowSpec(
        capability_id="hdr_merge",
        menu_locator="MPTopBarMergeMenuItem.HDRMerge",
        plugin_locator="HDR 合并",
        result_pattern=r"_HDR(?: \d+)?\.tiff$",
        # The merge action sits at the bottom of the native More panel in the
        # verified 1440x900 logical window (2880x1800 Retina capture).
        launch_position=(1033, 714),
    ),
    "focus_stacking": MergeWorkflowSpec(
        capability_id="focus_stacking",
        menu_locator="MPTopBarMergeMenuItem.FocusStacking",
        plugin_locator="焦点堆叠",
        result_pattern=r"_stack(?: \d+)?\.tiff$",
        launch_position=(1212, 854),
    ),
    "panorama_stitching": MergeWorkflowSpec(
        capability_id="panorama_stitching",
        menu_locator="MPTopBarMergeMenuItem.PanoramaStitching",
        plugin_locator="全景拼接",
        result_pattern=r"_PANORAMA(?: \d+)?\.tiff$",
        launch_position=(1212, 872),
        panel_scroll_lines=-10,
        post_continue_locators=("裁切", "保存"),
    ),
}
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DETAILS_SLIDER_LOCATOR = "Slider.MIPLDetailsEffect.Overall_Small_Detail.Slider"
BW_ACTIVATION_LOCATOR = "NSButton.MIPLBWChannels_v1_Effect.Apply"
BW_RED_SLIDER_LOCATOR = "Slider.MIPLBWChannels_v1_Effect.lRed.Slider"
DENOISE_LEVEL_LOCATOR = "NSButton.Noiseless.Mid"
DENOISE_SLIDER_LOCATOR = "Slider.MIPLDenoiseAIEffect.Luminosity Denoise.Slider"
SKY_PARAMETER_BINDINGS = {
    "horizon_offset": (
        "AdvancedSlider.NSButton.Sky Orientation",
        "Slider.MIPLSkyReplacementEffect.Horizon",
    ),
    "vertical_offset": (
        "AdvancedSlider.NSButton.Sky Orientation",
        "Slider.MIPLSkyReplacementEffect.Sky Vertical Offset",
    ),
    "horizontal_offset": (
        "AdvancedSlider.NSButton.Sky Orientation",
        "Slider.MIPLSkyReplacementEffect.Sky Horizontal Offset",
    ),
    "sky_flip": (
        "AdvancedSlider.NSButton.Sky Orientation",
        "NSButton.MIPLSkyReplacementEffect.SkyFlip",
    ),
    "edge_refinement": (
        "AdvancedSlider.NSButton.Mask Refinement",
        "Slider.MIPLSkyReplacementEffect.Sigma",
    ),
    "sky_global": (
        "AdvancedSlider.NSButton.Mask Refinement",
        "Slider.MIPLSkyReplacementEffect.SkyGlobal",
    ),
    "fix_gaps": (
        "AdvancedSlider.NSButton.Mask Refinement",
        "Slider.MIPLSkyReplacementEffect.FixGaps",
    ),
    "foreground_relight": (
        "AdvancedSlider.NSButton.Scene Relighting",
        "Slider.MIPLSkyReplacementEffect.Relighting",
    ),
    "relight_saturation": (
        "AdvancedSlider.NSButton.Scene Relighting",
        "Slider.MIPLSkyReplacementEffect.Relighting Saturation",
    ),
    "relight_human": (
        "AdvancedSlider.NSButton.Scene Relighting",
        "Slider.MIPLSkyReplacementEffect.Relight Human",
    ),
    "reflection_blur": (
        "AdvancedSlider.NSButton.Reflection",
        "Slider.MIPLSkyReplacementEffect.WaterBlur",
    ),
    "reflection_amount": (
        "AdvancedSlider.NSButton.Reflection",
        "Slider.MIPLSkyReplacementEffect.Water",
    ),
    "sky_grain": (
        "AdvancedSlider.NSButton.Sky Adjustments",
        "Slider.MIPLSkyReplacementEffect.Sky Grain",
    ),
    "sky_blur": (
        "AdvancedSlider.NSButton.Sky Adjustments",
        "Slider.MIPLSkyReplacementEffect.SkyBlur",
    ),
    "atmospheric_haze": (
        "AdvancedSlider.NSButton.Sky Adjustments",
        "Slider.MIPLSkyReplacementEffect.White",
    ),
    "temperature": (
        "AdvancedSlider.NSButton.Sky Adjustments",
        "Slider.MIPLSkyReplacementEffect.Temperature",
    ),
    "brightness": (
        "AdvancedSlider.NSButton.Sky Adjustments",
        "Slider.MIPLSkyReplacementEffect.SkyExposure",
    ),
}
MUTATING_UI_WORKSPACES = {
    "layer-stack",
    "edit-history",
    "black-white-after-conversion",
    "denoise-level-selected",
    "export-dialog",
    "multi-image-complete",
}


class LuminarQueueHandlers:
    """Bind queue records to verified accessibility operations.

    Missing native locators are explicit failures. A queue item is never marked ready
    merely because the application opened or a visually similar item was selected.
    """

    def __init__(
        self,
        config: LuminarSamplingConfig,
        controller: LuminarAppController,
        driver: LuminarAccessibilityDriver,
        *,
        reference_id: str,
        app_version: dict[str, str],
        ui_reference_root: Path,
    ) -> None:
        self.config = config
        self.controller = controller
        self.driver = driver
        self.ui_reference_root = ui_reference_root
        self.reference_id = reference_id
        self.app_version = dict(app_version)
        self.sampler = LuminarAutoSampler(
            config,
            controller,
            driver,
            reference_build=reference_id,
            app_version=app_version,
        )
        self._ui_selected_input_sha256: str | None = None
        self._ui_photo_clean = False
        self._ui_last_prepare_reused = False
        self._ui_parameter_evidence: dict[str, object] | None = None
        binding_path = (
            Path(__file__).resolve().parents[2]
            / "configs/parity/native-parameter-bindings.json"
        )
        if not binding_path.is_file():
            raise FileNotFoundError(
                f"native parameter binding audit is missing: {binding_path}"
            )
        binding_payload = json.loads(binding_path.read_text(encoding="utf-8"))
        self._native_parameter_binding_reference_id = str(
            binding_payload.get("reference_id") or ""
        )
        raw_bindings = binding_payload.get("records")
        if not isinstance(raw_bindings, list):
            raise TypeError("native parameter binding audit has no records")
        self._native_parameter_bindings = (
            {str(item["matrix_state_id"]): item for item in raw_bindings}
            if self._native_parameter_binding_reference_id == reference_id
            else {}
        )
        queue_path = (
            self.ui_reference_root.parent / "diagnostics/sampling-queue.json"
        )
        self._sampling_queue_payload = json.loads(
            queue_path.read_text(encoding="utf-8")
        )

    def mapping(self):
        return {
            SamplingKind.UI: self.ui,
            SamplingKind.EFFECT: self.effect,
            SamplingKind.PRESET: self.preset,
            SamplingKind.SKY: self.sky,
            SamplingKind.OVERLAY: self.overlay,
            SamplingKind.WORKFLOW: self.workflow,
        }

    def prepare_observation_photo(self, source: dict[str, object]) -> None:
        """Prepare the frozen UI fixture for an interaction observation."""

        self.controller.launch(timeout_seconds=self.config.timeouts.action_seconds)
        self.driver.activate()
        self.controller.enter_full_screen(
            timeout_seconds=self.config.timeouts.navigation_seconds
        )
        self._prepare_ui_photo(source)

    def apply_parameter_observation(
        self,
        record: SamplingQueueRecord,
        layout: CaptureLayout,
    ) -> tuple[object, dict[str, object]]:
        """Apply one audited parameter binding and return its verified readback."""

        if record.payload.get("matrix_kind") != "tool-parameter-state":
            raise ValueError("parameter observation requires a tool-parameter-state record")
        self._ui_parameter_evidence = None
        nodes = self._prepare_matrix_ui_state(
            record,
            str(record.payload["workspace_state"]),
            "tool-parameter-state",
            layout=layout,
            prefer_pointer_input=True,
        )
        evidence = self._ui_parameter_evidence
        if not isinstance(evidence, dict) or evidence.get("readback_verified") is not True:
            raise RuntimeError(
                f"native parameter readback was not verified: {record.payload['matrix_state_id']}"
            )
        return nodes, dict(evidence)

    def effect(self, record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        capability_id = str(record.payload["capability_id"])
        recipe = self.config.recipe_for(capability_id)
        parameter_binding = record.payload.get("parameter_binding")
        if parameter_binding is not None:
            if not isinstance(parameter_binding, dict):
                raise RuntimeError(
                    f"invalid exact parameter binding for {record.record_id}"
                )
            parameter = str(parameter_binding.get("parameter") or "")
            if capability_id == "sky_replace" and parameter == "asset_id":
                if (
                    parameter_binding.get("value_space") != "asset-id"
                    or not isinstance(parameter_binding.get("value"), str)
                    or parameter_binding.get("value") != record.payload.get("asset_id")
                ):
                    raise RuntimeError(
                        f"invalid sky asset binding for {record.record_id}"
                    )
                effective = {
                    **recipe.effective,
                    "parameter_binding": parameter_binding,
                    "preview_change_mae_min": self.config.screenshot_mae_max,
                }
            elif parameter == "amount":
                if not isinstance(parameter_binding.get("value"), (int, float)):
                    raise RuntimeError(
                        f"invalid exact amount binding for {record.record_id}"
                    )
                if parameter_binding.get("value_space") != "normalized-signed":
                    raise RuntimeError(
                        f"invalid exact parameter binding for {record.record_id}"
                    )
                effective = {
                    **recipe.effective,
                    "value": float(parameter_binding["value"]),
                    "value_space": parameter_binding["value_space"],
                    "parameter_binding": parameter_binding,
                    "preview_change_mae_min": self.config.screenshot_mae_max,
                }
            elif capability_id == "sky_replace" and parameter in SKY_PARAMETER_BINDINGS:
                section_locator, control_locator = SKY_PARAMETER_BINDINGS[parameter]
                if (
                    parameter_binding.get("value_space") != "native"
                    or not isinstance(parameter_binding.get("value"), (bool, int, float))
                ):
                    raise RuntimeError(
                        f"sky parameter binding must use native value space: {record.record_id}"
                    )
                effective = {
                    **recipe.effective,
                    "parameter_section_locator_id": section_locator,
                    "parameter_control_locator_id": control_locator,
                    "parameter_value": parameter_binding["value"],
                    "parameter_binding": parameter_binding,
                    "preview_change_mae_min": self.config.screenshot_mae_max,
                }
            else:
                raise RuntimeError(
                    f"unsupported exact parameter binding for {record.record_id}: {parameter}"
                )
            recipe = SamplingRecipe(
                capability_id=recipe.capability_id,
                workspace=recipe.workspace,
                locator_id=recipe.locator_id,
                strategy=recipe.strategy,
                default_capture=recipe.default_capture,
                effective=effective,
            )
        if "asset_index" in record.payload and "asset_count" in record.payload:
            recipe = SamplingRecipe(
                capability_id=recipe.capability_id,
                workspace=recipe.workspace,
                locator_id=recipe.locator_id,
                strategy=recipe.strategy,
                default_capture=recipe.default_capture,
                effective={
                    **recipe.effective,
                    "asset_index": record.payload["asset_index"],
                    "asset_count": record.payload["asset_count"],
                },
            )
        self._require_ready(
            self.sampler.probe(
                record.to_capture_case(),
                layout,
                recipe,
            )
        )

    def preset(self, record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        name = str(record.payload.get("localized_name") or record.payload["name"])
        category = str(
            record.payload.get("localized_category") or record.payload["category"]
        )
        recipe = SamplingRecipe(
            capability_id="preset_apply",
            workspace="presets",
            locator_id=name,
            strategy="preset",
            default_capture=True,
            effective={"category": category},
        )
        self._require_ready(
            self.sampler.probe(record.to_capture_case(), layout, recipe)
        )

    def sky(self, record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        base_recipe = self.config.recipe_for("sky_replace")
        recipe = SamplingRecipe(
            capability_id=base_recipe.capability_id,
            workspace=base_recipe.workspace,
            locator_id=base_recipe.locator_id,
            strategy=base_recipe.strategy,
            default_capture=base_recipe.default_capture,
            effective={
                **base_recipe.effective,
                "asset_index": record.payload["asset_index"],
                "asset_count": record.payload["asset_count"],
            },
        )
        self._require_ready(
            self.sampler.probe(
                record.to_capture_case(),
                layout,
                recipe,
            )
        )

    @staticmethod
    def _require_ready(result: ToolProbeResult) -> None:
        if result.status != "ready":
            raise RuntimeError(result.error or f"native sampling failed: {result.case_id}")

    def overlay(self, record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        category = str(record.payload.get("localized_category") or "")
        recipe = SamplingRecipe(
            capability_id="overlay_apply",
            workspace="edit",
            locator_id="overlaysView_addLayerItem",
            strategy="layer_asset_picker",
            default_capture=True,
            effective={
                "category": category,
                "asset_index": record.payload["asset_index"],
                "thumbnail_mae_max": self.config.overlay_thumbnail_mae_max,
                "thumbnail_mae_hard_max": (
                    self.config.overlay_thumbnail_mae_hard_max
                ),
                "thumbnail_margin_min": self.config.overlay_thumbnail_margin_min,
            },
        )
        self._require_ready(
            self.sampler.probe(record.to_capture_case(), layout, recipe)
        )

    def workflow(self, record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        capability_id = str(record.payload["capability_id"])
        spec = MERGE_WORKFLOWS.get(capability_id)
        if spec is None:
            raise RuntimeError(
                "native workflow execution is not yet verified for this workflow; "
                f"remaining locator calibration is required for {record.record_id}"
            )
        self._capture_merge_workflow(record, layout, spec)

    def _capture_merge_workflow(
        self,
        record: SamplingQueueRecord,
        layout: CaptureLayout,
        spec: MergeWorkflowSpec,
    ) -> None:
        raw_inputs = list(record.payload["inputs"])
        input_paths = [Path(str(item["path"])).resolve() for item in raw_inputs]
        folder = input_paths[0].parent
        if any(path.parent != folder for path in input_paths):
            raise RuntimeError(
                f"{spec.capability_id} inputs must share one import folder"
            )
        journal = CaptureJournal(layout)
        layout.prepare()
        self.controller.launch(timeout_seconds=self.config.timeouts.action_seconds)
        self.driver.activate()
        self.controller.enter_full_screen(
            timeout_seconds=self.config.timeouts.navigation_seconds
        )
        result_name = re.compile(spec.result_pattern, re.IGNORECASE)
        current_nodes = self.driver.snapshot()
        if self._workflow_was_started(
            journal, spec.capability_id, input_paths, raw_inputs
        ) and self._has_result_title(current_nodes, result_name):
            self._finalize_workflow_result(
                record,
                layout,
                journal,
                raw_inputs,
                input_paths,
                spec.capability_id,
            )
            return
        for _ in range(3):
            self.driver.cancel()
            time.sleep(0.1)
        self._select_multi_image_inputs(input_paths)
        self.driver.press("MPTopBarMergeButton")
        self.driver.ax_press(spec.menu_locator)
        time.sleep(1.0)
        if spec.panel_scroll_lines:
            self.driver.scroll_at(1212, 780, spec.panel_scroll_lines)
            time.sleep(0.5)
        launcher_nodes = self.driver.snapshot()
        self.driver.write_snapshot(layout.staging_before_ax_path, launcher_nodes)
        self._screenshot_window(layout.staging_before_path)
        journal.transition(
            CaptureStatus.TOOL_OPENED,
            workflow=spec.capability_id,
            inputs=[str(path) for path in input_paths],
            input_sha256s=[str(item["sha256"]) for item in raw_inputs],
            completion="pending-native-launch",
        )
        self.driver.click_at(*spec.launch_position)
        deadline = time.monotonic() + self.config.timeouts.action_seconds
        plugin_nodes = None
        while time.monotonic() < deadline:
            nodes = self.driver.snapshot()
            if self.driver.has_locator(spec.plugin_locator, nodes):
                plugin_nodes = nodes
                break
            if self._has_result_title(nodes, result_name):
                break
            time.sleep(0.2)
        else:
            raise TimeoutError(
                f"Luminar did not open {spec.plugin_locator} or expose its result"
            )
        if plugin_nodes is not None:
            self.driver.ax_press("继续")
            journal.transition(
                CaptureStatus.EFFECT_APPLIED,
                workflow=spec.capability_id,
                completion="pending-native-result",
            )
        result_ready = False
        for locator in spec.post_continue_locators:
            deadline = (
                time.monotonic() + self.config.timeouts.heavy_inference_seconds
            )
            while time.monotonic() < deadline:
                result_nodes = self.driver.snapshot()
                if self._has_result_title(result_nodes, result_name):
                    result_ready = True
                    break
                if self.driver.has_locator(locator, result_nodes):
                    self.driver.ax_press(locator)
                    break
                time.sleep(0.5)
            else:
                raise TimeoutError(
                    f"Luminar {spec.plugin_locator} did not expose {locator}"
                )
            if result_ready:
                break
        deadline = time.monotonic() + self.config.timeouts.heavy_inference_seconds
        while time.monotonic() < deadline:
            result_nodes = self.driver.snapshot()
            if self._has_result_title(result_nodes, result_name):
                break
            time.sleep(0.5)
        else:
            raise TimeoutError(
                f"Luminar {spec.plugin_locator} did not create its TIFF result"
            )
        self._finalize_workflow_result(
            record,
            layout,
            journal,
            raw_inputs,
            input_paths,
            spec.capability_id,
        )

    def _select_multi_image_inputs(self, input_paths: list[Path]):
        folder = input_paths[0].parent
        if any(path.parent != folder for path in input_paths):
            raise RuntimeError("multi-image inputs must share one import folder")
        self.driver.press(WORKSPACE_LOCATORS["catalog"])
        nodes = self.driver.snapshot()
        if not self.driver.has_locator(folder.name, nodes):
            self.controller.open_add_images_folder_dialog()
            self._wait_for_locator("OKButton")
            path_nodes = self._open_go_to_folder_field()
            field = next(
                node
                for node in path_nodes
                if node.identifier == "PathTextField"
                or (node.role == "AXTextField" and node.focused is True)
            )
            self.driver.set_value_at(field.index, str(folder))
            self.driver.confirm()
            self._wait_for_locator("OKButton")
            self.driver.ax_press("OKButton")
            self._wait_for_locator(folder.name)
        self.driver.press(folder.name)
        filename_nodes = self._wait_for_filenames(input_paths)
        current = self.driver.snapshot()
        if self.driver.has_locator("MPTopBarDeselectButton", current):
            self.driver.ax_press("MPTopBarDeselectButton")
        for index, path in enumerate(input_paths):
            label = filename_nodes[path.stem]
            assert label.position and label.size
            x = label.position[0] + label.size[0] // 2
            y = label.position[1] + 100
            if index == 0:
                self.driver.click_at(x, y)
            else:
                self.driver.command_click_at(x, y)
        selected = self._wait_for_locator("MPTopBarMergeButton")
        if not self.driver.has_locator(f"{len(input_paths)} Photos", selected):
            selected = self._wait_for_locator(f"{len(input_paths)} Photos")
        selected_names = {
            str(node.value)
            for node in selected
            if node.identifier == "MPInstrumentInfoViewControllerFileName"
        }
        if not {path.stem for path in input_paths} <= selected_names:
            raise RuntimeError(
                "Luminar multi-image selection does not contain every input"
            )
        return selected

    def _finalize_workflow_result(
        self,
        record: SamplingQueueRecord,
        layout: CaptureLayout,
        journal: CaptureJournal,
        raw_inputs: list[dict[str, object]],
        input_paths: list[Path],
        capability_id: str,
    ) -> None:
        nodes = self.driver.snapshot()
        if self.driver.has_locator("单图视图", nodes):
            self.driver.press("单图视图")
        self._wait_for_locator("PreviewImage")
        first = raw_inputs[0]
        capture_case = CaptureCase(
            case_id=record.capture_id,
            capability_id=capability_id,
            input_path=input_paths[0],
            input_sha256=str(first["sha256"]),
            parameters={"inputs": raw_inputs, "defaults": True},
            asset_id=None,
        )
        self.sampler.finalize_current_result(capture_case, layout, journal)

    def _open_go_to_folder_field(self):
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        while time.monotonic() < deadline:
            self.driver.open_go_to_folder()
            retry_at = min(deadline, time.monotonic() + 1.0)
            while time.monotonic() < retry_at:
                nodes = self.driver.snapshot()
                if any(
                    node.identifier == "PathTextField"
                    or (node.role == "AXTextField" and node.focused is True)
                    for node in nodes
                ):
                    return nodes
                time.sleep(0.15)
        raise TimeoutError("Luminar Go to Folder field did not become focused")

    @staticmethod
    def _has_result_title(nodes, pattern: re.Pattern[str]) -> bool:
        return any(
            pattern.search(str(value))
            for node in nodes
            for value in (node.title, node.value, node.description, node.help)
            if value is not None
        )

    @staticmethod
    def _workflow_was_started(
        journal: CaptureJournal,
        workflow: str,
        input_paths: list[Path],
        raw_inputs: list[dict[str, object]],
    ) -> bool:
        expected = [str(path) for path in input_paths]
        expected_hashes = [str(item["sha256"]) for item in raw_inputs]
        return any(
            item.get("workflow") == workflow
            and item.get("inputs") == expected
            and item.get("input_sha256s") == expected_hashes
            and item.get("status") == CaptureStatus.TOOL_OPENED
            for item in journal.events()
        )

    def _wait_for_locator(
        self, locator: str, *, timeout_seconds: float | None = None
    ):
        deadline = time.monotonic() + (
            timeout_seconds or self.config.timeouts.navigation_seconds
        )
        while time.monotonic() < deadline:
            nodes = self.driver.snapshot()
            if self.driver.has_locator(locator, nodes):
                return nodes
            time.sleep(0.2)
        raise TimeoutError(f"Luminar did not expose required locator: {locator}")

    def _wait_for_filenames(self, paths: list[Path]):
        expected = {path.stem for path in paths}
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        while time.monotonic() < deadline:
            nodes = self.driver.snapshot()
            labels = {
                str(node.value): node
                for node in nodes
                if node.identifier == "MPInstrumentInfoViewControllerFileName"
                and node.value is not None
            }
            if expected <= set(labels):
                return {name: labels[name] for name in expected}
            time.sleep(0.2)
        raise TimeoutError(f"Luminar did not expose workflow inputs: {sorted(expected)}")

    def ui(self, record: SamplingQueueRecord, layout: CaptureLayout) -> None:
        state = str(record.payload["matrix_state_id"])
        workspace = str(record.payload["workspace_state"])
        matrix_kind = str(record.payload["matrix_kind"])
        width, height = (int(value) for value in record.payload["viewport"])
        self.controller.launch(timeout_seconds=self.config.timeouts.action_seconds)
        self.driver.activate()
        layout.prepare()
        self.controller.enter_full_screen(
            timeout_seconds=self.config.timeouts.navigation_seconds
        )
        raw_input = record.payload.get("input")
        if isinstance(raw_input, dict):
            binding = self._native_parameter_bindings.get(
                str(record.payload.get("matrix_state_id") or ""), {}
            )
            native = binding.get("native") if isinstance(binding, dict) else None
            preserve_native_state = (
                isinstance(native, dict)
                and native.get("kind") == "semantic-readback"
            )
            self._prepare_ui_photo(
                raw_input, preserve_transient_state=preserve_native_state
            )
        self._ui_parameter_evidence = None
        nodes = self._prepare_matrix_ui_state(
            record, workspace, matrix_kind, layout=layout
        )
        destination = self.ui_reference_root / f"{width}x{height}" / f"{state}.png"
        ax_destination = destination.with_suffix(".ax.json")
        self._screenshot_window(destination)
        with Image.open(destination) as image:
            actual_size = image.size
        if actual_size != (width, height):
            raise RuntimeError(
                "Luminar screenshot did not reach requested pixel viewport: "
                f"{actual_size[0]}x{actual_size[1]} != {width}x{height}"
            )
        self.driver.write_snapshot(ax_destination, nodes)
        fixture_id, fixture_hash = ui_fixture_identity(record, self.config)
        CaptureJournal(layout).transition(
            CaptureStatus.READY,
            reference_id=self.reference_id,
            app_version=self.app_version,
            screenshot=str(destination),
            screenshot_sha256=sha256_file(destination),
            accessibility_tree=str(ax_destination),
            accessibility_tree_sha256=sha256_file(ax_destination),
            viewport=[width, height],
            ui_state=state,
            matrix_state_id=state,
            matrix_fingerprint=record.payload["matrix_fingerprint"],
            fixture_id=fixture_id,
            fixture_hash=fixture_hash,
            reused_selected_input=self._ui_last_prepare_reused,
            parameter_evidence=self._ui_parameter_evidence,
        )
        if matrix_kind == "tool-parameter-state" or workspace in MUTATING_UI_WORKSPACES:
            self._ui_photo_clean = False
        if matrix_kind == "tool-parameter-state":
            # Preserve the expanded native panel in the captured reference, then
            # close it before the next record.  Luminar keeps Restore Original
            # disabled while some canvas tools (notably Erase) remain expanded.
            self.driver.cancel()
            capability_id = str(record.payload.get("capability_id") or "")
            recipe = self.config.recipes.get(capability_id)
            if recipe is not None and self.driver.has_locator(recipe.locator_id):
                self.driver.press(recipe.locator_id)
        if workspace == "export-dialog":
            self.driver.cancel()
            self._wait_for_locator_absent("saveAsNameTextField")

    def _prepare_matrix_ui_state(
        self,
        record: SamplingQueueRecord,
        workspace: str,
        matrix_kind: str,
        *,
        layout: CaptureLayout,
        prefer_pointer_input: bool = False,
    ):
        if matrix_kind == "workspace-state":
            if workspace not in self.config.ui_states:
                raise RuntimeError(
                    f"native workspace transition for {workspace!r} is not configured"
                )
            return self._prepare_ui_state(workspace)
        if matrix_kind not in {"tool-panel-state", "tool-parameter-state"}:
            raise RuntimeError(f"unsupported current UI matrix kind: {matrix_kind!r}")
        capability_id = str(record.payload.get("capability_id") or "")
        recipe = self.config.recipes.get(capability_id)
        if recipe is None:
            raise RuntimeError(
                f"native UI recipe is missing for current capability {capability_id!r}"
            )
        binding = self._native_parameter_bindings.get(
            str(record.payload.get("matrix_state_id") or ""), {}
        )
        native = binding.get("native") if isinstance(binding, dict) else None
        if isinstance(native, dict) and native.get("kind") == "semantic-readback":
            control = native.get("control_locator_id")
            current = self.driver.snapshot()
            if isinstance(control, str) and self.driver.has_locator(control, current):
                readback = next(
                    node
                    for node in current
                    if any(
                        value == control
                        for value in (
                            node.identifier,
                            node.title,
                            node.description,
                            node.help,
                            node.value,
                        )
                    )
                )
                self._ui_parameter_evidence = {
                    "binding_status": "supported",
                    "kind": "semantic-readback",
                    "control_locator_id": control,
                    "requested_value": native.get("value"),
                    "readback": {
                        "identifier": readback.identifier,
                        "title": readback.title,
                        "value": readback.value,
                    },
                    "readback_verified": True,
                }
                return current
        self.driver.press(WORKSPACE_LOCATORS["catalog"])
        time.sleep(0.3)
        self.driver.press(WORKSPACE_LOCATORS["edit"])
        nodes = self.sampler.ensure_layer_stack(self.driver.snapshot())
        if matrix_kind == "tool-panel-state":
            panel_state = str(record.payload.get("panel_state") or "")
            if panel_state == "collapsed":
                if not self.driver.has_locator(recipe.locator_id, nodes):
                    nodes = self.sampler._find_tool_by_scrolling(recipe.locator_id)
                if nodes is not None and self.driver.has_locator(
                    recipe.locator_id, nodes
                ):
                    return nodes
                raise RuntimeError(
                    f"native collapsed tool is not visible: {capability_id!r}"
                )
            if panel_state == "expanded":
                return self._open_tool(recipe.locator_id)
            raise RuntimeError(f"unsupported tool panel state: {panel_state!r}")
        return self._apply_native_parameter_state(
            record,
            recipe,
            layout,
            prefer_pointer_input=prefer_pointer_input,
        )

    def _apply_native_parameter_state(
        self,
        record: SamplingQueueRecord,
        recipe: SamplingRecipe,
        layout: CaptureLayout,
        *,
        prefer_pointer_input: bool = False,
    ):
        if self._native_parameter_binding_reference_id != self.reference_id:
            raise RuntimeError(
                "native parameter binding reference mismatch: "
                f"{self._native_parameter_binding_reference_id!r} != "
                f"{self.reference_id!r}"
            )
        state_id = str(record.payload["matrix_state_id"])
        binding = self._native_parameter_bindings.get(state_id)
        if binding is None:
            raise RuntimeError(f"native parameter audit has no binding: {state_id}")
        if binding.get("status") != "supported":
            raise RuntimeError(
                f"native parameter is {binding.get('status')}: {state_id}: "
                f"{binding.get('reason')}"
            )
        native = binding.get("native")
        if not isinstance(native, dict):
            raise TypeError(f"native parameter binding is empty: {state_id}")
        nodes = self._open_tool(recipe.locator_id)
        activation = native.get("activation_locator_id")
        if isinstance(activation, str) and activation:
            if not self.driver.has_locator(activation, nodes):
                raise RuntimeError(
                    f"native parameter activation is absent: {state_id}: {activation}"
                )
            self.driver.press(activation)
            nodes = self.driver.snapshot()
        section = native.get("section_locator_id")
        control = native.get("control_locator_id")
        if (
            isinstance(section, str)
            and section
            and isinstance(control, str)
            and control
            and not self.driver.has_locator(control, nodes)
        ):
            if not self.driver.has_locator(section, nodes):
                raise RuntimeError(
                    f"native parameter section is absent: {state_id}: {section}"
                )
            self.driver.press(section)
            nodes = self.driver.snapshot()
        prerequisite_control = native.get("prerequisite_control_locator_id")
        if isinstance(prerequisite_control, str) and prerequisite_control:
            if not self.driver.has_locator(prerequisite_control, nodes):
                raise RuntimeError(
                    f"native prerequisite control is absent: {state_id}: "
                    f"{prerequisite_control}"
                )
            self.driver.press(prerequisite_control)
            nodes = self.driver.snapshot()

        kind = str(native.get("kind") or "")
        prerequisite = native.get("prerequisite")
        if prerequisite in {
            "select-first-local-sky",
            "select-first-local-reference",
        }:
            nodes = self._select_parameter_asset(
                record, recipe, nodes, layout
            )[0]
            if kind == "slider":
                self.driver.cancel()
                nodes = self.driver.snapshot()
        elif prerequisite is not None:
            raise RuntimeError(
                f"native parameter prerequisite is not implemented: {state_id}: "
                f"{prerequisite}"
            )
        if kind == "slider":
            if not isinstance(control, str) or not control:
                raise RuntimeError(f"native slider locator is missing: {state_id}")
            slider = select_unique_control(nodes, control)
            requested = native.get("value")
            if not isinstance(requested, (int, float)):
                raise RuntimeError(f"native slider value is invalid: {state_id}")
            value_space = native.get("value_space")
            effective = normalize_recipe_value(
                slider,
                float(requested),
                value_space=(str(value_space) if value_space == "normalized-signed" else None),
            )
            if prefer_pointer_input:
                click_x, click_y = slider_click_position(slider, effective)
                self.driver.click_at(click_x, click_y)
            else:
                observed = self.driver.set_value_at(slider.index, effective)
                if not isinstance(observed, (int, float)) or not math.isclose(
                    float(observed), effective, abs_tol=0.5
                ):
                    click_x, click_y = slider_click_position(slider, effective)
                    self.driver.click_at(click_x, click_y)
            readback_nodes = self.sampler._wait_for_control_readback(control, effective)
            readback = select_unique_control(readback_nodes, control)
            self._ui_parameter_evidence = {
                "binding_status": "supported",
                "kind": kind,
                "control_locator_id": control,
                "requested_value": requested,
                "effective_native_value": effective,
                "readback_value": readback.value,
                "readback_verified": control_readback_matches(readback, effective),
            }
            return readback_nodes

        if kind == "semantic-readback":
            if not isinstance(control, str) or not control:
                raise RuntimeError(f"native readback control is missing: {state_id}")
            matches = [
                node
                for node in nodes
                if any(
                    value == control
                    for value in (
                        node.identifier,
                        node.title,
                        node.description,
                        node.help,
                        node.value,
                    )
                )
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"native semantic readback {control!r} resolved to "
                    f"{len(matches)} controls: {state_id}"
                )
            readback = matches[0]
            self._ui_parameter_evidence = {
                "binding_status": "supported",
                "kind": kind,
                "control_locator_id": control,
                "requested_value": native.get("value"),
                "readback": {
                    "identifier": readback.identifier,
                    "title": readback.title,
                    "value": readback.value,
                },
                "readback_verified": True,
            }
            return nodes

        if kind == "menu-choice":
            if not isinstance(control, str) or not control:
                raise RuntimeError(f"native menu control is missing: {state_id}")
            choice_title = native.get("choice_title")
            if not isinstance(choice_title, str) or not choice_title:
                raise RuntimeError(f"native menu choice is missing: {state_id}")
            before_matches = [
                node
                for node in nodes
                if any(
                    value == control
                    for value in (
                    node.identifier,
                    node.title,
                    node.description,
                    node.help,
                    node.value,
                    )
                )
            ]
            if len(before_matches) != 1:
                raise RuntimeError(
                    f"native menu parent {control!r} resolved to "
                    f"{len(before_matches)} controls: {state_id}"
                )
            before = before_matches[0]
            selection = self.driver.select_menu_item(control, choice_title)
            after_nodes = self.driver.snapshot()
            after_matches = [
                node
                for node in after_nodes
                if any(
                    value == choice_title
                    for value in (
                    node.identifier,
                    node.title,
                    node.description,
                    node.help,
                    node.value,
                    )
                )
            ]
            if len(after_matches) != 1:
                raise RuntimeError(
                    f"native menu readback {choice_title!r} resolved to "
                    f"{len(after_matches)} controls: {state_id}"
                )
            after = after_matches[0]
            readback_verified = control_readback_matches(after, choice_title)
            if not readback_verified:
                raise RuntimeError(
                    f"native menu choice readback failed: {state_id}: "
                    f"{after.title!r}"
                )
            self._ui_parameter_evidence = {
                "binding_status": "supported",
                "kind": kind,
                "control_locator_id": control,
                "choice_title": choice_title,
                "requested_value": native.get("value"),
                "selection": selection,
                "before": {"title": before.title, "value": before.value},
                "after": {"title": after.title, "value": after.value},
                "readback_verified": True,
            }
            return after_nodes

        if kind == "button":
            if not isinstance(control, str) or not control:
                raise RuntimeError(f"native button locator is missing: {state_id}")
            before = select_unique_control(nodes, control)
            visual_before = layout.staging_dir / "parameter-button-before.png"
            visual_after = layout.staging_dir / "parameter-button-after.png"
            self._screenshot_window(visual_before)
            self.driver.press(control)
            after_nodes = self.driver.snapshot()
            self._screenshot_window(visual_after)
            after = select_unique_control(after_nodes, control)
            changed = any(
                left != right
                for left, right in (
                    (before.selected, after.selected),
                    (before.value, after.value),
                    (before.title, after.title),
                )
            )
            crop_apply_enabled = any(
                node.identifier == "NSButton.Crop.Apply" and node.enabled is True
                for node in after_nodes
            )
            visual_mae = normalized_image_mae(
                visual_before,
                visual_after,
                size=256,
            )
            if (
                not changed
                and not crop_apply_enabled
                and visual_mae <= self.config.screenshot_mae_max
            ):
                edit_state = self.sampler._verify_photo_has_edits()
                after_nodes = self.driver.snapshot()
            else:
                edit_state = None
            self._ui_parameter_evidence = {
                "binding_status": "supported",
                "kind": kind,
                "control_locator_id": control,
                "requested_value": native.get("value"),
                "before": {"value": before.value, "selected": before.selected},
                "after": {"value": after.value, "selected": after.selected},
                "visual_mae": visual_mae,
                "readback_verified": (
                    changed
                    or crop_apply_enabled
                    or visual_mae > self.config.screenshot_mae_max
                    or bool(edit_state)
                ),
                "edit_state": edit_state,
            }
            return after_nodes

        if kind == "asset-picker":
            after_nodes, asset_evidence = self._select_parameter_asset(
                record, recipe, nodes, layout
            )
            self._ui_parameter_evidence = {
                "binding_status": "supported",
                "kind": kind,
                **asset_evidence,
                "readback_verified": True,
            }
            return after_nodes

        if kind == "crop-box":
            raw_drag = native.get("drag")
            if (
                not isinstance(raw_drag, list)
                or len(raw_drag) != 4
                or not all(isinstance(value, (int, float)) for value in raw_drag)
            ):
                raise RuntimeError(f"native crop drag is invalid: {state_id}")
            preview = select_preview_node(nodes, self.sampler._window_bounds())
            if preview is None:
                raise RuntimeError(f"native crop preview is absent: {state_id}")
            start_x, start_y, end_x, end_y = normalized_preview_stroke(
                preview, raw_drag
            )
            self.driver.drag_at(start_x, start_y, end_x, end_y)
            time.sleep(0.5)
            after_nodes = self.driver.snapshot()
            apply_locator = str(native.get("apply_locator_id") or "")
            apply = next(
                (
                    node
                    for node in after_nodes
                    if node.identifier == apply_locator and node.enabled is True
                ),
                None,
            )
            used_guarded_canvas_fallback = False
            if apply is None and self.driver.low_interference:
                self.driver.guarded_canvas_drag_at(
                    start_x, start_y, end_x, end_y
                )
                time.sleep(0.5)
                after_nodes = self.driver.snapshot()
                apply = next(
                    (
                        node
                        for node in after_nodes
                        if node.identifier == apply_locator and node.enabled is True
                    ),
                    None,
                )
                used_guarded_canvas_fallback = True
            if apply is None:
                raise RuntimeError(
                    f"native crop drag did not enable apply control: {state_id}"
                )
            self._ui_parameter_evidence = {
                "binding_status": "supported",
                "kind": kind,
                "normalized_drag": raw_drag,
                "native_drag": [start_x, start_y, end_x, end_y],
                "apply_locator_id": apply_locator,
                "apply_enabled": True,
                "guarded_canvas_fallback": used_guarded_canvas_fallback,
                "readback_verified": True,
            }
            return after_nodes

        if kind == "stroke":
            raw_stroke = native.get("stroke")
            raw_source = native.get("source")
            apply_locator = native.get("apply_locator_id")
            preview = select_preview_node(nodes, self.sampler._window_bounds())
            if preview is None:
                raise RuntimeError(f"native stroke preview is absent: {state_id}")
            start_x, start_y, end_x, end_y = normalized_preview_stroke(
                preview, raw_stroke
            )
            source_point = None
            if isinstance(raw_source, list) and len(raw_source) == 2:
                if preview.position is None or preview.size is None:
                    raise RuntimeError(f"native stroke preview has no geometry: {state_id}")
                source_point = [
                    round(preview.position[0] + preview.size[0] * float(raw_source[0])),
                    round(preview.position[1] + preview.size[1] * float(raw_source[1])),
                ]
                self.driver.click_at(*source_point)
                time.sleep(0.8)
            self.driver.drag_at(start_x, start_y, end_x, end_y)
            time.sleep(0.5)
            if isinstance(apply_locator, str) and apply_locator:
                if not self.driver.has_locator(apply_locator):
                    raise RuntimeError(
                        f"native stroke apply control is absent: {state_id}: {apply_locator}"
                    )
                self.driver.press(apply_locator)
            after_nodes = self.driver.snapshot()
            used_guarded_canvas_fallback = False
            if (
                self.driver.low_interference
                and not self._has_tool_reset_marker(after_nodes)
            ):
                # Several Metal brush surfaces ignore process-targeted CGEvents.
                # Retry only those canvases with a real event while the physical
                # HID is idle; the helper restores the user's cursor atomically.
                if source_point is not None:
                    self.driver.guarded_canvas_click_at(*source_point)
                    time.sleep(0.8)
                self.driver.guarded_canvas_drag_at(
                    start_x, start_y, end_x, end_y
                )
                time.sleep(0.5)
                if isinstance(apply_locator, str) and apply_locator:
                    self.driver.press(apply_locator)
                after_nodes = self.driver.snapshot()
                used_guarded_canvas_fallback = True
            edit_state = self._verify_native_edit_state(after_nodes)
            self._ui_parameter_evidence = {
                "binding_status": "supported",
                "kind": kind,
                "normalized_stroke": raw_stroke,
                "native_stroke": [start_x, start_y, end_x, end_y],
                "normalized_source": raw_source,
                "native_source": source_point,
                "apply_locator_id": apply_locator,
                "guarded_canvas_fallback": used_guarded_canvas_fallback,
                "edit_state": edit_state,
                "readback_verified": bool(edit_state.get("verified")),
            }
            return after_nodes

        raise RuntimeError(
            f"native parameter operation is not implemented: {state_id}: {kind}"
        )

    @staticmethod
    def _has_tool_reset_marker(nodes) -> bool:
        return any(
            isinstance(node.identifier, str)
            and node.identifier.endswith(".ResetButton")
            and node.enabled is not False
            for node in nodes
        )

    def _verify_native_edit_state(self, nodes=None) -> dict[str, object]:
        """Accept a tool-local reset marker while global reset is deferred.

        Metal canvas tools do not expose Restore Original until their panel is
        collapsed.  Their enabled, dynamically-added ResetButton is the native
        proof that the edit exists while the panel is still open for capture.
        """

        try:
            return self.sampler._verify_photo_has_edits()
        except NonRetryableCaptureError:
            current = nodes if nodes is not None else self.driver.snapshot()
            reset = next(
                (
                    node
                    for node in current
                    if isinstance(node.identifier, str)
                    and node.identifier.endswith(".ResetButton")
                    and node.enabled is not False
                ),
                None,
            )
            if reset is None:
                raise
            return {
                "required": True,
                "verified": True,
                "locator_id": reset.identifier,
                "enabled": True,
                "scope": "tool",
                "global_restore_deferred_until_tool_close": True,
            }

    def _select_parameter_asset(
        self,
        record: SamplingQueueRecord,
        recipe: SamplingRecipe,
        nodes,
        layout: CaptureLayout,
    ):
        capability_id = str(record.payload["capability_id"])
        records = self._sampling_queue_payload.get("records", [])
        if capability_id == "sky_replace":
            return self._select_first_visible_sky_asset(
                record, recipe, nodes, layout
            )
        else:
            raw = next(
                item
                for item in records
                if item.get("kind") == "effect"
                and item.get("capability_id") == capability_id
                and item.get("asset_path")
            )
        asset_path = Path(str(raw["asset_path"])).resolve()
        asset_sha256 = sha256_file(asset_path)
        if asset_sha256 != raw.get("asset_sha256"):
            raise RuntimeError(
                f"native parameter asset hash mismatch: {capability_id}: {asset_path}"
            )
        case = CaptureCase.from_payload(
            {
                "case_id": f"ui-parameter-asset:{capability_id}",
                "capability_id": capability_id,
                "input": record.payload["input"],
                "parameters": {},
                "asset_id": raw["asset_id"],
                "asset_path": str(asset_path),
                "asset_sha256": asset_sha256,
            }
        )
        if capability_id == "color_transfer":
            control, value = self.sampler._select_inline_asset(
                case, recipe, nodes, layout
            )
        elif capability_id == "lut_mapping":
            control_locator = str(recipe.effective["control_locator_id"])
            choice_locator = str(recipe.effective["choice_locator_id"])
            self.driver.press(control_locator)
            menu_nodes = self.driver.snapshot()
            choices = [
                node
                for node in menu_nodes
                if node.role == "AXMenuItem"
                and node.enabled is not False
                and choice_locator
                in {node.identifier, node.title, node.value, node.description}
                and node.position is not None
                and node.size is not None
            ]
            if len(choices) != 1:
                raise RuntimeError(
                    f"native LUT choice is not unique: {choice_locator}: {len(choices)}"
                )
            choice = choices[0]
            self.driver.click_at(
                choice.position[0] + choice.size[0] // 2,
                choice.position[1] + choice.size[1] // 2,
            )
            control, value = control_locator, choice_locator
        else:
            raise RuntimeError(
                f"unsupported native parameter asset capability: {capability_id}"
            )
        time.sleep(0.3)
        after_nodes = self.driver.snapshot()
        return after_nodes, {
            "control": control,
            "value": value,
            "asset_id": raw["asset_id"],
            "asset_path": str(asset_path),
            "asset_sha256": asset_sha256,
        }

    def _select_first_visible_sky_asset(
        self,
        record: SamplingQueueRecord,
        recipe: SamplingRecipe,
        panel_nodes,
        layout: CaptureLayout,
    ):
        picker_locator = str(recipe.effective["picker_locator_id"])
        picker_identifier = str(recipe.effective["picker_thumbnail_identifier"])
        picker_control = select_unique_control(panel_nodes, picker_locator)
        panel_keys = {node.stable_key for node in panel_nodes}
        picker_nodes = ()
        for _ in range(3):
            self.driver.press(picker_locator)
            time.sleep(0.8)
            picker_nodes = self.driver.snapshot()
            if self.driver.has_locator("所有天空", picker_nodes):
                break
        else:
            raise TimeoutError("Luminar did not expose the current sky picker")
        thumbnails = [
            node
            for node in picker_nodes
            if node.role == "AXButton"
            and node.identifier == picker_identifier
            and node.enabled is not False
            and node.stable_key not in panel_keys
            and node.position is not None
            and node.size is not None
            and node.position[0] >= 1000
            and 48 <= node.size[0] <= 180
            and 48 <= node.size[1] <= 180
        ]
        if not thumbnails:
            raise RuntimeError("current sky picker has no visible local thumbnails")
        screenshot = layout.staging_dir / "sky-picker-current.png"
        self._screenshot_window(screenshot)
        # The current parameter contract requests ``first-local-free`` rather
        # than one named sky file.  Selecting a deterministic top-left visible
        # thumbnail is both faster and more faithful than trying to infer a file
        # identity from visually similar sky thumbnails.
        thumbnail = min(
            thumbnails,
            key=lambda node: (node.position[1], node.position[0], node.index),
        )
        self.driver.press_at(thumbnail.index)
        time.sleep(0.3)
        after_nodes = self.driver.snapshot()
        selected = next(
            (
                node
                for node in after_nodes
                if node.role == picker_control.role
                and node.position == picker_control.position
                and node.size == picker_control.size
            ),
            None,
        )
        selected_name = next(
            (
                value
                for value in (
                    selected.title,
                    selected.value,
                    selected.description,
                    selected.help,
                )
                if isinstance(value, str)
                and value
                and value != picker_locator
            ),
            None,
        ) if selected is not None else None
        edit_state = None
        if not selected_name:
            edit_state = self.sampler._verify_photo_has_edits()
            selected_name = "restore-original-enabled"
        return after_nodes, {
            "control": f"index:{thumbnail.index}",
            "value": selected_name,
            "asset_id": "first-local-free",
            "picker_screenshot_sha256": sha256_file(screenshot),
            "thumbnail_position": list(thumbnail.position),
            "semantic_readback": selected_name,
            "edit_state": edit_state,
        }

    def _prepare_ui_photo(
        self,
        raw_input: dict[str, object],
        *,
        preserve_transient_state: bool = False,
    ) -> None:
        path = Path(str(raw_input["path"])).resolve()
        expected = str(raw_input["sha256"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError(f"UI input hash mismatch: {digest} != {expected}")
        if not preserve_transient_state:
            self.driver.cancel()
        self.driver.activate()
        already_selected = False
        try:
            already_selected = self.sampler._snapshot_mentions_file(
                self.driver.snapshot(), path.name
            )
        except (RuntimeError, TimeoutError):
            pass
        self._ui_last_prepare_reused = (
            already_selected
            and self._ui_selected_input_sha256 == expected
            and self._ui_photo_clean
        )
        if self._ui_selected_input_sha256 != expected or not already_selected:
            self._ui_photo_clean = False
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        retry_at = 0.0
        while time.monotonic() < deadline:
            if not already_selected and time.monotonic() >= retry_at:
                self.controller.request_open_image(path)
                retry_at = time.monotonic() + 2.0
            nodes = self.driver.snapshot()
            if any(
                any(
                    expected_name in str(value).casefold()
                    for expected_name in (path.name.casefold(), path.stem.casefold())
                )
                for node in nodes
                for value in (node.identifier, node.title, node.value, node.help)
                if value is not None
            ):
                if not self._ui_photo_clean and not preserve_transient_state:
                    self.sampler.reset_photo_edits()
                self._ui_selected_input_sha256 = expected
                self._ui_photo_clean = True
                return
            time.sleep(0.2)
        raise TimeoutError(f"Luminar did not select UI input: {path.name}")

    def _prepare_ui_state(self, state: str):
        if state == "catalog":
            self.driver.press(WORKSPACE_LOCATORS["catalog"])
            if self.config.catalog_collection:
                self._wait_for_locator(self.config.catalog_collection)
                self.driver.press(self.config.catalog_collection)
                return self._wait_for_locator(self.config.catalog_collection)
            return self.driver.snapshot()
        if state == "presets":
            return self._prepare_presets_overview()
        if state == "multi-image":
            inputs = self._hdr_inputs()
            self._select_multi_image_inputs(inputs)
            self.driver.press("MPTopBarMergeButton")
            return self._wait_for_locator("MPTopBarMergeMenuItem.HDRMerge")
        if state == "multi-image-complete":
            return self._prepare_hdr_merge_complete()

        self.driver.press(WORKSPACE_LOCATORS["catalog"])
        time.sleep(0.3)
        self.driver.press(WORKSPACE_LOCATORS["edit"])
        nodes = self.driver.snapshot()
        nodes = self.sampler.ensure_layer_stack(nodes)
        if state == "edit":
            return nodes
        if state == "layer-stack":
            self.driver.press("overlaysView_addLayerItem")
            library = self._wait_for_locator("overlaysView_loadImageButton")
            thumbnails = [
                node
                for node in library
                if node.role == "AXImage"
                and node.identifier == "_NS:58"
                and node.position is not None
                and node.size is not None
            ]
            if not thumbnails:
                raise RuntimeError("Luminar layer library has no free overlay thumbnail")
            thumbnail = min(thumbnails, key=lambda item: (item.position[1], item.position[0]))
            self.driver.click_at(*self._node_center(thumbnail))
            return self._wait_for(
                lambda current: len(self._layer_thumbnails(current)) >= 2,
                "two real image layers",
                timeout_seconds=self.config.timeouts.inference_seconds,
            )
        if state == "layer-library":
            self.driver.press("overlaysView_addLayerItem")
            nodes = self._wait_for_locator("overlaysView_loadImageButton")
            if not all(
                self.driver.has_locator(category, nodes)
                for category in ("星尘散景", "漏光", "烟火", "耀斑")
            ):
                raise RuntimeError("Luminar layer library is missing a free category")
            return nodes
        if state == "tool-expanded":
            self.driver.press("EditExpandButton_AIEnhanceAdjustmentLayer")
            return self._wait_for_locator("ButtonTabsItem_Adjustments")
        if state == "edit-history":
            self._apply_details_edit(65)
            self.driver.press("NavigationPanel.Tab.Edits")
            return self._wait_for(
                lambda current: self.driver.has_locator(DETAILS_SLIDER_LOCATOR, current)
                and any(node.value == "编辑" for node in current),
                "edit history with committed Details edit",
            )
        if state == "more-panel":
            self.driver.press("NavigationPanel.Tab.Extra")
            return self._wait_for(
                lambda current: self._active_navigation_tab(
                    current, "NavigationPanel.Tab.Extra"
                )
                and not self.driver.has_locator(
                    "EditExpandButton_DefaultEffects", current
                ),
                "active More panel",
            )
        if state == "info-panel":
            self.driver.press("NavigationPanel.Tab.Info")
            return self._wait_for(
                lambda current: self._active_navigation_tab(
                    current, "NavigationPanel.Tab.Info"
                )
                and any(node.value == "影像资讯" for node in current),
                "active image Info panel",
            )
        if state == "edit-collapsed":
            expanded_preview = self._require_node(nodes, "PreviewImage")
            self.driver.press("NavigationPanel.Tab.Tools")
            return self._wait_for(
                lambda current: not self.driver.has_locator(
                    "EditExpandButton_DefaultEffects", current
                )
                and self._preview_geometry_changed(current, expanded_preview),
                "collapsed edit panel",
            )
        if state == "black-white-before-conversion":
            self._open_tool("EditExpandButton_BWChannels_v1_Effect")
            return self._wait_for_locator(BW_ACTIVATION_LOCATOR)
        if state == "black-white-after-conversion":
            self._open_tool("EditExpandButton_BWChannels_v1_Effect")
            self.driver.ax_press(BW_ACTIVATION_LOCATOR)
            return self._wait_for_locator(BW_RED_SLIDER_LOCATOR)
        if state == "denoise-level-selected":
            self._open_tool("EditExpandButton_DenoiseAI")
            self.driver.ax_press(DENOISE_LEVEL_LOCATOR)
            return self._wait_for(
                lambda current: self.driver.has_locator(DENOISE_LEVEL_LOCATOR, current)
                and self.driver.has_locator(DENOISE_SLIDER_LOCATOR, current),
                "Denoise AI medium level controls",
                timeout_seconds=self.config.timeouts.heavy_inference_seconds,
            )
        if state == "export-dialog":
            self._apply_details_edit(65)
            menu_nodes = self.driver.open_export_menu()
            export_items = [
                node
                for node in menu_nodes
                if node.identifier == "NSMenuItem.NewExport" and node.enabled is True
            ]
            if len(export_items) != 1:
                raise RuntimeError(
                    "Luminar New Export menu item is not uniquely enabled"
                )
            self.driver.ax_press("NSMenuItem.NewExport")
            return self._wait_for_locator("saveAsNameTextField")
        raise RuntimeError(f"native UI transition is not implemented: {state}")

    def _hdr_inputs(self) -> list[Path]:
        root = self.config.multi_image_validation_root / "hdr_merge"
        inputs = sorted(
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in RASTER_SUFFIXES
        )
        if len(inputs) < 2:
            raise RuntimeError(
                f"multi-image UI state requires at least two inputs: {root}"
            )
        return inputs

    def _prepare_hdr_merge_complete(self):
        self.driver.press(WORKSPACE_LOCATORS["catalog"])
        self._wait_for_locator("HDR Merge")
        self.driver.press("HDR Merge")
        result_pattern = re.compile(r"_HDR(?: \d+)?$", re.IGNORECASE)
        result_nodes = self._wait_for(
            lambda current: any(
                node.identifier == "MPInstrumentInfoViewControllerFileName"
                and node.value is not None
                and result_pattern.search(str(node.value))
                for node in current
            ),
            "existing completed HDR result",
        )
        result_names = sorted(
            {
                str(node.value)
                for node in result_nodes
                if node.identifier == "MPInstrumentInfoViewControllerFileName"
                and node.value is not None
                and result_pattern.search(str(node.value))
            },
            key=lambda value: (bool(re.search(r" \d+$", value)), len(value), value),
        )
        if result_names:
            self.driver.press(result_names[0])
            time.sleep(0.5)
            nodes = self.driver.snapshot()
            if self.driver.has_locator("单图视图", nodes):
                self.driver.press("单图视图")
            return self._wait_for_locator("PreviewImage")
        raise RuntimeError("Luminar HDR Merge collection has no reusable result")

    def _apply_details_edit(self, value: float):
        self._open_tool("EditExpandButton_DetailsEnhancerAdjustmentLayer")
        self.driver.set_value_first(DETAILS_SLIDER_LOCATOR, value)
        return self._wait_for(
            lambda current: any(
                node.identifier == DETAILS_SLIDER_LOCATOR
                and isinstance(node.value, (int, float))
                and abs(float(node.value) - value) <= 1
                for node in current
            ),
            f"Details value {value}",
        )

    def _open_tool(self, locator: str):
        nodes = self.driver.snapshot()
        if not self.driver.has_locator(locator, nodes):
            nodes = self.sampler._find_tool_by_scrolling(locator)
        if nodes is None or not self.driver.has_locator(locator, nodes):
            raise TimeoutError(f"Luminar did not expose required tool: {locator}")
        self.driver.press(locator)
        return self.driver.snapshot()

    @staticmethod
    def _node_center(node) -> tuple[int, int]:
        if node.position is None or node.size is None:
            raise RuntimeError("Luminar accessibility node has no bounds")
        return (
            round(node.position[0] + node.size[0] / 2),
            round(node.position[1] + node.size[1] / 2),
        )

    @staticmethod
    def _layer_thumbnails(nodes):
        return tuple(
            node
            for node in nodes
            if node.role == "AXImage"
            and node.identifier == "_NS:33"
            and node.size == (54, 54)
        )

    @staticmethod
    def _active_navigation_tab(nodes, locator: str) -> bool:
        return any(
            node.identifier == locator
            and node.size is not None
            and node.size[0] >= 50
            and node.size[1] >= 50
            for node in nodes
        )

    @staticmethod
    def _require_node(nodes, locator: str):
        matches = [
            node
            for node in nodes
            if locator
            in {node.identifier, node.title, node.description, node.help, node.value}
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Luminar locator {locator!r} resolved to {len(matches)} nodes"
            )
        return matches[0]

    @classmethod
    def _preview_geometry_changed(cls, nodes, previous) -> bool:
        current = cls._require_node(nodes, "PreviewImage")
        return current.position != previous.position or current.size != previous.size

    def _wait_for(
        self,
        predicate,
        description: str,
        *,
        timeout_seconds: float | None = None,
    ):
        deadline = time.monotonic() + (
            timeout_seconds or self.config.timeouts.navigation_seconds
        )
        while time.monotonic() < deadline:
            nodes = self.driver.snapshot()
            if predicate(nodes):
                return nodes
            time.sleep(0.2)
        raise TimeoutError(f"Luminar did not reach {description}")

    def _wait_for_locator_absent(self, locator: str):
        return self._wait_for(
            lambda current: not self.driver.has_locator(locator, current),
            f"absence of {locator}",
        )

    def _prepare_presets_overview(self):
        back = "NSButton.TemplateCollectionDetailViewController.BackButton"
        deadline = time.monotonic() + self.config.timeouts.navigation_seconds
        retry_at = 0.0
        nodes = self.driver.snapshot()
        while time.monotonic() < deadline:
            if time.monotonic() >= retry_at:
                self.driver.press(WORKSPACE_LOCATORS["presets"])
                retry_at = time.monotonic() + 1.0
            nodes = self.driver.snapshot()
            if self.driver.has_locator("对于这张照片", nodes):
                return nodes
            if self.driver.has_locator(back, nodes):
                self.driver.ax_press(back)
            time.sleep(0.2)
        raise TimeoutError("Luminar did not expose the presets overview")

    def _screenshot_window(self, destination: Path) -> WindowBounds:
        state = self.driver.state()
        raw_bounds = state.get("bounds")
        if not (
            isinstance(raw_bounds, list)
            and len(raw_bounds) == 4
            and all(isinstance(value, (int, float)) for value in raw_bounds)
        ):
            raise RuntimeError("Luminar accessibility state has no usable window bounds")
        bounds = WindowBounds(*(int(value) for value in raw_bounds))
        window_id = state.get("window_id")
        if not isinstance(window_id, int) or window_id <= 0:
            raise RuntimeError("Luminar accessibility state has no usable window id")
        return self.controller.screenshot_window(
            destination,
            window_id=window_id,
            bounds=bounds,
        )
