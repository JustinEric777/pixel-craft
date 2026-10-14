"""Import built-in preset graphs from the selected local Luminar reference."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.luminar_capture.app_controller import LuminarAppController
from scripts.luminar_install_inspector import RESOURCE_RELATIVE

DEFAULT_APP = Path("/Applications/Luminar Neo.app")


def _enabled(value: Any) -> bool:
    return str(value).strip().lower() not in {"0", "false", "no"}


def _different(value: Any, default: Any) -> bool:
    try:
        return not math.isclose(float(value), float(default), abs_tol=1e-9)
    except (TypeError, ValueError):
        return str(value) != str(default)


def _has_optional_data(parameter: dict[str, Any]) -> bool:
    return parameter.get("opt_data_type") not in {None, 0, "0"} or parameter.get(
        "opt_data_value"
    ) not in {None, 0, "0", ""}


def _active_effects(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten every active edit up to Luminar's current edit cursor.

    ``curr_edit_inedx`` is a cursor into the cumulative edit stack, not the
    single edit that represents the preset. Importing only that entry silently
    discarded the RAW/develop, curve, portrait, structure, and color stages.
    """
    effects: list[dict[str, Any]] = []
    for layer_index, layer in enumerate(payload.get("layers_array", [])):
        if not _enabled(layer.get("alive", True)) or not _enabled(
            layer.get("enabled", True)
        ):
            continue
        edits = layer.get("edits_array", [])
        if not edits:
            continue
        index = min(max(int(layer.get("curr_edit_inedx", len(edits) - 1)), 0), len(edits) - 1)
        for edit_index, edit in enumerate(edits[: index + 1]):
            if not _enabled(edit.get("enabled", True)):
                continue
            for effect in edit.get("effects_array", []):
                parameters = []
                for parameter in effect.get("params_array", []):
                    if not _different(
                        parameter.get("value"), parameter.get("default")
                    ) and not _has_optional_data(parameter):
                        continue
                    parameters.append(
                        {
                            key: parameter[key]
                            for key in (
                                "name",
                                "value",
                                "default",
                                "min",
                                "max",
                                "normalized_value",
                                "opt_data_type",
                                "opt_data_value",
                            )
                            if key in parameter
                        }
                    )
                if parameters:
                    effects.append(
                        {
                            "id": str(effect["id"]),
                            "parameters": parameters,
                            "source": {
                                "layer_index": layer_index,
                                "edit_index": edit_index,
                                "tool_name": str(edit.get("tool_name") or ""),
                                "blend_mode": edit.get("blend_mode"),
                                "permanent": _enabled(edit.get("permanent", False)),
                            },
                        }
                    )
    return effects


def build(
    resources: Path,
    *,
    reference_id: str = "unversioned-local-reference",
    app_version: str = "unknown",
    app_build: str = "unknown",
) -> dict[str, Any]:
    collections_root = resources / "TemplatePacks/Collections"
    records: list[dict[str, Any]] = []
    for collection_path in sorted(collections_root.glob("*/config.json")):
        collection = json.loads(collection_path.read_text(encoding="utf-8"))
        collection_name = str(collection.get("name") or collection_path.parent.name)
        for package_name in collection.get("templates", []):
            preset_path = collection_path.parent / str(package_name) / "template.lmps"
            if not preset_path.is_file():
                continue
            preset = json.loads(preset_path.read_text(encoding="utf-8"))
            effects = _active_effects(preset)
            if not effects:
                continue
            preset_id = str(preset.get("uuid") or preset_path.parent.stem).lower()
            records.append(
                {
                    "id": f"luminar_{preset_id}",
                    "name": str(preset.get("name") or preset_path.parent.stem),
                    "category": collection_name,
                    "status": "complete-source-graph-imported",
                    "source": {
                        "product": "Luminar Neo",
                        "version": app_version,
                        "build": app_build,
                        "uuid": str(preset.get("uuid") or ""),
                    },
                    "edit_graph": [
                        {
                            "effect": "luminar_preset",
                            "parameters": {
                                "source_effects": effects,
                                "opacity": 1.0,
                            },
                        }
                    ],
                }
            )
    return {
        "version": f"{app_version}-{app_build}",
        "reference_id": reference_id,
        "source": "Luminar Neo local built-in collections",
        "presets": records,
    }


def preserve_localization(
    payload: dict[str, Any], existing: dict[str, Any]
) -> dict[str, Any]:
    """Carry UI-only localized labels across a graph/provenance refresh."""

    localized = {
        str(record.get("id")): record
        for record in existing.get("presets", [])
        if isinstance(record, dict) and record.get("id")
    }
    for record in payload.get("presets", []):
        previous = localized.get(str(record.get("id")))
        if previous is None:
            continue
        for field in ("localized_name", "localized_category"):
            if previous.get(field):
                record[field] = previous[field]
    if isinstance(existing.get("category_localization"), dict):
        payload["category_localization"] = existing["category_localization"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--resources", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "configs/presets/free.json")
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    controller = LuminarAppController(args.app)
    profile.validate_app_version(controller.version())
    resources = (args.resources or args.app / RESOURCE_RELATIVE).resolve()
    payload = build(
        resources,
        reference_id=profile.id,
        app_version=profile.version,
        app_build=profile.build,
    )
    if args.output.is_file():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        preserve_localization(payload, existing)
    if not payload["presets"]:
        raise RuntimeError(f"no built-in presets found under {resources}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"presets": len(payload["presets"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
