"""Fail closed unless UI screenshots belong to the current build and fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frontend_build_hash(frontend_root: Path) -> str:
    files = [
        path
        for path in frontend_root.rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and "dist" not in path.parts
        and (
            "src" in path.relative_to(frontend_root).parts
            or path.name in {"package.json", "package-lock.json", "vite.config.ts"}
            or path.name.startswith("tsconfig")
        )
    ]
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(frontend_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _resolved_artifact(root: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("artifact path escapes execution root") from exc
    return resolved


def validate_execution_evidence(
    payload: dict[str, Any],
    *,
    config_path: Path,
    ui_matrix_path: Path,
    candidate_root: Path,
    frontend_root: Path,
    execution_root: Path,
    reference_id: str,
    region_manifest_path: Path | None = None,
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    ui_matrix = json.loads(ui_matrix_path.read_text(encoding="utf-8"))
    capture = config.get("capture", {})
    expected = {
        (f"{int(width)}x{int(height)}", str(record["id"]))
        for width, height in capture.get("ui_viewports", [])
        for record in ui_matrix.get("records", [])
        if isinstance(record, dict) and record.get("id")
    }
    issues: list[dict[str, Any]] = []
    if ui_matrix.get("reference_id") != reference_id:
        issues.append({"id": "ui-matrix-reference-id-mismatch"})
    matrix_fingerprint = str(ui_matrix.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        issues.append({"id": "invalid-ui-matrix-fingerprint"})
    if payload.get("matrix_fingerprint") != matrix_fingerprint:
        issues.append({"id": "ui-matrix-fingerprint-mismatch"})
    environment = payload.get("environment")
    required_environment = {
        "browser",
        "browser_version",
        "capture_engine",
        "logical_viewport",
        "physical_viewport",
        "device_scale_factor",
        "locale",
        "timezone",
        "motion",
        "build_hash",
    }
    if not isinstance(environment, dict) or not required_environment <= set(environment):
        issues.append({"id": "incomplete-browser-environment"})
        environment = environment if isinstance(environment, dict) else {}
    current_build_hash = frontend_build_hash(frontend_root)
    if environment.get("build_hash") != current_build_hash:
        issues.append({"id": "stale-frontend-build"})
    logical_viewport = environment.get("logical_viewport")
    device_scale_factor = environment.get("device_scale_factor")
    physical_viewport = environment.get("physical_viewport")
    try:
        logical_width, logical_height = (
            int(value) for value in logical_viewport
        )
        scale = float(device_scale_factor)
        derived_physical = {
            f"{round(logical_width * scale)}x{round(logical_height * scale)}"
        }
    except (TypeError, ValueError):
        derived_physical = set()
    expected_viewports = {viewport for viewport, _state in expected}
    if (
        derived_physical != expected_viewports
        or set(physical_viewport if isinstance(physical_viewport, list) else [])
        != expected_viewports
    ):
        issues.append({"id": "viewport-contract-mismatch"})
    if environment.get("locale") != "zh-Hans":
        issues.append({"id": "locale-contract-mismatch"})
    if environment.get("timezone") != "Asia/Shanghai":
        issues.append({"id": "timezone-contract-mismatch"})
    if environment.get("motion") != "reduce":
        issues.append({"id": "motion-contract-mismatch"})
    if payload.get("reference_id") != reference_id:
        issues.append({"id": "reference-id-mismatch"})
    if region_manifest_path is not None:
        regions = payload.get("regions")
        expected_regions = region_manifest_path.resolve()
        if not isinstance(regions, dict):
            issues.append({"id": "missing-region-manifest-binding"})
        else:
            manifest_value = regions.get("manifest")
            bound_path = Path(str(manifest_value or ""))
            bound_path = bound_path.resolve() if bound_path.is_absolute() else (ROOT / bound_path).resolve()
            if bound_path != expected_regions:
                issues.append({"id": "region-manifest-path-mismatch"})
            if not expected_regions.is_file():
                issues.append({"id": "missing-region-manifest"})
            elif regions.get("manifest_sha256") != sha256_file(expected_regions):
                issues.append({"id": "region-manifest-hash-mismatch"})

    fixture = payload.get("fixture")
    fixture_payload: dict[str, Any] = {}
    fixture_fingerprint = ""
    required_fixture = {
        "manifest",
        "manifest_sha256",
        "fixture_fingerprint",
        "collection",
        "expected_count",
        "catalog_count",
        "unique_source_hash_count",
    }
    if not isinstance(fixture, dict) or not required_fixture <= set(fixture):
        issues.append({"id": "incomplete-fixture-evidence"})
        fixture = fixture if isinstance(fixture, dict) else {}
    try:
        fixture_manifest = _resolved_artifact(execution_root, fixture.get("manifest"))
    except ValueError:
        fixture_manifest = execution_root / "__invalid__"
        issues.append({"id": "invalid-fixture-manifest-path"})
    if not fixture_manifest.is_file():
        issues.append({"id": "missing-fixture-manifest"})
    else:
        if sha256_file(fixture_manifest) != fixture.get("manifest_sha256"):
            issues.append({"id": "fixture-manifest-hash-mismatch"})
        try:
            loaded_fixture = json.loads(fixture_manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            loaded_fixture = None
        if not isinstance(loaded_fixture, dict):
            issues.append({"id": "invalid-fixture-manifest"})
        else:
            fixture_payload = loaded_fixture
    fixture_fingerprint = str(fixture.get("fixture_fingerprint") or "")
    for field in (
        "fixture_fingerprint",
        "collection",
        "expected_count",
        "catalog_count",
        "unique_source_hash_count",
    ):
        if fixture_payload and fixture.get(field) != fixture_payload.get(field):
            issues.append({"id": f"fixture-{field.replace('_', '-')}-mismatch"})
    if len(fixture_fingerprint) != 64:
        issues.append({"id": "invalid-fixture-fingerprint"})
    fixture_count = fixture.get("catalog_count")
    if (
        fixture.get("expected_count") != fixture_count
        or fixture.get("unique_source_hash_count") != fixture_count
    ):
        issues.append({"id": "fixture-catalog-not-unique-complete"})
    fixture_sources = {
        str(record.get("filename")): str(record.get("source_sha256"))
        for record in fixture_payload.get("records", [])
        if isinstance(record, dict)
    }

    records = payload.get("records")
    if not isinstance(records, list):
        records = []
        issues.append({"id": "missing-execution-records"})
    actual: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            issues.append({"id": "invalid-execution-record"})
            continue
        key = (
            str(record.get("viewport", "")),
            str(record.get("matrix_state_id", "")),
        )
        if record.get("state") is not None:
            issues.append(
                {
                    "id": "noncanonical-state-field",
                    "viewport": key[0],
                    "state": key[1],
                }
            )
        if key in actual:
            issues.append({"id": "duplicate-state", "viewport": key[0], "state": key[1]})
            continue
        actual[key] = record

    for viewport, state in sorted(expected):
        record = actual.get((viewport, state))
        if record is None:
            issues.append({"id": "missing-state", "viewport": viewport, "state": state})
            continue
        fixture_id = record.get("fixture_id")
        fixture_hash = str(record.get("fixture_hash", ""))
        if not isinstance(fixture_id, str) or not fixture_id or len(fixture_hash) != 64:
            issues.append({"id": "invalid-fixture", "viewport": viewport, "state": state})
        if record.get("actual_fixture_fingerprint") != fixture_fingerprint:
            issues.append(
                {"id": "fixture-fingerprint-mismatch", "viewport": viewport, "state": state}
            )
        if isinstance(fixture_id, str) and fixture_id.startswith("single-image:"):
            filename = fixture_id.split(":", 1)[1]
            if fixture_sources.get(filename) != fixture_hash:
                issues.append(
                    {"id": "fixture-source-mismatch", "viewport": viewport, "state": state}
                )
        if isinstance(fixture_id, str) and fixture_id.startswith("catalog:"):
            collection = fixture_id.split(":", 1)[1]
            if fixture.get("collection") != collection:
                issues.append(
                    {"id": "fixture-collection-mismatch", "viewport": viewport, "state": state}
                )
        try:
            screenshot = _resolved_artifact(execution_root, record.get("screenshot"))
        except ValueError:
            screenshot = execution_root / "__invalid__"
            issues.append({"id": "invalid-screenshot-path", "viewport": viewport, "state": state})
        expected_screenshot = (candidate_root / viewport / f"{state}.png").resolve()
        if screenshot != expected_screenshot:
            issues.append({"id": "unexpected-screenshot-path", "viewport": viewport, "state": state})
        if not screenshot.is_file():
            issues.append({"id": "missing-screenshot", "viewport": viewport, "state": state})
            continue
        if sha256_file(screenshot) != record.get("screenshot_sha256"):
            issues.append({"id": "screenshot-hash-mismatch", "viewport": viewport, "state": state})
        width, height = (int(value) for value in viewport.split("x", 1))
        with Image.open(screenshot) as image:
            if image.size != (width, height):
                issues.append({"id": "screenshot-size-mismatch", "viewport": viewport, "state": state})
        try:
            source_capture = _resolved_artifact(
                execution_root, record.get("source_capture")
            )
        except ValueError:
            source_capture = execution_root / "__invalid__"
            issues.append(
                {"id": "invalid-source-capture-path", "viewport": viewport, "state": state}
            )
        if not source_capture.is_file():
            issues.append(
                {"id": "missing-source-capture", "viewport": viewport, "state": state}
            )
            continue
        if sha256_file(source_capture) != record.get("source_capture_sha256"):
            issues.append(
                {"id": "source-capture-hash-mismatch", "viewport": viewport, "state": state}
            )
        for field in ("dom_snapshot", "accessibility_tree"):
            try:
                artifact = _resolved_artifact(execution_root, record.get(field))
            except ValueError:
                issues.append(
                    {
                        "id": f"invalid-{field.replace('_', '-')}-path",
                        "viewport": viewport,
                        "state": state,
                    }
                )
                continue
            if not artifact.is_file():
                issues.append(
                    {
                        "id": f"missing-{field.replace('_', '-')}",
                        "viewport": viewport,
                        "state": state,
                    }
                )
                continue
            if sha256_file(artifact) != record.get(f"{field}_sha256"):
                issues.append(
                    {
                        "id": f"{field.replace('_', '-')}-hash-mismatch",
                        "viewport": viewport,
                        "state": state,
                    }
                )
            try:
                artifact_payload = json.loads(artifact.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                artifact_payload = None
            if artifact_payload in ({}, [], None):
                issues.append(
                    {
                        "id": f"empty-{field.replace('_', '-')}",
                        "viewport": viewport,
                        "state": state,
                    }
                )
        if record.get("capture_method") != "native-dpr2":
            issues.append(
                {"id": "capture-method-mismatch", "viewport": viewport, "state": state}
            )
        if "scale_method" in record:
            issues.append(
                {"id": "derived-capture-not-allowed", "viewport": viewport, "state": state}
            )
        with Image.open(source_capture) as source_image, Image.open(screenshot) as candidate_image:
            if source_image.size != (width, height):
                issues.append(
                    {"id": "source-capture-size-mismatch", "viewport": viewport, "state": state}
                )
            elif ImageChops.difference(
                source_image.convert("RGB"), candidate_image.convert("RGB")
            ).getbbox():
                issues.append(
                    {"id": "candidate-native-capture-mismatch", "viewport": viewport, "state": state}
                )

    for viewport, state in sorted(set(actual) - expected):
        issues.append({"id": "unexpected-state", "viewport": viewport, "state": state})

    invalid_keys = {
        (str(issue.get("viewport", "")), str(issue.get("state", "")))
        for issue in issues
        if issue.get("viewport") and issue.get("state")
    }
    passed = sum(key in actual and key not in invalid_keys for key in expected)
    return {
        "version": "1.0",
        "reference_id": reference_id,
        "matrix_fingerprint": matrix_fingerprint,
        "expected": len(expected),
        "executed": len(expected & set(actual)),
        "passed": passed if not any("state" not in issue for issue in issues) else 0,
        "build_hash": current_build_hash,
        "issue_count": len(issues),
        "gate": "passed" if expected and not issues else "blocked",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/parity.yaml")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
    )
    parser.add_argument("--execution", type=Path)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--frontend-root", type=Path, default=ROOT / "frontend")
    parser.add_argument("--regions", type=Path, default=ROOT / "configs/parity/ui-regions.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    execution = (
        args.execution or profile.diagnostics_root / "ui-browser-execution.json"
    ).resolve()
    candidate_root = (
        args.candidates or profile.diagnostics_root / "ui-candidates"
    ).resolve()
    payload = (
        json.loads(execution.read_text(encoding="utf-8"))
        if execution.is_file()
        else {"records": []}
    )
    report = validate_execution_evidence(
        payload,
        config_path=args.config.resolve(),
        ui_matrix_path=args.matrix.resolve(),
        candidate_root=candidate_root,
        frontend_root=args.frontend_root.resolve(),
        execution_root=execution.parent,
        reference_id=profile.id,
        region_manifest_path=args.regions,
    )
    output = (
        args.output or profile.diagnostics_root / "ui-execution-evidence.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: report[key] for key in ("expected", "executed", "passed", "issue_count", "gate")},
            ensure_ascii=False,
        )
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
