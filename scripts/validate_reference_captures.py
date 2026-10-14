"""Validate one versioned Luminar black-box capture folder without fallbacks."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from configs.reference import load_reference_catalog


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _case_status(
    case: dict[str, Any],
    capture_root: Path,
    expected_build: str,
    required_outputs: set[str],
    required_metadata: set[str],
    expected_app_version: str | None = None,
    expected_app_build: str | None = None,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    output_root = capture_root / "luminar_outputs" / case_id
    ui_root = capture_root / "luminar_ui" / case_id
    metadata_path = capture_root / "metadata" / f"{case_id}.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    files = {
        key: (ui_root if key.startswith("ui_") else output_root) / filename
        for key, filename in {
            "preview": "preview.png",
            "export": "export.png",
            "mask": "mask.png",
            "ui_before": "before.png",
            "ui_after": "after.png",
        }.items()
    }
    missing = [key for key, path in files.items() if key in required_outputs and not path.is_file()]
    errors: list[str] = []
    captured_any = any(path.is_file() for path in files.values())
    if captured_any and not metadata_path.is_file():
        errors.append("metadata-missing")
    if metadata:
        for key in sorted(required_metadata - set(metadata)):
            errors.append(f"metadata-field-missing:{key}")
    if metadata and metadata.get("reference_build") not in {None, expected_build}:
        errors.append(f"reference_build-mismatch:{metadata.get('reference_build')}")
    app_version = metadata.get("app_version", {}) if isinstance(metadata, dict) else {}
    if metadata and expected_app_version and str(app_version.get("version", "")) != expected_app_version:
        errors.append(f"app-version-mismatch:{app_version.get('version')}")
    if metadata and expected_app_build and str(app_version.get("build", "")) != expected_app_build:
        errors.append(f"app-build-mismatch:{app_version.get('build')}")
    if metadata and metadata.get("case_id") not in {None, case.get("case_id")}:
        errors.append("case-id-mismatch")
    input_path = Path(str(case.get("input", {}).get("path", "")))
    expected_input_hash = case.get("input", {}).get("sha256")
    if input_path.is_file() and expected_input_hash and _sha256(input_path) != expected_input_hash:
        errors.append("input-hash-mismatch")
    if metadata and metadata.get("input_sha256") not in {None, expected_input_hash}:
        errors.append("metadata-input-hash-mismatch")
    if metadata and metadata.get("capability_id") not in {
        None,
        case.get("capability_id"),
    }:
        errors.append("metadata-capability-mismatch")
    if (
        metadata
        and metadata.get("parameters") is not None
        and metadata.get("parameters") != case.get("parameters")
    ):
        errors.append("metadata-parameters-mismatch")
    metadata_hashes = metadata.get("sha256", {}) if isinstance(metadata, dict) else {}
    for key, path in files.items():
        expected_hash = metadata_hashes.get(key)
        if metadata and path.is_file() and not expected_hash:
            errors.append(f"{key}-hash-missing")
        if expected_hash and path.is_file() and _sha256(path) != expected_hash:
            errors.append(f"{key}-hash-mismatch")
    captured = not missing and not errors
    return {
        "case_id": case_id,
        "status": "ready" if captured else "pending-reference" if not errors else "invalid",
        "missing": missing,
        "errors": errors,
        "metadata": str(metadata_path) if metadata_path.is_file() else None,
        "files": {key: str(path) if path.is_file() else None for key, path in files.items()},
    }


def run(
    cases_path: Path,
    capture_root: Path,
    expected_build: str,
    *,
    required_outputs: set[str] | None = None,
    required_metadata: set[str] | None = None,
    expected_app_version: str | None = None,
    expected_app_build: str | None = None,
) -> dict[str, Any]:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    outputs = required_outputs or {"preview", "export"}
    metadata_fields = required_metadata or {
        "case_id",
        "reference_build",
        "capability_id",
        "parameters",
        "input_sha256",
        "export_format",
        "color_profile",
    }
    records = [
        _case_status(
            case,
            capture_root,
            expected_build,
            outputs,
            metadata_fields,
            expected_app_version,
            expected_app_build,
        )
        for case in payload.get("cases", [])
    ]
    return {
        "version": "0.1.0",
        "generated_by": "scripts/validate_reference_captures.py",
        "expected_build": expected_build,
        "cases": str(cases_path),
        "capture_root": str(capture_root),
        "case_count": len(records),
        "ready": sum(item["status"] == "ready" for item in records),
        "pending": sum(item["status"] == "pending-reference" for item in records),
        "invalid": sum(item["status"] == "invalid" for item in records),
        "exact_gate": "passed"
        if records and all(item["status"] == "ready" for item in records)
        else "blocked",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--capture-root", type=Path)
    parser.add_argument("--parity-config", type=Path, default=ROOT / "configs/parity.yaml")
    parser.add_argument(
        "--output", type=Path
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    cases_path = (args.cases or profile.cases_path).resolve()
    capture_root = (args.capture_root or profile.capture_root).resolve()
    output_path = (
        args.output or profile.diagnostics_root / "reference-capture-audit.json"
    ).resolve()
    parity = yaml.safe_load(args.parity_config.read_text(encoding="utf-8"))
    capture = parity.get("capture", {})
    report = run(
        cases_path,
        capture_root,
        profile.id,
        required_outputs=set(capture.get("required_outputs", ["preview", "export"])),
        required_metadata=set(capture.get("required_metadata", [])),
        expected_app_version=profile.version,
        expected_app_build=profile.build,
    )
    report["reference_id"] = profile.id
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_count", "ready", "pending", "invalid", "exact_gate")}, ensure_ascii=False))
    return 0 if report["exact_gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
