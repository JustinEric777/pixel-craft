"""Build deterministic parameter, UI and interaction anchors for exact parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.luminar_capture.attempt_store import write_json_atomic


def _anchors(spec: dict[str, Any]) -> list[Any]:
    if "anchor_values" in spec:
        return list(dict.fromkeys(spec["anchor_values"]))
    if spec.get("type") == "enum":
        return list(spec.get("values", []))
    if spec.get("type") in {"float", "integer"}:
        minimum = spec.get("min")
        maximum = spec.get("max")
        default = spec.get("default")
        values = [default]
        if minimum is not None and maximum is not None:
            values.extend([minimum, maximum])
            if not all(
                key in spec
                for key in ("native_min", "native_max", "native_default")
            ):
                values.insert(2, (float(minimum) + float(maximum)) / 2)
        return list(dict.fromkeys(value for value in values if value is not None))
    if spec.get("type") == "boolean":
        default = bool(spec.get("default", False))
        return [default, not default]
    return [spec.get("default")] if "default" in spec else []


def _native_anchor_value(spec: dict[str, Any], value: Any) -> Any | None:
    """Map one public parameter anchor to its exact observed native readback."""

    for anchor in spec.get("native_anchors", []):
        if anchor.get("value") == value:
            return anchor.get("native_value")
    if spec.get("type") == "boolean":
        return bool(value)
    if value == spec.get("default") and "native_default" in spec:
        return spec["native_default"]
    if value == spec.get("min") and "native_min" in spec:
        return spec["native_min"]
    if value == spec.get("max") and "native_max" in spec:
        return spec["native_max"]
    return None


def _parameter_spec(
    common: dict[str, dict[str, Any]],
    capability: dict[str, Any],
    parameter: str,
) -> dict[str, Any] | None:
    """Resolve the product-specific contract for one capability parameter."""

    shared = common.get(parameter)
    if shared is None:
        return None
    override = (capability.get("parameter_overrides") or {}).get(parameter) or {}
    resolved = {**shared, **override}
    if resolved.get("type") in {"float", "integer"}:
        minimum = resolved.get("min")
        maximum = resolved.get("max")
        default = resolved.get("default")
        if not all(isinstance(value, (int, float)) for value in (minimum, maximum)):
            raise ValueError(f"numeric parameter range is incomplete: {parameter}")
        if float(minimum) > float(maximum):
            raise ValueError(f"numeric parameter range is reversed: {parameter}")
        if isinstance(default, (int, float)) and not (
            float(minimum) <= float(default) <= float(maximum)
        ):
            raise ValueError(f"numeric parameter default is outside range: {parameter}")
        if resolved.get("signed") is False and float(minimum) < 0:
            raise ValueError(f"unipolar parameter has a negative minimum: {parameter}")
    return resolved


def semantic_payload(reference_id: str, record: dict[str, Any]) -> dict[str, Any]:
    parameters = dict(record.get("parameters") or {})
    parameters.pop("asset_id", None)
    source = record.get("input") or {}
    return {
        "reference_id": reference_id,
        "capability_id": record.get("capability_id"),
        "input_sha256": source.get("sha256"),
        "asset_identity": record.get("asset_id") or record.get("asset_sha256"),
        "parameters": parameters,
    }


def semantic_key(reference_id: str, record: dict[str, Any]) -> str:
    encoded = json.dumps(
        semantic_payload(reference_id, record),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _apply_fixture_override(
    schema: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    anchor = record.get("anchor")
    if not isinstance(anchor, dict):
        return record
    for override in schema.get("fixture_overrides", []):
        if override.get("capability_id") != record.get("capability_id"):
            continue
        if override.get("parameter") != anchor.get("parameter"):
            continue
        if anchor.get("value") not in override.get("values", []):
            continue
        fixture = dict(override.get("input") or {})
        fixture_path = Path(str(fixture.get("path", "")))
        if not fixture_path.is_absolute():
            fixture["path"] = str((ROOT / fixture_path).resolve())
        return {**record, "input": fixture}
    return record


def build_matrix(schema_path: Path, cases_path: Path, reference_id: str) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    source_cases = json.loads(cases_path.read_text(encoding="utf-8")).get("cases", [])
    first_case = {
        str(item["capability_id"]): item
        for item in reversed(source_cases)
    }
    common = schema["common_parameters"]
    generated_records = []
    for capability_id, capability in schema["capabilities"].items():
        source = first_case.get(capability_id)
        if source is None:
            continue
        defaults = {}
        for name in capability.get("parameters", []):
            spec = _parameter_spec(common, capability, name)
            if spec is not None and "default" in spec:
                defaults[name] = spec["default"]
        source_asset_id = source.get("asset_id") or (
            source.get("parameters") or {}
        ).get("asset_id")
        base_record = {
            "capability_id": capability_id,
            "input": source.get("input"),
            "asset_id": source_asset_id,
            "asset_sha256": source.get("asset_sha256"),
        }
        generated_records.append(
            {
                "id": f"exact:{capability_id}:defaults",
                **base_record,
                "parameters": defaults,
                "anchor": "defaults",
                **(
                    {
                        "native_parameter_binding": {
                            "parameter": "asset_id",
                            "value": source_asset_id,
                            "value_space": "asset-id",
                        }
                    }
                    if capability_id == "sky_replace" and source_asset_id
                    else {}
                ),
            }
        )
        for parameter in capability.get("parameters", []):
            spec = _parameter_spec(common, capability, parameter)
            if not spec or spec.get("type") in {"asset", "array"}:
                continue
            for index, value in enumerate(_anchors(spec)):
                native_value = _native_anchor_value(spec, value)
                generated_records.append(
                    _apply_fixture_override(schema, {
                        "id": f"exact:{capability_id}:{parameter}:{index}",
                        **base_record,
                        "parameters": {**defaults, parameter: value},
                        "anchor": {"parameter": parameter, "value": value},
                        **(
                            {
                                "native_parameter_binding": {
                                    "parameter": parameter,
                                    "value": native_value,
                                    "value_space": "native",
                                }
                            }
                            if native_value is not None
                            else {}
                        ),
                    })
                )
    invalid = []
    unique: dict[str, dict[str, Any]] = {}
    for record in generated_records:
        if not (record.get("input") or {}).get("sha256"):
            invalid.append({"id": record["id"], "reason": "input-sha256-missing"})
            continue
        capability = schema["capabilities"][record["capability_id"]]
        asset_required = any(
            common.get(name, {}).get("type") == "asset"
            for name in capability.get("parameters", [])
        )
        if asset_required and not record.get("asset_id"):
            invalid.append({"id": record["id"], "reason": "asset-id-missing"})
            continue
        key = semantic_key(reference_id, record)
        if key in unique:
            existing = unique[key]
            if "anchors" not in existing:
                existing["anchors"] = [existing.pop("anchor")]
            existing["anchors"].append(record["anchor"])
            continue
        unique[key] = {**record, "semantic_key": key}
    if invalid:
        detail = ", ".join(f"{item['id']}:{item['reason']}" for item in invalid[:5])
        raise ValueError(f"exact matrix contains invalid records: {detail}")
    records = sorted(unique.values(), key=lambda item: item["semantic_key"])
    interactions = [
        "catalog-import-select",
        "preset-preview-apply",
        "edit-slider-drag",
        "edit-toggle-collapse",
        "layer-add-reorder-opacity-delete",
        "undo-redo",
        "before-after-compare",
        "zoom-pan",
        "export-dialog",
        "multi-image-workflow",
    ]
    fingerprint_payload = {
        "reference_id": reference_id,
        "semantic_keys": [record["semantic_key"] for record in records],
        "interactions": interactions,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "version": "1.0",
        "reference_id": reference_id,
        "profile": "exact",
        "matrix_fingerprint": fingerprint,
        "generated_effect_case_count": len(generated_records),
        "effect_case_count": len(records),
        "duplicate_semantic_count": len(generated_records) - len(records),
        "invalid_count": len(invalid),
        "interaction_case_count": len(interactions),
        "records": records,
        "interactions": interactions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=ROOT / "configs/capabilities/parameter-schema.json")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--reference-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_matrix(
        args.schema.resolve(), args.cases.resolve(), args.reference_id
    )
    write_json_atomic(args.output.resolve(), report)
    print(json.dumps({key: report[key] for key in ("reference_id", "matrix_fingerprint", "effect_case_count", "interaction_case_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
