import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_interaction_browser_execution import build_execution


def _contracts() -> dict:
    return {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "logical_viewport": [1440, 900],
        "device_scale_factor": 2,
        "physical_viewport": [2880, 1800],
        "records": [
            {
                "id": "toggle",
                "events": [{"action": "click", "target": "工具"}],
                "visible_assertions": ["canvas-expanded"],
                "api_assertions": ["project-unchanged"],
                "allowed_wait_conditions": ["layout-settled"],
            }
        ],
    }


def _raw() -> dict:
    return {
        "reference_id": "reference",
        "matrix_fingerprint": "c" * 64,
        "environment": {
            "browser": "browser",
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
                "id": "toggle",
                "status": "passed",
                "events": [{"action": "click", "target": "工具"}],
                "visible_assertions": ["canvas-expanded"],
                "api_assertions": ["project-unchanged"],
                "wait_conditions": ["layout-settled"],
                "fixed_sleep": False,
                "final_screenshot": "toggle/final.png",
                "dom_snapshot": "toggle/dom.json",
                "accessibility_tree": "toggle/ax.json",
                "execution_trace": "toggle/execution.json",
                "network_trace": "toggle/network.json",
                "console_log": "toggle/console.json",
            }
        ],
    }


def test_builder_links_browser_and_native_artifacts(tmp_path: Path) -> None:
    evidence = tmp_path / "browser"
    screenshot = evidence / "toggle/final.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"png")
    for name in ("dom.json", "ax.json", "execution.json", "network.json", "console.json"):
        (screenshot.parent / name).write_text(
            json.dumps({"artifact": name}), encoding="utf-8"
        )
    native = tmp_path / "native/toggle/observation.json"
    native.parent.mkdir(parents=True)
    native.write_text(json.dumps({"contract_id": "toggle"}), encoding="utf-8")

    payload = build_execution(
        _contracts(),
        _raw(),
        evidence_root=evidence,
        native_root=tmp_path / "native",
        output_root=tmp_path,
    )

    record = payload["records"][0]
    assert record["event_count"] == 1
    assert len(record["final_screenshot_sha256"]) == 64
    assert record["native_observation"] == native.resolve().as_posix()
    assert record["dom_snapshot_sha256"] == hashlib.sha256(
        (screenshot.parent / "dom.json").read_bytes()
    ).hexdigest()


def test_builder_rejects_native_observation_from_source_contract_id_alias(
    tmp_path: Path,
) -> None:
    contracts = _contracts()
    contracts["records"][0]["id"] = "workflow:toggle"
    contracts["records"][0]["source_contract_id"] = "toggle"
    raw = _raw()
    raw["records"][0]["id"] = "workflow:toggle"

    evidence = tmp_path / "browser"
    artifacts = evidence / "toggle"
    artifacts.mkdir(parents=True)
    (artifacts / "final.png").write_bytes(b"png")
    for name in ("dom.json", "ax.json", "execution.json", "network.json", "console.json"):
        (artifacts / name).write_text(
            json.dumps({"artifact": name}), encoding="utf-8"
        )
    for field, name in (
        ("final_screenshot", "final.png"),
        ("dom_snapshot", "dom.json"),
        ("accessibility_tree", "ax.json"),
        ("execution_trace", "execution.json"),
        ("network_trace", "network.json"),
        ("console_log", "console.json"),
    ):
        raw["records"][0][field] = f"toggle/{name}"
    native = tmp_path / "native/toggle/observation.json"
    native.parent.mkdir(parents=True)
    native.write_text(json.dumps({"contract_id": "toggle"}), encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="workflow:toggle"):
        build_execution(
            contracts,
            raw,
            evidence_root=evidence,
            native_root=tmp_path / "native",
            output_root=tmp_path,
        )


def test_builder_rejects_fixed_sleep(tmp_path: Path) -> None:
    raw = _raw()
    raw["records"][0]["fixed_sleep"] = True

    with pytest.raises(ValueError, match="fixed_sleep=false"):
        build_execution(
            _contracts(),
            raw,
            evidence_root=tmp_path,
            native_root=tmp_path,
            output_root=tmp_path,
        )


def test_builder_rejects_viewport_contract_mismatch(tmp_path: Path) -> None:
    raw = _raw()
    raw["environment"]["logical_viewport"] = [1280, 720]

    with pytest.raises(ValueError, match="logical_viewport"):
        build_execution(
            _contracts(),
            raw,
            evidence_root=tmp_path,
            native_root=tmp_path,
            output_root=tmp_path,
        )
