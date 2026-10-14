from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.validate_interaction_execution import (
    validate_execution,
    validate_native_observations,
)


def _contracts() -> dict[str, object]:
    return {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "logical_viewport": [1440, 900],
        "device_scale_factor": 2,
        "physical_viewport": [2880, 1800],
        "records": [
            {
                "id": "example",
                "events": [{"action": "click", "target": "button"}],
                "visible_assertions": ["visible"],
                "api_assertions": ["called-once"],
                "allowed_wait_conditions": ["ready"],
                "final_screenshot_state": "edit",
            }
        ],
    }


def _native_observation(tmp_path: Path) -> Path:
    root = tmp_path / "native"
    observation_root = root / "example"
    observation_root.mkdir(parents=True)
    artifacts = {
        "before_screenshot": observation_root / "before.png",
        "after_screenshot": observation_root / "after.png",
        "accessibility_snapshot": observation_root / "window.ax.json",
    }
    for path in artifacts.values():
        path.write_bytes(b"evidence")
    payload = {
        "contract_id": "example",
        "reference_id": "reference",
        "app_version": {
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
        "matrix_fingerprint": "c" * 64,
        "fixture_hash": "a" * 64,
        "capture_environment": {
            "native_full_screen": True,
            "capture_mode": "local-physical-display",
            "display_session_verified": True,
            "automation_input_verified": True,
            "user_authorized_local_capture": True,
            "capture_provider": "fixture-provider",
            "capture_session_id": "fixture-session",
            "capture_verified_at": "2026-09-01T00:00:00Z",
            "window_bounds": {"x": 0, "y": 0, "width": 1440, "height": 900},
        },
        "events": [{"action": "click", "target": "button"}],
        "visible_assertions": ["visible"],
        "wait_conditions": ["ready"],
        "final_state": "edit",
    }
    for field, path in artifacts.items():
        payload[field] = path.name
        payload[f"{field}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    observation = observation_root / "observation.json"
    observation.write_text(json.dumps(payload), encoding="utf-8")
    return observation


def _validate(tmp_path: Path, execution: dict[str, object]) -> dict[str, object]:
    return validate_execution(
        _contracts(),
        execution,
        execution_root=tmp_path,
        native_observation_root=tmp_path / "native",
        expected_app={
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
    )


def _browser_artifacts(tmp_path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in (
        "dom_snapshot",
        "accessibility_tree",
        "execution_trace",
        "network_trace",
        "console_log",
    ):
        path = tmp_path / f"{field}.json"
        path.write_text(json.dumps({"artifact": field}), encoding="utf-8")
        result[field] = path.name
        result[f"{field}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def test_execution_requires_browser_evidence(tmp_path: Path) -> None:
    report = _validate(tmp_path, {"records": []})

    assert report["gate"] == "blocked"
    assert {item["id"] for item in report["issues"]} >= {
        "missing-execution",
        "incomplete-browser-environment",
        "reference-id-mismatch",
        "missing-native-observation",
    }


def test_native_only_validation_does_not_require_browser_execution(tmp_path: Path) -> None:
    _native_observation(tmp_path)

    report = validate_native_observations(
        _contracts(),
        native_observation_root=tmp_path / "native",
        expected_app={
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
    )

    assert report["gate"] == "passed"
    assert report["passed"] == 1
    assert report["issue_count"] == 0


def test_native_only_validation_rejects_source_contract_id_alias(tmp_path: Path) -> None:
    _native_observation(tmp_path)
    contracts = _contracts()
    contracts["records"][0]["id"] = "workflow:example"
    contracts["records"][0]["source_contract_id"] = "example"

    report = validate_native_observations(
        contracts,
        native_observation_root=tmp_path / "native",
        expected_app={
            "version": "1.28.0",
            "build": "23071",
            "bundle_id": "com.skylum.luminarneo",
        },
    )

    assert report["gate"] == "blocked"
    assert report["passed"] == 0
    assert report["issues"] == [
        {"id": "missing-native-observation", "contract": "workflow:example"}
    ]


def test_execution_passes_only_with_complete_contract_evidence(tmp_path: Path) -> None:
    observation = _native_observation(tmp_path)
    screenshot = tmp_path / "final.png"
    screenshot.write_bytes(b"png")
    execution = {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "environment": {
            "browser": "chromium",
            "browser_version": "1",
            "logical_viewport": [1440, 900],
            "device_scale_factor": 2,
            "physical_viewport": [2880, 1800],
            "locale": "zh-Hans",
            "timezone": "Asia/Shanghai",
            "build_hash": "a" * 64,
        },
        "records": [
            {
                "id": "example",
                "status": "passed",
                "event_count": 1,
                "visible_assertions": ["visible"],
                "api_assertions": {"called-once": True},
                "wait_conditions": ["ready"],
                "fixed_sleep": False,
                "final_screenshot": "final.png",
                "final_screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                "native_observation": str(observation.relative_to(tmp_path)),
                "native_observation_sha256": hashlib.sha256(observation.read_bytes()).hexdigest(),
                **_browser_artifacts(tmp_path),
            }
        ],
    }

    report = _validate(tmp_path, execution)

    assert report["gate"] == "passed"
    assert report["executed"] == 1
    assert report["passed"] == 1
    assert report["issue_count"] == 0


def test_execution_rejects_partial_assertions_and_fixed_sleep(tmp_path: Path) -> None:
    observation = _native_observation(tmp_path)
    screenshot = tmp_path / "final.png"
    screenshot.write_bytes(b"png")
    execution = {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "environment": {
            "browser": "chromium",
            "browser_version": "1",
            "logical_viewport": [1440, 900],
            "device_scale_factor": 2,
            "physical_viewport": [2880, 1800],
            "locale": "zh-Hans",
            "timezone": "Asia/Shanghai",
            "build_hash": "a" * 64,
        },
        "records": [
            {
                "id": "example",
                "status": "passed",
                "event_count": 1,
                "visible_assertions": [],
                "api_assertions": [],
                "wait_conditions": ["unknown"],
                "fixed_sleep": True,
                "final_screenshot": "final.png",
                "final_screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                "native_observation": str(observation.relative_to(tmp_path)),
                "native_observation_sha256": hashlib.sha256(observation.read_bytes()).hexdigest(),
                **_browser_artifacts(tmp_path),
            }
        ],
    }

    report = _validate(tmp_path, execution)

    assert report["gate"] == "blocked"
    assert {item["id"] for item in report["issues"]} >= {
        "visible-assertions-incomplete",
        "api-assertions-incomplete",
        "undeclared-execution-wait",
        "fixed-sleep-forbidden",
    }


def test_execution_rejects_native_observation_hash_mismatch(tmp_path: Path) -> None:
    observation = _native_observation(tmp_path)
    screenshot = tmp_path / "final.png"
    screenshot.write_bytes(b"png")
    execution = {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "environment": {
            "browser": "in-app",
            "browser_version": "1",
            "logical_viewport": [1440, 900],
            "device_scale_factor": 2,
            "physical_viewport": [2880, 1800],
            "locale": "zh-Hans",
            "timezone": "Asia/Shanghai",
            "build_hash": "a" * 64,
        },
        "records": [
            {
                "id": "example",
                "status": "passed",
                "event_count": 1,
                "visible_assertions": ["visible"],
                "api_assertions": ["called-once"],
                "wait_conditions": ["ready"],
                "fixed_sleep": False,
                "final_screenshot": "final.png",
                "final_screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                "native_observation": str(observation.relative_to(tmp_path)),
                "native_observation_sha256": "0" * 64,
                **_browser_artifacts(tmp_path),
            }
        ],
    }

    report = _validate(tmp_path, execution)

    assert report["gate"] == "blocked"
    assert any(issue["id"] == "native-observation-hash-mismatch" for issue in report["issues"])
