import json
import sys
from pathlib import Path

from scripts import build_capability_metadata


def test_inventory_builder_never_generates_parameter_schema(
    tmp_path: Path, monkeypatch
) -> None:
    inventory = tmp_path / "inventory.json"
    registry = tmp_path / "registry.json"
    output = tmp_path / "output"
    inventory.write_text(
        json.dumps(
            {
                "effect_ids": ["AIEnhanceAdjustmentLayer"],
                "tool_names": ["AI Adjustments"],
            }
        ),
        encoding="utf-8",
    )
    registry.write_text(
        json.dumps(
            {
                "capabilities": [
                    {"id": "ai_enhance", "group": "enhance"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_capability_metadata.py",
            str(inventory),
            str(registry),
            "--output-dir",
            str(output),
        ],
    )

    assert build_capability_metadata.main() == 0
    assert (output / "parity-matrix.json").is_file()
    assert (output / "tool-mappings.json").is_file()
    assert not (output / "parameter-schema.json").exists()
