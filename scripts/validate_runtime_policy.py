"""Enforce the ONNX Runtime first, explicit OpenVINO fallback runtime policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(model_config_path: Path, model_module: Path) -> dict[str, Any]:
    payload = yaml.safe_load(model_config_path.read_text(encoding="utf-8"))
    selection = payload.get("selection", {})
    records = payload.get("models", [])
    issues: list[dict[str, str]] = []
    if selection.get("primary") != "onnxruntime":
        issues.append({"kind": "primary-backend", "value": str(selection.get("primary"))})
    if selection.get("fallback") != "openvino":
        issues.append({"kind": "fallback-backend", "value": str(selection.get("fallback"))})

    allowed_formats = {"onnx", "ort", "openvino_ir"}
    for record in records:
        model_id = str(record.get("id", ""))
        model_format = str(record.get("format", ""))
        backend = str(record.get("backend", "auto"))
        searchable = json.dumps(record, ensure_ascii=False).lower()
        if model_format not in allowed_formats:
            issues.append({"kind": "unsupported-format", "model_id": model_id, "value": model_format})
        if backend not in {"auto", "onnxruntime", "openvino"}:
            issues.append({"kind": "unsupported-backend", "model_id": model_id, "value": backend})
        if "coreml" in searchable:
            issues.append({"kind": "forbidden-coreml-record", "model_id": model_id})

    for path in model_module.rglob("*.py"):
        if "coreml" in path.read_text(encoding="utf-8", errors="ignore").lower():
            issues.append({"kind": "forbidden-coreml-code", "value": str(path)})

    return {
        "version": "1.0",
        "model_count": len(records),
        "primary": selection.get("primary"),
        "fallback": selection.get("fallback"),
        "coreml_references": sum("coreml" in item["kind"] for item in issues),
        "issues": issues,
        "gate": "passed" if not issues else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument("--model-module", type=Path, default=ROOT / "ai/model")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/diagnostics/runtime-policy.json"
    )
    args = parser.parse_args()
    report = run(args.models.resolve(), args.model_module.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
