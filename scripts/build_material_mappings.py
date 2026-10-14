"""Build capability-to-material-family mappings from parity metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FAMILY_BY_GROUP = {
    "sky": ["sky", "atmosphere"],
    "portrait": ["face_relight", "face_zones", "makeup", "contact_lens"],
    "color": ["lut", "color_transfer"],
    "light": ["atmosphere", "overlay", "shader"],
    "restore": ["overlay"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("parity", type=Path)
    parser.add_argument("assets", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parity = json.loads(args.parity.read_text(encoding="utf-8"))
    assets = json.loads(args.assets.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for record in assets.get("records", []):
        counts[record["family"]] = counts.get(record["family"], 0) + 1
    mappings = []
    for record in parity.get("records", []):
        families = FAMILY_BY_GROUP.get(record.get("group"), [])
        mappings.append(
            {
                "capability_id": record.get("capability_id"),
                "original_effect_id": record.get("original_effect_id"),
                "families": [
                    {"family": family, "available_count": counts.get(family, 0)}
                    for family in families
                ],
                "asset_requirement": "required"
                if families
                and record.get("capability_id")
                in {"sky_replace", "augmented_sky", "lut_mapping", "color_transfer"}
                else "optional",
                "status": "mapped"
                if all(counts.get(family, 0) > 0 for family in families)
                else ("no-material-family" if not families else "missing-family-assets"),
            }
        )
    payload = {"version": "0.2.0", "family_counts": counts, "mappings": mappings}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"mappings": len(mappings), "families": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
