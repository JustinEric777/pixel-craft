"""Build the current UI comparison-region contract from verified Native evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.ui_regions import content_sha256, sha256_file


def _matches(node: dict[str, Any], selector: dict[str, Any]) -> bool:
    return all(node.get(key) == value for key, value in selector.items())


def _has_selector(nodes: list[dict[str, Any]], selector: dict[str, Any]) -> bool:
    return any(_matches(node, selector) for node in nodes)


def _scaled_node_bounds(
    nodes: list[dict[str, Any]],
    selector: dict[str, Any],
    *,
    viewport: tuple[int, int],
) -> list[int] | None:
    candidates = [node for node in nodes if _matches(node, selector)]
    for node in candidates:
        position = node.get("position")
        size = node.get("size")
        if (
            isinstance(position, list)
            and len(position) == 2
            and isinstance(size, list)
            and len(size) == 2
            and all(isinstance(value, (int, float)) for value in position + size)
            and size[0] > 0
            and size[1] > 0
        ):
            # Luminar AX coordinates are macOS logical points. The frozen Native
            # references are physical-pixel screenshots on a 2x Retina display.
            scale = viewport[0] / 1440
            return [round(value * scale) for value in (*position, *size)]
    return None


def _exclusions(
    state: str,
    nodes: list[dict[str, Any]],
    *,
    viewport: tuple[int, int],
) -> list[dict[str, Any]]:
    exclusions: list[dict[str, Any]] = []
    help_selector = {"identifier": "NavigationPanel.Tab.Help"}
    help_bounds = _scaled_node_bounds(nodes, help_selector, viewport=viewport)
    if help_bounds is not None:
        exclusions.append(
            {
                "id": "help",
                "bounds": help_bounds,
                "native_ax_selector": help_selector,
                "scope_reason": "用户明确排除帮助功能。",
            }
        )

    if state in {
        "workspace:catalog",
        "workspace:multi-image",
        "workspace:multi-image-complete",
    }:
        tutorial_selector = {"description": "教程"}
        tutorial_bounds = _scaled_node_bounds(
            nodes, tutorial_selector, viewport=viewport
        )
        if tutorial_bounds is not None:
            exclusions.insert(
                0,
                {
                    "id": "tutorial",
                    "bounds": tutorial_bounds,
                    "native_ax_selector": tutorial_selector,
                    "scope_reason": "用户明确排除教程功能。",
                },
            )

    if state == "workspace:presets":
        purchased_selector = {"value": "已购买"}
        promotion_selector = {"value": "新品上市"}
        if not _has_selector(nodes, purchased_selector) or not _has_selector(
            nodes, promotion_selector
        ):
            raise ValueError("preset reference is missing the frozen store selectors")
        exclusions[0:0] = [
            {
                "id": "purchased-entry",
                "bounds": [2120, 562, 602, 106],
                "native_ax_selector": purchased_selector,
                "scope_reason": (
                    "用户明确排除付费相关入口；仅排除 Native AX 标识的已购买标题栏。"
                ),
            },
            {
                "id": "market-promotion",
                "bounds": [2148, 1152, 542, 648],
                "native_ax_selector": promotion_selector,
                "scope_reason": (
                    "用户明确排除商店和推广；该区域由 Native AX 的新品上市标题及"
                    "可见购物车卡片界定。"
                ),
            },
        ]

    if state == "workspace:export-dialog":
        icloud_selector = {"value": "iCloud云盘"}
        if not _has_selector(nodes, icloud_selector):
            raise ValueError("export reference is missing the frozen iCloud selector")
        exclusions.append(
            {
                "id": "icloud-sidebar-row",
                "bounds": [672, 352, 262, 42],
                "native_ax_selector": icloud_selector,
                "scope_reason": (
                    "用户明确排除云功能；本地文件名、格式、尺寸、色彩空间和保存操作"
                    "仍全部纳入。"
                ),
            }
        )
    return exclusions


def build(
    *,
    matrix: dict[str, Any],
    reference_manifest: dict[str, Any],
    reference_root: Path,
) -> dict[str, Any]:
    all_matrix_ids = [
        str(record["id"])
        for record in matrix.get("records", [])
        if isinstance(record, dict) and record.get("id")
    ]
    matrix_ids = [
        str(record["id"])
        for record in matrix.get("records", [])
        if isinstance(record, dict)
        and record.get("id")
        and record.get("comparison_mode", "pixel") == "pixel"
    ]
    if len(all_matrix_ids) != len(set(all_matrix_ids)):
        raise ValueError("UI matrix contains duplicate state IDs")
    reference_records = {
        str(record["matrix_state_id"]): record
        for record in reference_manifest.get("records", [])
        if isinstance(record, dict) and record.get("matrix_state_id")
    }
    if set(reference_records) != set(all_matrix_ids):
        missing = sorted(set(all_matrix_ids) - set(reference_records))
        unexpected = sorted(set(reference_records) - set(all_matrix_ids))
        raise ValueError(
            f"Native reference manifest does not match the UI matrix: "
            f"missing={missing}, unexpected={unexpected}"
        )

    records: list[dict[str, Any]] = []
    for state in matrix_ids:
        reference = reference_records[state]
        if reference.get("status") != "verified" or reference.get("issues"):
            raise ValueError(f"Native reference is not verified: {state}")
        viewport_value = reference.get("viewport")
        if not isinstance(viewport_value, list) or len(viewport_value) != 2:
            raise ValueError(f"Native reference has an invalid viewport: {state}")
        viewport = (int(viewport_value[0]), int(viewport_value[1]))
        relative_ax = Path(str(reference.get("accessibility_tree") or ""))
        ax_path = (reference_root / relative_ax).resolve()
        ax_path.relative_to(reference_root.resolve())
        if not ax_path.is_file():
            raise FileNotFoundError(ax_path)
        if sha256_file(ax_path) != reference.get("accessibility_tree_sha256"):
            raise ValueError(f"Native AX hash does not match its manifest: {state}")
        ax_payload = json.loads(ax_path.read_text(encoding="utf-8"))
        nodes = [
            node for node in ax_payload.get("nodes", []) if isinstance(node, dict)
        ]
        records.append(
            {
                "state": state,
                "viewport": list(viewport),
                "reference_ax": relative_ax.as_posix(),
                "reference_ax_sha256": sha256_file(ax_path),
                "include": [[0, 0, *viewport]],
                "exclude": _exclusions(state, nodes, viewport=viewport),
            }
        )

    payload: dict[str, Any] = {
        "version": "2.0",
        "reference_id": reference_manifest.get("reference_id"),
        "matrix_fingerprint": matrix.get("matrix_fingerprint"),
        "coordinate_space": "physical-pixels",
        "records": records,
    }
    payload["content_sha256"] = content_sha256(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix", type=Path, default=ROOT / "configs/parity/core-ui-state-matrix.json"
    )
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "configs/parity/ui-regions.json"
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    reference_root = (args.reference_root or profile.ui_reference_root).resolve()
    reference_manifest = args.reference_manifest or reference_root / "reference-manifest.json"
    payload = build(
        matrix=json.loads(args.matrix.read_text(encoding="utf-8")),
        reference_manifest=json.loads(
            reference_manifest.read_text(encoding="utf-8")
        ),
        reference_root=reference_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "record_count": len(payload["records"]),
                "content_sha256": payload["content_sha256"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
