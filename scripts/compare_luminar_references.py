"""Compare two versioned Luminar installation inventories without executing either app."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _model_index(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item["logical_model_id"]), str(item["format"])): item
        for item in payload.get("model_variants", [])
    }


def _preset_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in payload.get("presets", [])}


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _preset_graph_hash(item: dict[str, Any]) -> str:
    return _stable_hash(item.get("edit_graph", []))


def _ui_inventory(payload: dict[str, Any]) -> dict[str, list[str]]:
    groups = payload.get("tool_groups", [])
    tool_ids = [
        str(tool)
        for group in groups
        for tool in group.get("tools", [])
        if tool
    ]
    sky = payload.get("tools", {}).get("sky_replace", {})
    return {
        "group_ids": [str(group.get("id")) for group in groups],
        "tool_ids": tool_ids,
        "sky_parameter_ids": sorted(str(key) for key in sky.get("parameters", {})),
    }


def compare(
    baseline_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    *,
    baseline_presets: dict[str, Any] | None = None,
    candidate_presets: dict[str, Any] | None = None,
    baseline_ui: dict[str, Any] | None = None,
    candidate_ui: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline_models = _model_index(baseline_manifest)
    candidate_models = _model_index(candidate_manifest)
    shared_models = sorted(baseline_models.keys() & candidate_models.keys())
    model_hash_matches = [
        key
        for key in shared_models
        if baseline_models[key].get("sha256") == candidate_models[key].get("sha256")
    ]
    baseline_preset_index = _preset_index(baseline_presets or {})
    candidate_preset_index = _preset_index(candidate_presets or {})
    shared_presets = sorted(baseline_preset_index.keys() & candidate_preset_index.keys())
    matching_preset_graphs = [
        preset_id
        for preset_id in shared_presets
        if _preset_graph_hash(baseline_preset_index[preset_id])
        == _preset_graph_hash(candidate_preset_index[preset_id])
    ]
    baseline_ui_inventory = _ui_inventory(baseline_ui or {})
    candidate_ui_inventory = _ui_inventory(candidate_ui or {})
    return {
        "version": "1.0",
        "generated_by": "scripts/compare_luminar_references.py",
        "baseline_reference_id": baseline_manifest.get("reference_build", {}).get("id"),
        "candidate_reference_id": candidate_manifest.get("reference_build", {}).get("id"),
        "models": {
            "baseline_count": len(baseline_models),
            "candidate_count": len(candidate_models),
            "shared_count": len(shared_models),
            "shared_hash_match_count": len(model_hash_matches),
            "candidate_only": [
                {"logical_model_id": key[0], "format": key[1]}
                for key in sorted(candidate_models.keys() - baseline_models.keys())
            ],
            "baseline_only": [
                {"logical_model_id": key[0], "format": key[1]}
                for key in sorted(baseline_models.keys() - candidate_models.keys())
            ],
            "shared_hash_mismatches": [
                {"logical_model_id": key[0], "format": key[1]}
                for key in shared_models
                if key not in model_hash_matches
            ],
        },
        "presets": {
            "baseline_count": len(baseline_preset_index),
            "candidate_count": len(candidate_preset_index),
            "shared_count": len(shared_presets),
            "matching_graph_count": len(matching_preset_graphs),
            "candidate_only": sorted(candidate_preset_index.keys() - baseline_preset_index.keys()),
            "baseline_only": sorted(baseline_preset_index.keys() - candidate_preset_index.keys()),
        },
        "ui": {
            "baseline": baseline_ui_inventory,
            "candidate": candidate_ui_inventory,
            "same_group_ids": baseline_ui_inventory["group_ids"]
            == candidate_ui_inventory["group_ids"],
            "same_tool_ids": baseline_ui_inventory["tool_ids"]
            == candidate_ui_inventory["tool_ids"],
            "same_sky_parameter_ids": baseline_ui_inventory["sky_parameter_ids"]
            == candidate_ui_inventory["sky_parameter_ids"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--baseline-presets", type=Path)
    parser.add_argument("--candidate-presets", type=Path)
    parser.add_argument("--baseline-ui", type=Path)
    parser.add_argument("--candidate-ui", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(
        _load(args.baseline_manifest),
        _load(args.candidate_manifest),
        baseline_presets=_load(args.baseline_presets),
        candidate_presets=_load(args.candidate_presets),
        baseline_ui=_load(args.baseline_ui),
        candidate_ui=_load(args.candidate_ui),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
