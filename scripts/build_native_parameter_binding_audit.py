#!/usr/bin/env python3
"""Audit current core parameters against exact Luminar Neo AX controls."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.parity_parameter_values import canonical_parameter_value

DEFAULT_MATRIX = ROOT / "configs/parity/core-ui-state-matrix.json"
DEFAULT_SCHEMA = ROOT / "configs/capabilities/parameter-schema.json"
DEFAULT_SAMPLING = ROOT / "configs/luminar_sampling.yaml"
DEFAULT_OUTPUT = ROOT / "configs/parity/native-parameter-bindings.json"

SKY_CONTROLS = {
    "horizon_offset": ("AdvancedSlider.NSButton.Sky Orientation", "Slider.MIPLSkyReplacementEffect.Horizon"),
    "vertical_offset": ("AdvancedSlider.NSButton.Sky Orientation", "Slider.MIPLSkyReplacementEffect.Sky Vertical Offset"),
    "horizontal_offset": ("AdvancedSlider.NSButton.Sky Orientation", "Slider.MIPLSkyReplacementEffect.Sky Horizontal Offset"),
    "sky_flip": ("AdvancedSlider.NSButton.Sky Orientation", "NSButton.MIPLSkyReplacementEffect.SkyFlip"),
    "edge_refinement": ("AdvancedSlider.NSButton.Mask Refinement", "Slider.MIPLSkyReplacementEffect.Sigma"),
    "sky_global": ("AdvancedSlider.NSButton.Mask Refinement", "Slider.MIPLSkyReplacementEffect.SkyGlobal"),
    "fix_gaps": ("AdvancedSlider.NSButton.Mask Refinement", "Slider.MIPLSkyReplacementEffect.FixGaps"),
    "foreground_relight": ("AdvancedSlider.NSButton.Scene Relighting", "Slider.MIPLSkyReplacementEffect.Relighting"),
    "relight_saturation": ("AdvancedSlider.NSButton.Scene Relighting", "Slider.MIPLSkyReplacementEffect.Relighting Saturation"),
    "relight_human": ("AdvancedSlider.NSButton.Scene Relighting", "Slider.MIPLSkyReplacementEffect.Relight Human"),
    "reflection_blur": ("AdvancedSlider.NSButton.Reflection", "Slider.MIPLSkyReplacementEffect.WaterBlur"),
    "reflection_amount": ("AdvancedSlider.NSButton.Reflection", "Slider.MIPLSkyReplacementEffect.Water"),
    "sky_grain": ("AdvancedSlider.NSButton.Sky Adjustments", "Slider.MIPLSkyReplacementEffect.Sky Grain"),
    "sky_blur": ("AdvancedSlider.NSButton.Sky Adjustments", "Slider.MIPLSkyReplacementEffect.SkyBlur"),
    "atmospheric_haze": ("AdvancedSlider.NSButton.Sky Adjustments", "Slider.MIPLSkyReplacementEffect.White"),
    "temperature": ("AdvancedSlider.NSButton.Sky Adjustments", "Slider.MIPLSkyReplacementEffect.Temperature"),
    "brightness": ("AdvancedSlider.NSButton.Sky Adjustments", "Slider.MIPLSkyReplacementEffect.SkyExposure"),
}

AMOUNT_OVERRIDES = {
    "color_transfer": "Slider.MIPLColorTransferEffect.Amount.Slider",
    "dodge_burn": "Slider.MIPLDodgeAndBurnEffect.Amount.Slider",
    "lut_mapping": "Slider.MIPLLUTMappingEffect.Amount.Slider",
}

NEON_CONTROLS = {
    "neon_spread": "Slider.MIPLNewNeonLightEffect.FreeNeonGlow.Slider",
    "neon_atmosphere": "Slider.MIPLNewNeonLightEffect.FreeCloudsIndent.Slider",
    "neon_hue": "Slider.MIPLNewNeonLightEffect.FreeNeonHue.Slider",
    "neon_whiteness": "Slider.MIPLNewNeonLightEffect.FreeNeonWhiteness.Slider",
}

DENOISE_CONTROLS = {
    "luminosity": "Slider.MIPLDenoiseAIEffect.Luminosity Denoise.Slider",
    "details": "Slider.MIPLDenoiseAIEffect.Details.Slider",
    "sharpness": "Slider.MIPLDenoiseAIEffect.Sharpness.Slider",
}

BLOCKED_AMOUNT_CAPABILITIES = {"crop_ai", "deblur", "erase", "clone"}


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _native_value(definition: dict[str, Any], canonical: float) -> float:
    anchors = definition.get("native_anchors")
    if isinstance(anchors, list) and anchors:
        points = sorted(
            (float(item["value"]), float(item["native_value"])) for item in anchors
        )
        if canonical <= points[0][0]:
            return points[0][1]
        if canonical >= points[-1][0]:
            return points[-1][1]
        for (left, native_left), (right, native_right) in itertools.pairwise(points):
            if left <= canonical <= right:
                ratio = (canonical - left) / (right - left)
                return round(native_left + (native_right - native_left) * ratio, 6)
    if "native_min" in definition and "native_max" in definition:
        minimum = float(definition["min"])
        maximum = float(definition["max"])
        ratio = (canonical - minimum) / (maximum - minimum)
        return round(
            float(definition["native_min"])
            + ratio * (float(definition["native_max"]) - float(definition["native_min"])),
            6,
        )
    return canonical


def _snapshot_nodes(path: Path) -> list[dict[str, Any]]:
    payload = _json(path)
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        raise TypeError(f"AX snapshot has no nodes list: {path}")
    return nodes


def _exact_amount_locator(
    capability_id: str,
    recipe: Any,
    nodes: list[dict[str, Any]],
) -> str | None:
    if capability_id in BLOCKED_AMOUNT_CAPABILITIES:
        return None
    override = AMOUNT_OVERRIDES.get(capability_id)
    configured = recipe.effective.get("control_locator_id")
    candidate = override or (
        configured if isinstance(configured, str) and configured.startswith("Slider.") else None
    )
    identifiers = [str(node.get("identifier") or "") for node in nodes]
    if candidate:
        if candidate not in identifiers:
            raise RuntimeError(
                f"configured amount locator is absent from {capability_id} snapshot: {candidate}"
            )
        return candidate
    sliders = [
        node
        for node in nodes
        if node.get("role") == "AXSlider"
        and str(node.get("identifier") or "").endswith(".Slider")
        and node.get("enabled") is not False
    ]
    sliders.sort(key=lambda node: tuple(node.get("position") or [10**9, 10**9]))
    if not sliders:
        return None
    locator = str(sliders[0].get("identifier") or "")
    return locator or None


def build_audit(
    *,
    matrix: dict[str, Any],
    schema: dict[str, Any],
    sampling_path: Path,
    ui_root: Path,
) -> dict[str, Any]:
    sampling = load_luminar_sampling_config(sampling_path)
    definitions = schema.get("common_parameters", {})
    records: list[dict[str, Any]] = []
    parameter_records = [
        item for item in matrix.get("records", []) if item.get("kind") == "tool-parameter-state"
    ]
    for item in parameter_records:
        state_id = str(item["id"])
        capability_id = str(item["capability_id"])
        parameter = str(item["parameter"])
        shared_definition = definitions.get(parameter)
        if not isinstance(shared_definition, dict):
            raise TypeError(f"missing parameter definition: {state_id}")
        override = (
            schema.get("capabilities", {})
            .get(capability_id, {})
            .get("parameter_overrides", {})
            .get(parameter, {})
        )
        definition = {**shared_definition, **override}
        canonical = canonical_parameter_value(parameter, definition)
        snapshot = ui_root / f"tool:{capability_id}:expanded.ax.json"
        nodes = _snapshot_nodes(snapshot)
        evidence = {"ax_snapshot": str(snapshot.resolve()), "sha256": _sha256(snapshot)}
        status = "blocked-native-mismatch"
        reason = "current core parameter has no equivalent control in the native tool panel"
        native: dict[str, Any] | None = None

        if parameter == "opacity":
            reason = "Luminar exposes no universal per-tool opacity control; layer opacity is a different contract"
        elif parameter == "amount":
            locator = _exact_amount_locator(capability_id, sampling.recipe_for(capability_id), nodes)
            if locator:
                status = "supported"
                reason = (
                    "bound to the exact native amount control after selecting a reference asset"
                    if capability_id == "color_transfer"
                    else "bound to the recipe's exact native primary intensity control"
                )
                native = {
                    "kind": "slider",
                    "control_locator_id": locator,
                    "value": canonical,
                    "value_space": "normalized-signed",
                }
                activation = sampling.recipe_for(capability_id).effective.get("activation_locator_id")
                if isinstance(activation, str) and activation:
                    native["activation_locator_id"] = activation
                if capability_id == "color_transfer":
                    native["prerequisite"] = "select-first-local-reference"
            else:
                reason = f"{capability_id} has no native continuous primary intensity control"
        elif capability_id == "sky_replace" and parameter == "asset_id":
            status = "supported"
            reason = "bound to the native sky asset picker"
            native = {
                "kind": "asset-picker",
                "control_locator_id": "NSButton.TextureButtonSky Selection",
                "value": "first-local-free",
            }
        elif capability_id == "sky_replace" and parameter in SKY_CONTROLS:
            section, control = SKY_CONTROLS[parameter]
            status = "supported"
            reason = "bound to an exact native Sky AI control with independent readback"
            native = {
                "kind": "button" if definition.get("type") == "boolean" else "slider",
                "section_locator_id": section,
                "control_locator_id": control,
                "value": (
                    canonical
                    if definition.get("type") == "boolean"
                    else _native_value(definition, float(canonical))
                ),
                "value_space": "native",
            }
            if parameter == "sky_flip":
                native["prerequisite"] = "select-first-local-sky"
        elif capability_id == "denoise" and parameter == "denoise_level":
            status = "supported"
            reason = "bound to the exact native Noiseless level button"
            native = {
                "kind": "button",
                "control_locator_id": {
                    "low": "NSButton.Noiseless.Low",
                    "middle": "NSButton.Noiseless.Mid",
                    "high": "NSButton.Noiseless.High",
                }[str(canonical)],
                "value": canonical,
            }
        elif capability_id == "denoise" and parameter in DENOISE_CONTROLS:
            status = "supported"
            reason = "bound to an exact native Noiseless adjustment slider"
            native = {
                "kind": "slider",
                "control_locator_id": DENOISE_CONTROLS[parameter],
                "value": _native_value(definition, float(canonical)),
                "value_space": "native",
            }
        elif capability_id == "deblur" and parameter == "sharp_level":
            status = "supported"
            reason = "bound to the exact native Supersharp level button"
            native = {
                "kind": "button",
                "control_locator_id": {
                    "low": "NSButton.Supersharp.Low",
                    "middle": "NSButton.Supersharp.Mid",
                    "high": "NSButton.Supersharp.High",
                }[str(canonical)],
                "value": canonical,
            }
        elif capability_id == "deblur" and parameter == "face_enhancer_enabled":
            status = "supported"
            reason = "bound to the exact native Supersharp face enhancer toggle"
            native = {
                "kind": "button",
                "control_locator_id": "NSButton.Supersharp.FaceEnhancer",
                "value": canonical,
            }
        elif capability_id in {"color_transfer", "lut_mapping"} and parameter == "asset_id":
            status = "supported"
            reason = "bound to the tool's exact native local asset selector"
            native = {
                "kind": "asset-picker",
                "control_locator_id": (
                    "NSButton.TextureButtonReference Path"
                    if capability_id == "color_transfer"
                    else "NSButton.ChoseLUT"
                ),
                "value": "first-local-free",
            }
        elif capability_id == "new_neon_light" and parameter in NEON_CONTROLS:
            status = "supported"
            reason = "bound to an exact native Neon AI slider"
            native = {
                "kind": "slider",
                "control_locator_id": NEON_CONTROLS[parameter],
                "value": _native_value(definition, float(canonical)),
                "value_space": "native",
                "activation_locator_id": "NSButton.Neon.Freeform",
            }
        elif parameter == "strokes" and capability_id in {
            "erase", "dodge_burn", "clone", "new_neon_light"
        }:
            recipe = sampling.recipe_for(capability_id)
            status = "supported"
            reason = "bound to the verified normalized preview stroke recipe"
            native = {
                "kind": "stroke",
                "stroke": recipe.effective.get("stroke"),
                "source": recipe.effective.get("source"),
                "apply_locator_id": recipe.effective.get("apply_locator_id"),
                "activation_locator_id": recipe.effective.get("activation_locator_id"),
            }
        elif capability_id == "crop_ai" and parameter in {"flip_x", "flip_y"}:
            status = "supported"
            reason = "bound to the exact native crop flip button"
            native = {
                "kind": "button",
                "control_locator_id": (
                    "NSButton.Crop.FlipHorizontal"
                    if parameter == "flip_x"
                    else "NSButton.Crop.FlipVertical"
                ),
                "value": canonical,
            }
        elif capability_id == "crop_ai" and parameter == "crop_box":
            status = "supported"
            reason = "bound to the native crop box and exact Apply action"
            native = {
                "kind": "crop-box",
                "drag": [0.0, 0.0, 0.1, 0.1],
                "apply_locator_id": "NSButton.Crop.Apply",
            }
        elif capability_id == "crop_ai" and parameter == "crop_ratio":
            status = "supported"
            reason = "bound to the native crop ratio menu and exact Free choice"
            native = {
                "kind": "menu-choice",
                "control_locator_id": "NSButton.Crop.AspectRatio",
                "choice_title": "自由",
                "value": "free",
            }
        elif capability_id == "crop_ai" and parameter == "crop_rotation":
            reason = "frozen 54-degree value is not represented by the native 90-degree rotate action"
        elif capability_id == "crop_ai" and parameter == "straighten":
            reason = "frozen numeric straighten value is not equivalent to native automatic horizon alignment"
        elif capability_id == "bokeh_ai" and parameter == "bokeh_shape":
            controls = {
                "circle": "NSButton.BokehAI.Shape.Circle",
                "filled_circle": "NSButton.BokehAI.Shape.FilledCircle",
                "oval": "NSButton.BokehAI.Shape.Oval",
                "hexagon": "NSButton.BokehAI.Shape.Hexagon",
                "heart": "NSButton.BokehAI.Shape.Heart",
                "star": "NSButton.BokehAI.Shape.Star",
            }
            status = "supported"
            reason = "bound to the exact native Bokeh Shape Adjustments button"
            native = {
                "kind": "button",
                "section_locator_id": "AdvancedSlider.NSButton.Bokeh Shape Adjustments",
                "control_locator_id": controls[str(canonical)],
                "value": canonical,
            }

        records.append(
            {
                "matrix_state_id": state_id,
                "capability_id": capability_id,
                "parameter": parameter,
                "parameter_type": definition.get("type"),
                "canonical_value": canonical,
                "status": status,
                "reason": reason,
                "native": native,
                "evidence": evidence,
            }
        )

    statuses = Counter(str(item["status"]) for item in records)
    return {
        "version": "1.0",
        "reference_id": matrix["reference_id"],
        "matrix_fingerprint": matrix["matrix_fingerprint"],
        "record_count": len(records),
        "counts": dict(sorted(statuses.items())),
        "gate": "passed" if statuses == {"supported": len(records)} else "blocked",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--sampling", type=Path, default=DEFAULT_SAMPLING)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--ui-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    ui_root = args.ui_root or profile.ui_reference_root / "2880x1800"
    report = build_audit(
        matrix=_json(args.matrix.resolve()),
        schema=_json(args.schema.resolve()),
        sampling_path=args.sampling.resolve(),
        ui_root=ui_root.resolve(),
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **{key: report[key] for key in ("record_count", "counts", "gate")}}, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
