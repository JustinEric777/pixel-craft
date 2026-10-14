"""Typed configuration for guided Computer Use Luminar capture runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SamplingTimeouts:
    action_seconds: float
    navigation_seconds: float
    inference_seconds: float
    heavy_inference_seconds: float
    export_seconds: float
    stable_seconds: float


@dataclass(frozen=True)
class SamplingRecipe:
    capability_id: str
    workspace: str
    locator_id: str
    strategy: str
    default_capture: bool
    effective: dict[str, Any]


@dataclass(frozen=True)
class LuminarSamplingConfig:
    reference_id: str
    app_path: Path
    retries: int
    stable_samples: int
    screenshot_mae_max: float
    preview_change_mae_min: float
    change_pixel_delta_min: float
    change_pixel_fraction_min: float
    preview_export_comparison_size: int
    preview_export_rgb_mae_max: float
    preview_export_luma_mae_max: float
    export_source_mae_min: float
    panel_scroll_attempts: int
    panel_scroll_lines: int
    overlay_thumbnail_mae_max: float
    overlay_thumbnail_mae_hard_max: float
    overlay_thumbnail_margin_min: float
    timeouts: SamplingTimeouts
    viewports: tuple[tuple[int, int], ...]
    logical_viewport: tuple[int, int]
    environment_evidence_path: Path
    ui_states: tuple[str, ...]
    page_order: tuple[str, ...]
    ui_state_pages: dict[str, str]
    excluded_feature_groups: tuple[str, ...]
    excluded_capabilities: frozenset[str]
    overlay_collection_order: tuple[str, ...]
    canonical_input_sha256: dict[str, str]
    catalog_collection: str
    multi_image_validation_root: Path
    native_export_root: Path
    export_extension: str
    recipes: dict[str, SamplingRecipe]

    def recipe_for(self, capability_id: str) -> SamplingRecipe:
        try:
            return self.recipes[capability_id]
        except KeyError as exc:
            raise KeyError(f"Luminar sampling recipe is missing: {capability_id}") from exc


def _positive_number(payload: dict[str, Any], key: str) -> float:
    value = float(payload[key])
    if value <= 0:
        raise ValueError(f"sampling timeout must be positive: {key}")
    return value


def load_luminar_sampling_config(path: Path) -> LuminarSamplingConfig:
    """Load one fail-closed Luminar sampling configuration."""

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Luminar sampling configuration is missing: {path}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"invalid Luminar sampling configuration: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError("Luminar sampling configuration root must be an object")
    reference = payload.get("reference", {})
    automation = payload.get("automation", {})
    capture = payload.get("capture", {})
    raw_recipes = payload.get("recipes", {})
    if not isinstance(raw_recipes, dict) or not raw_recipes:
        raise ValueError("Luminar sampling configuration requires recipes")
    recipes: dict[str, SamplingRecipe] = {}
    for capability_id, raw in raw_recipes.items():
        if not isinstance(raw, dict):
            raise TypeError(f"sampling recipe must be an object: {capability_id}")
        locator_id = str(raw.get("locator_id") or "")
        strategy = str(raw.get("strategy") or "")
        if not locator_id or not strategy:
            raise ValueError(
                f"sampling recipe requires locator_id and strategy: {capability_id}"
            )
        effective = raw.get("effective", {})
        if not isinstance(effective, dict):
            raise TypeError(f"sampling recipe effective must be an object: {capability_id}")
        recipes[str(capability_id)] = SamplingRecipe(
            capability_id=str(capability_id),
            workspace=str(raw.get("workspace", "edit")),
            locator_id=locator_id,
            strategy=strategy,
            default_capture=bool(raw.get("default_capture", True)),
            effective=dict(effective),
        )
    raw_viewports = capture.get("viewports", [])
    project_root = path.resolve().parent.parent
    viewports = tuple((int(item[0]), int(item[1])) for item in raw_viewports)
    if not viewports or any(width <= 0 or height <= 0 for width, height in viewports):
        raise ValueError("sampling capture requires positive viewports")
    raw_logical_viewport = capture.get("logical_viewport", [])
    if (
        not isinstance(raw_logical_viewport, list)
        or len(raw_logical_viewport) != 2
        or any(int(value) <= 0 for value in raw_logical_viewport)
    ):
        raise ValueError("sampling capture requires one positive logical_viewport")
    logical_viewport = (
        int(raw_logical_viewport[0]),
        int(raw_logical_viewport[1]),
    )
    raw_environment_evidence = str(capture.get("environment_evidence_path") or "")
    if not raw_environment_evidence:
        raise ValueError("sampling capture requires environment_evidence_path")
    environment_evidence = Path(raw_environment_evidence)
    environment_evidence_path = (
        environment_evidence.resolve()
        if environment_evidence.is_absolute()
        else (project_root / environment_evidence).resolve()
    )
    timeouts = automation.get("timeouts", {})
    raw_output_value = str(capture.get("native_export_root") or "")
    if not raw_output_value:
        raise ValueError("sampling capture requires native_export_root")
    raw_output_root = Path(raw_output_value)
    output_root = (
        raw_output_root.resolve()
        if raw_output_root.is_absolute()
        else (project_root / raw_output_root).resolve()
    )
    raw_multi_image_value = str(capture.get("multi_image_validation_root") or "")
    if not raw_multi_image_value:
        raise ValueError("sampling capture requires multi_image_validation_root")
    raw_multi_image_root = Path(raw_multi_image_value)
    multi_image_validation_root = (
        raw_multi_image_root.resolve()
        if raw_multi_image_root.is_absolute()
        else (project_root / raw_multi_image_root).resolve()
    )
    export_extension = str(capture.get("export_extension") or "")
    if export_extension not in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        raise ValueError(f"unsupported sampling export extension: {export_extension!r}")
    page_order = tuple(str(item) for item in capture.get("page_order", []))
    if page_order != ("catalog", "presets", "edit"):
        raise ValueError(
            "sampling capture page_order must be catalog, presets, edit"
        )
    ui_states = tuple(str(item) for item in capture.get("ui_states", []))
    raw_ui_state_pages = capture.get("ui_state_pages", {})
    if not isinstance(raw_ui_state_pages, dict):
        raise TypeError("sampling capture ui_state_pages must be an object")
    ui_state_pages = {
        str(state): str(page) for state, page in raw_ui_state_pages.items()
    }
    excluded_feature_groups = tuple(
        str(item) for item in capture.get("excluded_feature_groups", [])
    )
    excluded_capabilities = frozenset(
        str(item) for item in capture.get("excluded_capabilities", [])
    )
    overlay_collection_order = tuple(
        str(item) for item in capture.get("overlay_collection_order", [])
    )
    if not overlay_collection_order:
        raise ValueError("sampling capture requires overlay_collection_order")
    raw_canonical_inputs = capture.get("canonical_input_sha256", {})
    if not isinstance(raw_canonical_inputs, dict):
        raise TypeError("sampling capture canonical_input_sha256 must be an object")
    canonical_input_sha256 = {
        str(kind): str(digest)
        for kind, digest in raw_canonical_inputs.items()
    }
    if set(canonical_input_sha256) != {"preset", "overlay"} or any(
        len(digest) != 64 for digest in canonical_input_sha256.values()
    ):
        raise ValueError(
            "sampling capture requires SHA-256 canonical inputs for preset and overlay"
        )
    missing_state_pages = sorted(set(ui_states) - set(ui_state_pages))
    invalid_state_pages = sorted(set(ui_state_pages.values()) - set(page_order))
    if missing_state_pages or invalid_state_pages:
        raise ValueError(
            "sampling capture ui_state_pages is invalid: "
            f"missing={missing_state_pages}, invalid_pages={invalid_state_pages}"
        )
    comparison_size = int(automation.get("preview_export_comparison_size", 128))
    rgb_mae_max = float(automation.get("preview_export_rgb_mae_max", 0.03))
    luma_mae_max = float(automation.get("preview_export_luma_mae_max", 0.02))
    overlay_thumbnail_mae_max = float(
        automation.get("overlay_thumbnail_mae_max", 16.0)
    )
    overlay_thumbnail_mae_hard_max = float(
        automation.get("overlay_thumbnail_mae_hard_max", 32.0)
    )
    overlay_thumbnail_margin_min = float(
        automation.get("overlay_thumbnail_margin_min", 8.0)
    )
    change_pixel_delta_min = float(
        automation.get("change_pixel_delta_min", 0.04)
    )
    change_pixel_fraction_min = float(
        automation.get("change_pixel_fraction_min", 0.001)
    )
    if (
        comparison_size <= 0
        or rgb_mae_max <= 0
        or luma_mae_max <= 0
        or overlay_thumbnail_mae_max <= 0
        or overlay_thumbnail_mae_hard_max < overlay_thumbnail_mae_max
        or overlay_thumbnail_margin_min <= 0
        or not 0 < change_pixel_delta_min <= 1
        or not 0 < change_pixel_fraction_min <= 1
    ):
        raise ValueError("sampling preview/export comparison settings must be positive")
    return LuminarSamplingConfig(
        reference_id=str(reference.get("id") or ""),
        app_path=Path(str(reference.get("app") or "")).expanduser().resolve(),
        retries=int(automation.get("retries", 2)),
        stable_samples=int(automation.get("stable_samples", 3)),
        screenshot_mae_max=float(automation.get("screenshot_mae_max", 0.002)),
        preview_change_mae_min=float(
            automation.get("preview_change_mae_min", 0.01)
        ),
        change_pixel_delta_min=change_pixel_delta_min,
        change_pixel_fraction_min=change_pixel_fraction_min,
        preview_export_comparison_size=comparison_size,
        preview_export_rgb_mae_max=rgb_mae_max,
        preview_export_luma_mae_max=luma_mae_max,
        export_source_mae_min=float(
            automation.get("export_source_mae_min", 0.01)
        ),
        panel_scroll_attempts=int(automation.get("panel_scroll_attempts", 14)),
        panel_scroll_lines=int(automation.get("panel_scroll_lines", 8)),
        overlay_thumbnail_mae_max=overlay_thumbnail_mae_max,
        overlay_thumbnail_mae_hard_max=overlay_thumbnail_mae_hard_max,
        overlay_thumbnail_margin_min=overlay_thumbnail_margin_min,
        timeouts=SamplingTimeouts(
            action_seconds=_positive_number(timeouts, "action_seconds"),
            navigation_seconds=_positive_number(timeouts, "navigation_seconds"),
            inference_seconds=_positive_number(timeouts, "inference_seconds"),
            heavy_inference_seconds=_positive_number(
                timeouts, "heavy_inference_seconds"
            ),
            export_seconds=_positive_number(timeouts, "export_seconds"),
            stable_seconds=_positive_number(timeouts, "stable_seconds"),
        ),
        viewports=viewports,
        logical_viewport=logical_viewport,
        environment_evidence_path=environment_evidence_path,
        ui_states=ui_states,
        page_order=page_order,
        ui_state_pages=ui_state_pages,
        excluded_feature_groups=excluded_feature_groups,
        excluded_capabilities=excluded_capabilities,
        overlay_collection_order=overlay_collection_order,
        canonical_input_sha256=canonical_input_sha256,
        catalog_collection=str(capture.get("catalog_collection") or ""),
        multi_image_validation_root=multi_image_validation_root,
        native_export_root=output_root,
        export_extension=export_extension,
        recipes=recipes,
    )
