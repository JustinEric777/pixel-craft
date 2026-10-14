"""Fail closed unless every interaction contract has complete browser evidence."""

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

from configs.reference import load_reference_catalog
from scripts.validate_ui_execution_evidence import frontend_build_hash

EFFECT_CONTRACTS = {
    "workflow:edit-tool-expand-crop",
    "workflow:photo-switch-history",
    "workflow:preset-import-preview-apply",
    "workflow:layer-lifecycle",
    "workflow:mask-lifecycle",
    "workflow:compare-zoom-pan",
    "workflow:multi-image-three-workflows",
    "workflow:export-dialog-file",
}


def _passed_names(value: Any) -> set[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    if isinstance(value, dict):
        return {str(name) for name, passed in value.items() if passed is True}
    return set()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(root: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("artifact path escapes evidence root") from exc
    return resolved


def _validate_native_observation(
    contract_id: str,
    contract: dict[str, Any],
    *,
    native_root: Path,
    reference_id: str,
    expected_app: dict[str, str],
    matrix_fingerprint: str,
) -> tuple[Path | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    path = native_root / contract_id / "observation.json"
    if not path.is_file():
        return None, [{"id": "missing-native-observation", "contract": contract_id}]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return path, [{"id": "invalid-native-observation", "contract": contract_id}]
    if payload.get("contract_id") != contract_id:
        issues.append({"id": "native-contract-id-mismatch", "contract": contract_id})
    if payload.get("reference_id") != reference_id:
        issues.append({"id": "native-reference-id-mismatch", "contract": contract_id})
    if payload.get("app_version") != expected_app:
        issues.append({"id": "native-app-version-mismatch", "contract": contract_id})
    if payload.get("matrix_fingerprint") != matrix_fingerprint:
        issues.append({"id": "native-matrix-fingerprint-mismatch", "contract": contract_id})
    if payload.get("events") != contract.get("events"):
        issues.append({"id": "native-events-mismatch", "contract": contract_id})
    if payload.get("final_state") != contract.get("final_screenshot_state"):
        issues.append({"id": "native-final-state-mismatch", "contract": contract_id})
    if _passed_names(payload.get("visible_assertions")) != set(
        contract.get("visible_assertions", [])
    ):
        issues.append({"id": "native-visible-assertions-incomplete", "contract": contract_id})
    waits = payload.get("wait_conditions")
    if not isinstance(waits, list) or not set(waits) <= set(
        contract.get("allowed_wait_conditions", [])
    ):
        issues.append({"id": "undeclared-native-wait", "contract": contract_id})
    if len(str(payload.get("fixture_hash", ""))) != 64:
        issues.append({"id": "invalid-native-fixture", "contract": contract_id})
    capture_environment = payload.get("capture_environment")
    if (
        not isinstance(capture_environment, dict)
        or capture_environment.get("native_full_screen") is not True
        or capture_environment.get("capture_mode") != "local-physical-display"
        or capture_environment.get("display_session_verified") is not True
        or capture_environment.get("automation_input_verified") is not True
        or capture_environment.get("user_authorized_local_capture") is not True
        or not capture_environment.get("capture_provider")
        or not capture_environment.get("capture_session_id")
        or not capture_environment.get("capture_verified_at")
        or not isinstance(capture_environment.get("window_bounds"), dict)
    ):
        issues.append({"id": "native-full-screen-evidence-missing", "contract": contract_id})
    if contract_id in EFFECT_CONTRACTS:
        evidence = payload.get("assertion_evidence")
        if not isinstance(evidence, dict) or evidence.get("source_edits_reset") is not True:
            issues.append(
                {"id": "native-source-not-reset-before-effect", "contract": contract_id}
            )
    observation_root = path.parent
    for field in ("before_screenshot", "after_screenshot", "accessibility_snapshot"):
        try:
            artifact = _artifact(observation_root, payload.get(field))
        except ValueError:
            issues.append({"id": "invalid-native-artifact-path", "contract": contract_id, "field": field})
            continue
        if not artifact.is_file():
            issues.append({"id": "missing-native-artifact", "contract": contract_id, "field": field})
            continue
        if payload.get(f"{field}_sha256") != _sha256(artifact):
            issues.append({"id": "native-artifact-hash-mismatch", "contract": contract_id, "field": field})
    return path, issues


def validate_execution(
    contracts: dict[str, Any],
    execution: dict[str, Any],
    *,
    execution_root: Path,
    native_observation_root: Path,
    expected_app: dict[str, str],
    frontend_root: Path | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    expected = {
        str(item["id"]): item
        for item in contracts.get("records", [])
        if isinstance(item, dict) and item.get("id")
    }
    records = execution.get("records")
    if not isinstance(records, list):
        records = []
        issues.append({"id": "missing-execution-records"})
    actual: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not record.get("id"):
            issues.append({"id": "invalid-execution-record"})
            continue
        contract_id = str(record["id"])
        if contract_id in actual:
            issues.append({"id": "duplicate-execution-record", "contract": contract_id})
            continue
        actual[contract_id] = record

    environment = execution.get("environment")
    required_environment = {
        "browser",
        "browser_version",
        "logical_viewport",
        "device_scale_factor",
        "physical_viewport",
        "locale",
        "timezone",
        "build_hash",
    }
    if not isinstance(environment, dict) or not required_environment <= set(environment):
        issues.append({"id": "incomplete-browser-environment"})
        environment = environment if isinstance(environment, dict) else {}
    if environment.get("locale") != "zh-Hans":
        issues.append({"id": "locale-contract-mismatch"})
    if environment.get("timezone") != "Asia/Shanghai":
        issues.append({"id": "timezone-contract-mismatch"})
    for field in (
        "logical_viewport",
        "device_scale_factor",
        "physical_viewport",
    ):
        if environment.get(field) != contracts.get(field):
            issues.append({"id": f"{field.replace('_', '-')}-contract-mismatch"})
    if frontend_root is not None and environment.get("build_hash") != frontend_build_hash(
        frontend_root
    ):
        issues.append({"id": "stale-frontend-build"})
    if execution.get("reference_id") != contracts.get("reference_id"):
        issues.append({"id": "reference-id-mismatch"})
    matrix_fingerprint = str(contracts.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        issues.append({"id": "invalid-interaction-matrix-fingerprint"})
    if execution.get("matrix_fingerprint") != matrix_fingerprint:
        issues.append({"id": "interaction-matrix-fingerprint-mismatch"})

    for contract_id, contract in expected.items():
        native_observation, native_issues = _validate_native_observation(
            contract_id,
            contract,
            native_root=native_observation_root,
            reference_id=str(contracts.get("reference_id", "")),
            expected_app=expected_app,
            matrix_fingerprint=matrix_fingerprint,
        )
        issues.extend(native_issues)
        record = actual.get(contract_id)
        if record is None:
            issues.append({"id": "missing-execution", "contract": contract_id})
            continue
        if record.get("status") != "passed":
            issues.append(
                {
                    "id": "execution-not-passed",
                    "contract": contract_id,
                    "status": record.get("status"),
                }
            )
        if record.get("event_count") != len(contract.get("events", [])):
            issues.append({"id": "event-count-mismatch", "contract": contract_id})
        expected_visible = set(contract.get("visible_assertions", []))
        if _passed_names(record.get("visible_assertions")) != expected_visible:
            issues.append({"id": "visible-assertions-incomplete", "contract": contract_id})
        expected_api = set(contract.get("api_assertions", []))
        if _passed_names(record.get("api_assertions")) != expected_api:
            issues.append({"id": "api-assertions-incomplete", "contract": contract_id})
        waits = record.get("wait_conditions")
        allowed_waits = set(contract.get("allowed_wait_conditions", []))
        if not isinstance(waits, list) or not set(waits) <= allowed_waits:
            issues.append({"id": "undeclared-execution-wait", "contract": contract_id})
        if record.get("fixed_sleep"):
            issues.append({"id": "fixed-sleep-forbidden", "contract": contract_id})
        if native_observation is not None:
            linked_value = Path(str(record.get("native_observation", "")))
            linked_native = (
                linked_value.resolve()
                if linked_value.is_absolute()
                else (execution_root / linked_value).resolve()
            )
            try:
                linked_native.relative_to(native_observation_root.resolve())
            except ValueError:
                issues.append({"id": "invalid-native-link", "contract": contract_id})
            if linked_native != native_observation.resolve():
                issues.append({"id": "native-observation-link-mismatch", "contract": contract_id})
            elif record.get("native_observation_sha256") != _sha256(native_observation):
                issues.append({"id": "native-observation-hash-mismatch", "contract": contract_id})
        try:
            screenshot = _artifact(execution_root, record.get("final_screenshot"))
        except ValueError:
            issues.append({"id": "invalid-final-screenshot-path", "contract": contract_id})
            continue
        if not screenshot.is_file():
            issues.append({"id": "missing-final-screenshot", "contract": contract_id})
        elif record.get("final_screenshot_sha256") != _sha256(screenshot):
            issues.append({"id": "final-screenshot-hash-mismatch", "contract": contract_id})
        for field in (
            "dom_snapshot",
            "accessibility_tree",
            "execution_trace",
            "network_trace",
            "console_log",
        ):
            try:
                artifact = _artifact(execution_root, record.get(field))
            except ValueError:
                issues.append(
                    {
                        "id": f"invalid-{field.replace('_', '-')}-path",
                        "contract": contract_id,
                    }
                )
                continue
            if not artifact.is_file():
                issues.append(
                    {
                        "id": f"missing-{field.replace('_', '-')}",
                        "contract": contract_id,
                    }
                )
                continue
            if record.get(f"{field}_sha256") != _sha256(artifact):
                issues.append(
                    {
                        "id": f"{field.replace('_', '-')}-hash-mismatch",
                        "contract": contract_id,
                    }
                )
            try:
                payload = json.loads(artifact.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if payload in ({}, [], None):
                issues.append(
                    {
                        "id": f"empty-{field.replace('_', '-')}",
                        "contract": contract_id,
                    }
                )

    for contract_id in sorted(set(actual) - set(expected)):
        issues.append({"id": "unexpected-execution", "contract": contract_id})

    passed = sum(
        contract_id in actual
        and actual[contract_id].get("status") == "passed"
        and not any(item.get("contract") == contract_id for item in issues)
        for contract_id in expected
    )
    return {
        "version": "1.0",
        "reference_id": contracts.get("reference_id"),
        "matrix_fingerprint": matrix_fingerprint,
        "contract_count": len(expected),
        "executed": len(set(expected) & set(actual)),
        "passed": passed,
        "issue_count": len(issues),
        "gate": "passed" if expected and not issues else "blocked",
        "issues": issues,
    }


def validate_native_observations(
    contracts: dict[str, Any],
    *,
    native_observation_root: Path,
    expected_app: dict[str, str],
) -> dict[str, Any]:
    """Validate native observations without requiring browser execution yet."""

    expected = {
        str(item["id"]): item
        for item in contracts.get("records", [])
        if isinstance(item, dict) and item.get("id")
    }
    issues: list[dict[str, Any]] = []
    matrix_fingerprint = str(contracts.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        issues.append({"id": "invalid-interaction-matrix-fingerprint"})
    passed = 0
    for contract_id, contract in expected.items():
        _, contract_issues = _validate_native_observation(
            contract_id,
            contract,
            native_root=native_observation_root,
            reference_id=str(contracts.get("reference_id", "")),
            expected_app=expected_app,
            matrix_fingerprint=matrix_fingerprint,
        )
        issues.extend(contract_issues)
        if not contract_issues:
            passed += 1
    return {
        "version": "1.0",
        "reference_id": contracts.get("reference_id"),
        "matrix_fingerprint": contracts.get("matrix_fingerprint"),
        "contract_count": len(expected),
        "passed": passed,
        "issue_count": len(issues),
        "gate": "passed" if expected and not issues else "blocked",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--contracts",
        type=Path,
        default=ROOT / "configs/parity/core-interaction-matrix.json",
    )
    parser.add_argument("--execution", type=Path)
    parser.add_argument("--native-observations", type=Path)
    parser.add_argument("--native-only", action="store_true")
    parser.add_argument("--frontend-root", type=Path, default=ROOT / "frontend")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    contracts = json.loads(args.contracts.read_text(encoding="utf-8"))
    native_root = (
        args.native_observations or profile.observations_root / "interactions"
    ).resolve()
    expected_app = {
        "version": profile.version,
        "build": profile.build,
        "bundle_id": profile.bundle_id,
    }
    if args.native_only:
        report = validate_native_observations(
            contracts,
            native_observation_root=native_root,
            expected_app=expected_app,
        )
    else:
        execution_path = (
            args.execution or profile.diagnostics_root / "interaction-browser-execution.json"
        ).resolve()
        if execution_path.is_file():
            execution = json.loads(execution_path.read_text(encoding="utf-8"))
        else:
            execution = {"records": []}
        report = validate_execution(
            contracts,
            execution,
            execution_root=execution_path.parent,
            native_observation_root=native_root,
            expected_app=expected_app,
            frontend_root=args.frontend_root.resolve(),
        )
    output = (args.output or profile.diagnostics_root / "interaction-execution.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
