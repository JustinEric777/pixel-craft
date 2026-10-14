"""Extract a useful capability matrix from Luminar's non-standard JSON-like files.

The source files are treated as read-only evidence. Some releases contain
trailing commas or incomplete fragments, so this tool intentionally uses
conservative regex extraction and never executes or imports application code.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def extract_object_keys(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'^\s*"([^"\n]+)"\s*:\s*\{', text, re.MULTILINE)))


def extract_tool_names(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'"tool_name"\s*:\s*"([^"]+)"', text)))


def extract_model_files(root: Path) -> list[dict[str, Any]]:
    files = []
    for path in sorted(root.iterdir()):
        if path.suffix.lower() not in {".onnx", ".xml", ".bin", ".ort"}:
            continue
        files.append(
            {"name": path.name, "suffix": path.suffix.lower(), "size_bytes": path.stat().st_size}
        )
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("luminar_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profiles = args.luminar_root / "profiles"
    model_root = profiles / "profiles"
    edits = (profiles / "EditsConfig.json").read_text(encoding="utf-8", errors="replace")
    tools = (profiles / "MiplTools.json").read_text(encoding="utf-8", errors="replace")
    descriptions_path = profiles / "MiplToolsDescription.json"
    descriptions = descriptions_path.read_text(encoding="utf-8", errors="replace")
    result = {
        "source_root": str(args.luminar_root),
        "read_only_evidence": True,
        "config_files": {
            "edits_config": str(profiles / "EditsConfig.json"),
            "mipl_tools": str(profiles / "MiplTools.json"),
            "mipl_parameters": str(profiles / "MiplToolsParameters.json"),
            "mipl_descriptions": str(descriptions_path),
        },
        "config_parse_notes": [
            "MiplToolsDescription.json is not strict JSON in this release; names are extracted conservatively.",
            "MiplToolsParameters.json and EffectsConfig.json require format-specific parser work before parameter parity.",
        ],
        "effect_ids": extract_object_keys(edits),
        "tool_names": extract_tool_names(tools),
        "description_ids": extract_object_keys(descriptions),
        "model_files": extract_model_files(model_root),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
