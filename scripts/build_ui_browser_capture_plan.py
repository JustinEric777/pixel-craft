#!/usr/bin/env python3
"""Build the current-only Browser UI capture plan from the canonical UI matrix."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.parity_parameter_values import (
    canonical_parameter_value,
    effective_parameter_definition,
)

DEFAULT_MATRIX = ROOT / "configs/parity/core-ui-state-matrix.json"
DEFAULT_EDITOR = ROOT / "configs/ui/editor.json"
DEFAULT_SCHEMA = ROOT / "configs/capabilities/parameter-schema.json"
DEFAULT_REGISTRY = ROOT / "configs/capabilities/registry.json"
DEFAULT_OUTPUT = ROOT / "test_data/parity/ui-browser-capture-plan.json"
FIXTURE_FILENAME = "004_60ae06fe1d.jpg"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _catalog_steps() -> list[dict[str, Any]]:
    return [
        {"type": "click-name", "name": "目录"},
        {"type": "wait-for-text", "text": "所有照片", "timeout_ms": 10_000},
    ]


def _edit_steps() -> list[dict[str, Any]]:
    return [
        *_catalog_steps(),
        {
            "type": "double-click-text",
            "selector": ".photo-card-name",
            "text": FIXTURE_FILENAME,
        },
        {"type": "wait-for-selector", "selector": ".workspace-edit", "timeout_ms": 30_000},
    ]


def _workspace_recipes() -> dict[str, list[dict[str, Any]]]:
    edit = _edit_steps()
    catalog = _catalog_steps()
    return {
        "workspace:catalog": catalog,
        "workspace:presets": [
            *edit,
            {"type": "click-name", "name": "预设"},
            {"type": "wait-for-text", "text": "城市灯光", "timeout_ms": 30_000},
        ],
        "workspace:edit": edit,
        "workspace:layer-stack": edit,
        "workspace:layer-library": [
            *edit,
            {"type": "click-name", "name": "添加图层"},
            {"type": "wait-for-text", "text": "添加本地素材", "timeout_ms": 10_000},
        ],
        "workspace:tool-expanded": [
            *edit,
            {
                "type": "show-tool",
                "capability_id": "bw_channels",
                "expanded": True,
                "locator": '[data-capability-id="bw_channels"]',
            },
            {"type": "wait-for-text", "text": "转换为黑白", "timeout_ms": 10_000},
        ],
        "workspace:edit-history": [
            *edit,
            {"type": "click-name", "name": "编辑"},
            {"type": "wait-for-text", "text": "没有编辑", "timeout_ms": 10_000},
        ],
        "workspace:more-panel": [
            *edit,
            {"type": "click-name", "name": "更多"},
            {"type": "wait-for-text", "text": "合并工具", "timeout_ms": 10_000},
        ],
        "workspace:info-panel": [
            *edit,
            {"type": "click-name", "name": "信息"},
            {"type": "wait-for-text", "text": "影像资讯", "timeout_ms": 10_000},
        ],
        "workspace:edit-collapsed": [*edit, {"type": "click-name", "name": "工具"}],
        "workspace:black-white-before-conversion": [
            *edit,
            {
                "type": "show-tool",
                "capability_id": "bw_channels",
                "expanded": True,
                "locator": '[data-capability-id="bw_channels"]',
            },
            {"type": "wait-for-text", "text": "转换为黑白", "timeout_ms": 10_000},
        ],
        "workspace:black-white-after-conversion": [
            *edit,
            {
                "type": "show-tool",
                "capability_id": "bw_channels",
                "expanded": True,
                "locator": '[data-capability-id="bw_channels"]',
            },
            {"type": "wait-for-text", "text": "转换为黑白", "timeout_ms": 10_000},
            {"type": "click-name", "name": "转换为黑白"},
            {"type": "wait-for-text", "text": "已转换为黑白", "timeout_ms": 10_000},
        ],
        "workspace:denoise-level-selected": [
            *edit,
            {
                "type": "show-tool",
                "capability_id": "denoise",
                "expanded": True,
                "locator": '[data-capability-id="denoise"]',
            },
            {
                "type": "change-parameter",
                "capability_id": "denoise",
                "parameter": "denoise_level",
                "parameter_type": "enum",
                "value": "high",
                "locator": '[data-capability-id="denoise"] [data-parameter-id="denoise_level"]',
            },
        ],
        "workspace:export-dialog": [
            *edit,
            {"type": "click-name", "name": "导出"},
            {"type": "wait-for-text", "text": "颜色配置", "timeout_ms": 10_000},
        ],
        "workspace:multi-image": [
            *catalog,
            {"type": "click-name", "name": "HDR Merge"},
            {"type": "wait-for-text", "text": "为 HDR 合并选择照片", "timeout_ms": 10_000},
        ],
        "workspace:multi-image-complete": [
            *catalog,
            {"type": "click-name", "name": "HDR Merge"},
            {
                "type": "set-files",
                "selector": ".workflow-empty-picker input[type=file]",
                "files": [
                    "test_data/multi_image/hdr_merge/frame-1-brightness-0.5.jpg",
                    "test_data/multi_image/hdr_merge/frame-2-brightness-1.0.jpg",
                    "test_data/multi_image/hdr_merge/frame-3-brightness-1.5.jpg",
                ],
            },
            {"type": "wait-for-text", "text": "3 张照片", "timeout_ms": 10_000},
            {"type": "click-name", "name": "合并"},
            {"type": "wait-for-text", "text": "预览", "timeout_ms": 120_000},
        ],
    }


def build_plan(
    matrix: dict[str, Any],
    editor: dict[str, Any],
    schema: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    records = matrix.get("records")
    if not isinstance(records, list) or len(records) != 170:
        raise ValueError("current UI matrix must contain exactly 170 records")
    if matrix.get("reference_id") != editor.get("reference_id"):
        raise ValueError("UI matrix/editor reference_id mismatch")

    grouped_capabilities = {
        capability_id
        for group in editor.get("tool_groups", [])
        for capability_id in group.get("capabilities", [])
    }
    titles = {
        item["id"]: item["title"]
        for item in registry.get("capabilities", [])
        if item.get("id") in grouped_capabilities
    }
    workspace_recipes = _workspace_recipes()
    plan_records: list[dict[str, Any]] = []

    for record in records:
        matrix_state_id = record.get("id")
        kind = record.get("kind")
        if kind == "workspace-state":
            steps = workspace_recipes.get(matrix_state_id)
            if steps is None:
                raise ValueError(f"workspace state has no explicit recipe: {matrix_state_id}")
        elif kind == "tool-panel-state":
            capability_id = record.get("capability_id")
            if capability_id not in titles:
                raise ValueError(f"tool state has no current editor title: {matrix_state_id}")
            expanded = matrix_state_id.endswith(":expanded")
            steps = [
                *_edit_steps(),
                {
                    "type": "show-tool",
                    "capability_id": capability_id,
                    "title": titles[capability_id],
                    "expanded": expanded,
                    "locator": f'[data-capability-id="{capability_id}"]',
                },
            ]
        elif kind == "tool-parameter-state":
            capability_id = record.get("capability_id")
            parameter = record.get("parameter")
            definition = effective_parameter_definition(schema, capability_id, parameter)
            if capability_id not in titles:
                raise ValueError(f"parameter state has no current editor title: {matrix_state_id}")
            steps = [
                *_edit_steps(),
                {
                    "type": "show-tool",
                    "capability_id": capability_id,
                    "title": titles[capability_id],
                    "expanded": True,
                    "locator": f'[data-capability-id="{capability_id}"]',
                },
                {
                    "type": "change-parameter",
                    "capability_id": capability_id,
                    "parameter": parameter,
                    "parameter_type": definition.get("type"),
                    "value": canonical_parameter_value(parameter, definition),
                    "locator": (
                        f'[data-capability-id="{capability_id}"] '
                        f'[data-parameter-id="{parameter}"]'
                    ),
                },
            ]
        else:
            raise ValueError(f"unsupported UI matrix kind: {kind}")
        plan_records.append(
            {
                "matrix_state_id": matrix_state_id,
                "kind": kind,
                "url": "http://127.0.0.1:5175",
                "steps": deepcopy(steps),
            }
        )

    ids = [record["matrix_state_id"] for record in plan_records]
    if len(ids) != len(set(ids)) or set(ids) != {record["id"] for record in records}:
        raise ValueError("capture plan does not match the current UI matrix IDs exactly")
    return {
        "version": "3.0",
        "reference_id": matrix["reference_id"],
        "matrix_fingerprint": matrix["matrix_fingerprint"],
        "base_url": "http://127.0.0.1:5175",
        "logical_viewport": [1440, 900],
        "device_scale_factor": 2,
        "physical_viewport": [2880, 1800],
        "locale": "zh-Hans",
        "timezone": "Asia/Shanghai",
        "settle_ms": 250,
        "records": plan_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = build_plan(
        _read_json(args.matrix),
        _read_json(args.editor),
        _read_json(args.schema),
        _read_json(args.registry),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "reference_id": plan["reference_id"],
                "matrix_fingerprint": plan["matrix_fingerprint"],
                "records": len(plan["records"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
