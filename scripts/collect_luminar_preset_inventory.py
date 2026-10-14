"""Collect localized built-in preset names from the full-screen Luminar UI."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.accessibility_driver import (
    AccessibilityNode,
    LuminarAccessibilityDriver,
)
from scripts.luminar_capture.app_controller import LuminarAppController

CATEGORY_LOCALIZATION = {
    "Animal Friends": "动物朋友",
    "Artistic": "艺术",
    "Big City Lights": "都市灯光",
    "Big Screen": "大屏幕",
    "Blockbuster": "电影大片",
    "Closeups": "特写",
    "Easy Landscapes": "轻快风景",
    "Easy Portraits": "简单人像",
    "Essence": "本质精髓",
    "Experimental": "实验",
    "Filmatic": "电影效果",
    "Influencer": "影响者",
    "Monochrome": "单色",
    "Natural Skies": "自然天空",
    "Nature": "自然",
    "Objects": "对象",
    "Overcast": "阴天",
    "Savannah": "大草原",
    "Scenery": "风景",
    "Sunsets": "日落",
    "Urban Style": "城市风貌",
    "Waterscapes": "水景",
}


def _wait_for(driver: LuminarAccessibilityDriver, locator: str, timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        nodes = driver.snapshot()
        if driver.has_locator(locator, nodes):
            return nodes
        time.sleep(0.2)
    raise TimeoutError(f"Luminar did not expose preset locator: {locator}")


def _open_presets(
    driver: LuminarAccessibilityDriver, *, timeout: float
) -> tuple[AccessibilityNode, ...]:
    deadline = time.monotonic() + timeout
    retry_at = 0.0
    while time.monotonic() < deadline:
        if time.monotonic() >= retry_at:
            driver.press("NavigationPanel.Tab.Presets")
            retry_at = time.monotonic() + 1.0
        nodes = driver.snapshot()
        if driver.has_locator("对于这张照片", nodes) or driver.has_locator(
            "NSButton.TemplateCollectionDetailViewController.BackButton", nodes
        ):
            return nodes
        time.sleep(0.15)
    raise TimeoutError("Luminar did not open the presets workspace")


def _category_node(
    nodes: tuple[AccessibilityNode, ...], localized_name: str
) -> AccessibilityNode | None:
    candidates = [
        node
        for node in nodes
        if node.identifier == "_NS:59"
        and node.value == localized_name
        and node.position is not None
        and node.size is not None
        and node.size[0] <= 130
    ]
    return max(candidates, key=lambda node: node.position[1], default=None)


def _open_category(
    driver: LuminarAccessibilityDriver,
    localized_name: str,
    *,
    timeout: float,
) -> tuple[AccessibilityNode, ...]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        nodes = driver.snapshot()
        node = _category_node(nodes, localized_name)
        if node is None:
            raise RuntimeError(f"Luminar preset category is absent: {localized_name}")
        assert node.position is not None
        if 180 <= node.position[1] <= 760:
            driver.click_at(node.position[0] + 55, node.position[1] - 55)
            return _wait_for(
                driver,
                "NSButton.TemplateCollectionDetailViewController.BackButton",
                timeout,
            )
        lines = -8 if node.position[1] > 760 else 8
        driver.scroll_at(1212, 700, lines)
        time.sleep(0.15)
    raise TimeoutError(f"Luminar preset category did not become visible: {localized_name}")


def collect(
    presets_path: Path,
    output_path: Path,
    *,
    config_path: Path,
    update_presets: bool,
) -> dict[str, Any]:
    config = load_luminar_sampling_config(config_path)
    payload = json.loads(presets_path.read_text(encoding="utf-8"))
    presets = list(payload.get("presets", []))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    category_order: list[str] = []
    for preset in presets:
        category = str(preset["category"])
        if category not in grouped:
            category_order.append(category)
        grouped[category].append(preset)
    missing = sorted(set(grouped) - set(CATEGORY_LOCALIZATION))
    if missing:
        raise RuntimeError(f"preset category localization is missing: {missing}")

    controller = LuminarAppController(config.app_path)
    driver = LuminarAccessibilityDriver(
        timeout_seconds=config.timeouts.action_seconds
    )
    controller.launch(timeout_seconds=config.timeouts.action_seconds)
    driver.activate()
    controller.enter_full_screen(timeout_seconds=config.timeouts.action_seconds)
    navigation_timeout = config.timeouts.navigation_seconds
    nodes = _open_presets(driver, timeout=navigation_timeout)
    if driver.has_locator(
        "NSButton.TemplateCollectionDetailViewController.BackButton", nodes
    ):
        driver.ax_press("NSButton.TemplateCollectionDetailViewController.BackButton")
    _wait_for(driver, "对于这张照片", navigation_timeout)

    inventory = []
    for category in category_order:
        localized_category = CATEGORY_LOCALIZATION[category]
        detail_nodes = _open_category(
            driver,
            localized_category,
            timeout=navigation_timeout,
        )
        localized_names = [
            str(node.value)
            for node in sorted(
                (
                    node
                    for node in detail_nodes
                    if node.identifier == "_NS:51"
                    and isinstance(node.value, str)
                    and node.position is not None
                ),
                key=lambda node: node.position[1],
            )
        ]
        source_presets = grouped[category]
        if len(localized_names) != len(source_presets):
            raise RuntimeError(
                f"preset count mismatch for {category}: "
                f"{len(localized_names)} != {len(source_presets)}"
            )
        for preset, localized_name in zip(source_presets, localized_names, strict=True):
            preset["localized_name"] = localized_name
            preset["localized_category"] = localized_category
            inventory.append(
                {
                    "id": preset["id"],
                    "name": preset["name"],
                    "localized_name": localized_name,
                    "category": category,
                    "localized_category": localized_category,
                    "access": "built-in-free",
                }
            )
        driver.ax_press("NSButton.TemplateCollectionDetailViewController.BackButton")
        _wait_for(driver, "对于这张照片", navigation_timeout)

    report = {
        "version": "1.0",
        "reference_id": config.reference_id,
        "window_mode": "native-full-screen",
        "paid_content_included": False,
        "category_count": len(category_order),
        "preset_count": len(inventory),
        "presets": inventory,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if update_presets:
        payload["category_localization"] = CATEGORY_LOCALIZATION
        presets_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    active = load_reference_catalog(project_root=ROOT).resolve()
    parser.add_argument(
        "--presets", type=Path, default=ROOT / "configs/presets/free.json"
    )
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/luminar_sampling.yaml"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=active.diagnostics_root / "native-preset-inventory.json",
    )
    parser.add_argument("--update-presets", action="store_true")
    args = parser.parse_args()
    report = collect(
        args.presets.resolve(),
        args.output.resolve(),
        config_path=args.config.resolve(),
        update_presets=args.update_presets,
    )
    print(
        json.dumps(
            {
                "category_count": report["category_count"],
                "preset_count": report["preset_count"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
