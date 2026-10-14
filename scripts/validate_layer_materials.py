"""Fail closed when Luminar's published free layer materials drift."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs import load_config
from storage.assets.catalog import AssetCatalog


def main() -> None:
    root = ROOT
    config = load_config(root)
    catalog = AssetCatalog(
        config.paths.asset_root,
        layer_library=config.ui.get("layer_library"),
    )
    groups = catalog.layer_material_groups()
    expected = [("星尘散景", 12), ("漏光", 12), ("烟火", 8), ("耀斑", 6)]
    actual = [(group["label"], group["count"]) for group in groups]
    if actual != expected:
        raise SystemExit(f"layer material groups mismatch: {actual!r}")
    materials = [item for group in groups for item in group["items"]]
    if len(materials) != 38:
        raise SystemExit(f"expected 38 published materials, found {len(materials)}")
    if any(item["blend_mode"] != "screen" for item in materials):
        raise SystemExit("every published Luminar overlay must use screen blending")
    print("layer-materials: 4 groups, 38 published items, screen defaults valid")


if __name__ == "__main__":
    main()
