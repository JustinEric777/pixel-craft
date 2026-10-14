"""Render the same edit graph for preview and export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageOps

from core.errors import ModelExecutionError
from core.execution import CapabilityExecutionGraph
from core.project.entities import ProjectState

from .basic import apply_effect, blend, composite_image_layer, composite_texture


def render_project(
    state: ProjectState,
    output: Path | None = None,
    asset_root: Path | None = None,
    model_service: Any | None = None,
    execution_graphs: dict[str, CapabilityExecutionGraph] | None = None,
) -> Image.Image:
    current = Image.open(state.source.path).convert("RGB")
    catalog_rotation = int(state.metadata.get("catalog_rotation", 0)) % 360
    if catalog_rotation:
        current = current.rotate(
            -catalog_rotation,
            expand=True,
            resample=Image.Resampling.BICUBIC,
        )
    for layer in state.layers:
        if not layer.visible:
            continue
        with Image.open(layer.path) as source_layer:
            layer_mask = _mask_image(state, layer.mask_artifact, current.size)
            current = composite_image_layer(
                current,
                source_layer,
                opacity=layer.opacity,
                mode=layer.blend_mode,
                scale=layer.scale,
                offset_x=layer.offset_x,
                offset_y=layer.offset_y,
                rotation=layer.rotation,
                flip_x=layer.flip_x,
                flip_y=layer.flip_y,
                stretch=layer.source_kind == "library",
                mask=layer_mask,
            )
    for node in state.edits:
        if not node.enabled:
            continue
        texture_path = node.parameters.get("asset_path")
        texture = None
        candidate = None
        if texture_path and asset_root:
            root = asset_root.resolve()
            candidate = (root / str(texture_path)).resolve()
            if not candidate.is_relative_to(root):
                raise ValueError("asset_path must remain inside the configured asset root")
            if node.effect != "lut_mapping":
                texture = Image.open(candidate).convert("RGB")
        effect_parameters = dict(node.parameters)
        if asset_root is not None:
            effect_parameters["_asset_root"] = str(asset_root.resolve())
        if candidate is not None and node.effect == "lut_mapping":
            effect_parameters["_lut_path"] = str(candidate)
        if texture is not None and node.effect in {"sky_replace", "augmented_sky"}:
            # The model service owns sky masking and geometric compositing;
            # PIL objects stay inside the renderer and never cross the API.
            effect_parameters["_sky_texture"] = texture
        if texture is not None and node.effect == "color_transfer":
            effect_parameters["_reference_image"] = texture
        edited = (
            model_service.apply_image_effect(current, node.effect, effect_parameters)
            if model_service
            else None
        )
        if edited is None:
            graph = (execution_graphs or {}).get(node.effect)
            if graph is not None and graph.implementation == "model-backed":
                raise ModelExecutionError(
                    f"model-backed effect did not produce an image: {node.effect}"
                )
            edited = apply_effect(current, node.effect, effect_parameters)
        if texture is not None and node.effect not in {
            "sky_replace",
            "augmented_sky",
            "color_transfer",
        }:
            edited = composite_texture(
                edited,
                texture,
                opacity=float(node.parameters.get("texture_opacity", 0.5)),
                mode=str(node.parameters.get("texture_mode", "screen")),
                offset_y=float(node.parameters.get("texture_offset_y", 0.0)),
            )
        opacity = float(node.parameters.get("opacity", 1.0))
        edit_mask = _mask_image(state, node.mask_artifact, edited.size)
        if edited.size != current.size:
            # Restoration/upscale nodes may intentionally change the canvas
            # size. Blend at the new size instead of silently shrinking the
            # model output back to the input dimensions.
            current = blend(
                current.resize(edited.size, Image.Resampling.BICUBIC),
                edited,
                opacity,
                edit_mask,
            )
        else:
            current = blend(current, edited, opacity, edit_mask)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        current.save(output)
    return current


def _mask_image(
    state: ProjectState, mask_id: str | None, size: tuple[int, int]
) -> Image.Image | None:
    if mask_id is None:
        return None
    mask = state.masks.get(mask_id)
    if mask is None or not mask.path.is_file():
        raise ValueError(f"mask artifact is missing: {mask_id}")
    image = Image.open(mask.path).convert("L").resize(size, Image.Resampling.BILINEAR)
    if mask.feather:
        image = image.filter(ImageFilter.GaussianBlur(mask.feather))
    if mask.inverted:
        image = ImageOps.invert(image)
    if mask.density != 1.0:
        density = max(0.0, min(1.0, mask.density))
        image = image.point(lambda value: round(value * density))
    return image
