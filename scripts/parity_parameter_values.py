"""Canonical current-only parameter values shared by UI capture builders."""

from __future__ import annotations

from typing import Any


def effective_parameter_definition(
    schema: dict[str, Any], capability_id: str, parameter: str
) -> dict[str, Any]:
    """Merge a common definition with one capability's explicit overrides."""

    common = schema.get("common_parameters", {}).get(parameter)
    if not isinstance(common, dict):
        raise TypeError(f"parameter has no common definition: {capability_id}.{parameter}")
    capability = schema.get("capabilities", {}).get(capability_id, {})
    overrides = capability.get("parameter_overrides", {}).get(parameter, {})
    if not isinstance(overrides, dict):
        raise TypeError(f"parameter override must be an object: {capability_id}.{parameter}")
    return {**common, **overrides}


def canonical_parameter_value(parameter: str, definition: dict[str, Any]) -> Any:
    """Return one deterministic non-default value for a parameter state."""

    parameter_type = definition.get("type")
    default = definition.get("default")
    if parameter_type == "float":
        minimum = float(definition["min"])
        maximum = float(definition["max"])
        candidate = minimum + (maximum - minimum) * 0.65
        if abs(candidate - float(default)) < 1e-9:
            candidate = minimum + (maximum - minimum) * 0.35
        return round(candidate, 6)
    if parameter_type == "enum":
        values = definition.get("values")
        if not isinstance(values, list) or not values:
            raise ValueError(f"enum parameter has no values: {parameter}")
        return next((value for value in values if value != default), values[0])
    if parameter_type == "boolean":
        return not bool(default)
    if parameter_type == "asset":
        return "fixture:canonical-asset"
    if parameter_type == "array":
        if parameter == "crop_box":
            return [0.1, 0.1, 0.8, 0.8]
        if parameter == "strokes":
            return [{"x": 0.5, "y": 0.5, "radius": 0.05, "strength": 1.0}]
        raise ValueError(f"array parameter has no explicit recipe: {parameter}")
    raise ValueError(f"unsupported parameter type for {parameter}: {parameter_type}")
