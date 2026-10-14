"""Build a versioned, read-only manifest for a local Luminar installation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.luminar_install_inspector import LuminarInstallInspector


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=Path("/Applications/Luminar Neo.app"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/diagnostics/reference/current-local-install",
    )
    parser.add_argument(
        "--local-lock",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    manifest, contracts, lock = LuminarInstallInspector(args.app).inspect()
    write_json(args.output_dir / "install-manifest.json", manifest)
    write_json(args.output_dir / "ui-contract.json", contracts)
    write_json(args.local_lock or args.output_dir / "local-install.lock.json", lock)
    print(
        json.dumps(
            {
                "reference_build": manifest["reference_build"]["id"],
                **manifest["counts"],
                "ui_tool_groups": len(contracts["tool_groups"]),
                "sky_parameters": len(contracts["tools"]["sky_replace"]["parameters"]),
                "preset_collections": manifest["counts"]["preset_collections"],
                "presets": manifest["counts"]["presets"],
                "presets_declared": manifest["counts"]["presets_declared"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
