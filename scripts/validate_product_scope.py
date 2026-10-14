"""Validate the published free-only UI scope and excluded product controls."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog

FORBIDDEN_UI_PATTERNS = {
    "可用更新": re.compile("可用更新"),
    "付费": re.compile("付费"),
    # Luminar labels locally available collections as “已购买”. Keep that
    # read-only native state while rejecting purchase calls to action.
    "购买": re.compile(r"(?<!已)购买"),
    "订阅": re.compile("订阅"),
}
FORBIDDEN_CAPABILITY_GROUPS = {"generative"}


def run(
    ui_path: Path,
    preset_path: Path,
    cases_path: Path,
    frontend_root: Path,
) -> dict[str, Any]:
    ui = json.loads(ui_path.read_text(encoding="utf-8"))
    presets = json.loads(preset_path.read_text(encoding="utf-8"))
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    visible_ids = [
        str(capability_id)
        for group in ui.get("tool_groups", [])
        for capability_id in group.get("capabilities", [])
    ]
    visible_ids.extend(
        str(item["capability_id"])
        for item in ui.get("catalog_actions", [])
        if item.get("capability_id")
    )
    case_ids = {str(item.get("capability_id")) for item in cases.get("cases", [])}
    forbidden_groups = sorted(
        str(group.get("id"))
        for group in ui.get("tool_groups", [])
        if str(group.get("id")) in FORBIDDEN_CAPABILITY_GROUPS
    )
    invalid_presets = sorted(
        str(item.get("id"))
        for item in presets.get("presets", [])
        if item.get("paid") or item.get("requires_purchase") or item.get("subscription")
    )
    forbidden_ui_hits: list[str] = []
    for source in sorted(frontend_root.rglob("*.tsx")):
        if source.name.endswith(".test.tsx"):
            continue
        text = source.read_text(encoding="utf-8")
        for token, pattern in FORBIDDEN_UI_PATTERNS.items():
            if pattern.search(text):
                forbidden_ui_hits.append(f"{source.relative_to(frontend_root)}:{token}")
    issues = {
        "duplicate_visible_capabilities": sorted(
            {item for item in visible_ids if visible_ids.count(item) > 1}
        ),
        "visible_capabilities_without_cases": sorted(set(visible_ids) - case_ids),
        "forbidden_groups": forbidden_groups,
        "invalid_presets": invalid_presets,
        "forbidden_ui_hits": forbidden_ui_hits,
    }
    passed = all(not values for values in issues.values()) and bool(presets.get("presets"))
    return {
        "version": "1.0",
        "generated_by": "scripts/validate_product_scope.py",
        "gate": "passed" if passed else "blocked",
        "visible_capability_count": len(visible_ids),
        "preset_count": len(presets.get("presets", [])),
        "preset_category_count": len(
            {str(item.get("category")) for item in presets.get("presets", [])}
        ),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--ui", type=Path, default=ROOT / "configs/ui/editor.json")
    parser.add_argument("--presets", type=Path, default=ROOT / "configs/presets/free.json")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--frontend-root", type=Path, default=ROOT / "frontend/src")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    cases = args.cases or profile.cases_path
    output = args.output or profile.diagnostics_root / "product-scope.json"
    report = run(
        args.ui.resolve(),
        args.presets.resolve(),
        cases.resolve(),
        args.frontend_root.resolve(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
