"""Validate visible tool icon, tone and AI badge metadata."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs import load_config


def main() -> None:
    root = ROOT
    ui = load_config(root).ui
    groups = ui.get("tool_groups", [])
    visuals = ui.get("capability_visuals", {})
    visible = [capability for group in groups for capability in group["capabilities"]]
    capability_payload = json.loads(
        (root / "configs/capabilities/registry.json").read_text(encoding="utf-8")
    )
    titles = {item["id"]: item["title"] for item in capability_payload["capabilities"]}
    errors: list[str] = []
    for group in groups:
        if not group.get("tone"):
            errors.append(f"missing tone: {group.get('id')}")
    for capability in visible:
        visual = visuals.get(capability)
        if not visual:
            errors.append(f"missing visual metadata: {capability}")
            continue
        if not visual.get("icon") or not isinstance(visual.get("ai_badge"), bool):
            errors.append(f"invalid visual metadata: {capability}")
        if bool(visual.get("ai_badge")) != str(titles.get(capability, "")).endswith("AI"):
            errors.append(f"AI badge/title mismatch: {capability}")
    if set(visuals) != set(visible):
        errors.append("capability_visuals must match the visible tool set exactly")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"tool-visuals: {len(groups)} groups, {len(visible)} tools valid")


if __name__ == "__main__":
    main()
