"""Capability policy and parameter validation independent of HTTP."""

from __future__ import annotations

from typing import Any

from .errors import ParameterValidationError, UnknownCapabilityError


class CapabilitySchema:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.capabilities = payload.get("capabilities", {})
        self.common = payload.get("common_parameters", {})

    def require_capability(self, effect: str) -> dict[str, Any]:
        try:
            return self.capabilities[effect]
        except KeyError as exc:
            raise UnknownCapabilityError(f"unknown capability: {effect}") from exc

    def validate(self, effect: str, parameters: dict[str, Any]) -> dict[str, Any]:
        capability = self.require_capability(effect)
        declared = set(capability.get("parameters", [])) | set(
            capability.get("internal_parameters", [])
        )
        allowed = declared | {
            "asset_id",
            "asset_path",
            "texture_opacity",
            "texture_mode",
            "texture_offset_y",
            "sky_scale",
            "horizon_offset",
            "vertical_offset",
            "horizontal_offset",
            "sky_flip",
            "edge_refinement",
            "fix_gaps",
            "sky_global",
            "foreground_relight",
            "relight_saturation",
            "relight_human",
            "reflection_amount",
            "reflection_blur",
            "sky_blur",
            "sky_grain",
            "atmospheric_haze",
            "temperature",
            "brightness",
        }
        unknown = sorted(set(parameters) - allowed)
        if unknown:
            raise ParameterValidationError(
                f"unsupported parameters for {effect}: {', '.join(unknown)}"
            )
        result = dict(parameters)
        for name in declared:
            if name not in result:
                continue
            definition = self.common.get(name, {})
            value = result[name]
            if definition.get("type") == "float":
                if isinstance(value, bool) or not isinstance(value, (float, int)):
                    raise ParameterValidationError(f"{name} must be a number")
                value = float(value)
                if "min" in definition and value < definition["min"]:
                    raise ParameterValidationError(f"{name} must be >= {definition['min']}")
                if "max" in definition and value > definition["max"]:
                    raise ParameterValidationError(f"{name} must be <= {definition['max']}")
                result[name] = value
            elif definition.get("type") == "enum" and value not in definition.get("values", []):
                raise ParameterValidationError(f"{name} must be one of {definition['values']}")
            elif definition.get("type") == "array" and not isinstance(value, list):
                raise ParameterValidationError(f"{name} must be an array")
            elif definition.get("type") == "boolean" and not isinstance(value, bool):
                raise ParameterValidationError(f"{name} must be a boolean")
        if "crop_box" in result:
            crop_box = result["crop_box"]
            if (
                not isinstance(crop_box, list)
                or len(crop_box) != 4
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in crop_box)
            ):
                raise ParameterValidationError("crop_box must be [left, top, right, bottom]")
            left, top, right, bottom = (float(value) for value in crop_box)
            if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
                raise ParameterValidationError("crop_box must be normalized and non-empty")
            result["crop_box"] = [left, top, right, bottom]
        if "texture_opacity" in result:
            value = result["texture_opacity"]
            if not isinstance(value, (float, int)) or not 0 <= value <= 1:
                raise ParameterValidationError("texture_opacity must be between 0 and 1")
        if "texture_mode" in result and result["texture_mode"] not in {
            "screen",
            "multiply",
            "replace",
        }:
            raise ParameterValidationError("texture_mode must be screen, multiply or replace")
        if "texture_offset_y" in result and not isinstance(
            result["texture_offset_y"], (float, int)
        ):
            raise ParameterValidationError("texture_offset_y must be a number")
        if "strokes" in result:
            self._validate_strokes(result["strokes"])
        return result

    @staticmethod
    def _validate_strokes(strokes: Any) -> None:
        if not isinstance(strokes, list) or len(strokes) > 128:
            raise ParameterValidationError("strokes must contain at most 128 strokes")
        for stroke in strokes:
            if not isinstance(stroke, dict):
                raise ParameterValidationError("each stroke must be an object")
            points = stroke.get("points")
            if not isinstance(points, list) or not points or len(points) > 4096:
                raise ParameterValidationError("stroke points must contain 1 to 4096 points")
            for point in points:
                CapabilitySchema._validate_point(point, "stroke point")
            source = stroke.get("source")
            if source is not None:
                CapabilitySchema._validate_point(source, "clone source")
            radius = stroke.get("radius", 0.04)
            if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not 0.001 <= radius <= 0.25:
                raise ParameterValidationError("stroke radius must be between 0.001 and 0.25")

    @staticmethod
    def _validate_point(point: Any, label: str) -> None:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point)
            or any(not 0.0 <= float(value) <= 1.0 for value in point)
        ):
            raise ParameterValidationError(f"{label} must be normalized [x, y]")
