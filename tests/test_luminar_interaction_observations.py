from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

import scripts.run_luminar_interaction_observations as observations
from scripts.luminar_capture.accessibility_driver import AccessibilityNode
from scripts.run_luminar_interaction_observations import (
    _contract_supported,
    _observation_valid,
    _observe_before_after_compare,
    _observe_edit_toggle_collapse,
    _observe_multi_image_three_workflows,
    _selected_contracts,
    _write_blocked_observation,
)


def _node(
    identifier: str,
    position: tuple[int, int],
    *,
    title: str | None = None,
    help_text: str | None = None,
    size: tuple[int, int] = (400, 600),
) -> AccessibilityNode:
    role = "AXWindow" if identifier == "window" else (
        "AXImage" if identifier == "PreviewImage" else "AXButton"
    )
    return AccessibilityNode(
        index=0,
        role=role,
        subrole=None,
        identifier=identifier,
        title=title,
        description=None,
        help=help_text,
        value=None,
        min_value=None,
        max_value=None,
        enabled=True,
        focused=None,
        selected=None,
        position=position,
        size=size,
        orientation=None,
    )


class FakeDriver:
    def __init__(self) -> None:
        self.states = [
            (
                _node("window", (0, 0), title="008_e45cd3c34a.jpg"),
                _node("PreviewImage", (300, 70)),
                _node("EditExpandButton_DefaultEffects", (0, 0)),
            ),
            (_node("PreviewImage", (440, 70)),),
            (_node("PreviewImage", (300, 70)), _node("EditExpandButton_DefaultEffects", (0, 0))),
        ]
        self.index = 0

    def activate(self) -> None:
        return None

    def snapshot(self):
        state = self.states[min(self.index, len(self.states) - 1)]
        self.index += 1
        return state

    def press_first(self, locator: str) -> None:
        assert locator == "NavigationPanel.Tab.Tools"

    def write_snapshot(self, path: Path, nodes) -> None:
        path.write_text(json.dumps({"nodes": len(nodes)}), encoding="utf-8")


class FakeController:
    def request_open_image(self, path: Path) -> Path:
        raise AssertionError("fixture is already open")

    def screenshot_window(self, output: Path):
        output.write_bytes(b"screenshot")


class FakeCompareDriver:
    def __init__(self) -> None:
        self.source_visible = False

    def activate(self) -> None:
        return None

    def snapshot(self):
        return (
            _node("window", (0, 0), title="008_e45cd3c34a.jpg", size=(1200, 900)),
            _node("PreviewImage", (300, 70), size=(600, 700)),
            _node("compare", (1000, 820), help_text="预览 [ \\ ]", size=(60, 40)),
        )

    def mouse_down_at(self, x: int, y: int) -> None:
        assert (x, y) == (1030, 840)
        self.source_visible = True

    def mouse_up_at(self, x: int, y: int) -> None:
        assert (x, y) == (1030, 840)
        self.source_visible = False

    def write_snapshot(self, path: Path, nodes) -> None:
        path.write_text(json.dumps({"nodes": len(nodes)}), encoding="utf-8")


class FakeCompareController:
    def __init__(self, driver: FakeCompareDriver) -> None:
        self.driver = driver

    def request_open_image(self, path: Path) -> Path:
        raise AssertionError("fixture is already open")

    def screenshot_window(self, output: Path):
        image = Image.new("RGB", (1200, 900), "#111111")
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (300, 70, 900, 770),
            fill="#eeeeee" if self.driver.source_visible else "#555555",
        )
        image.save(output)


def test_edit_toggle_observation_checks_native_layout(tmp_path: Path) -> None:
    evidence = _observe_edit_toggle_collapse(FakeDriver(), FakeController(), tmp_path)

    assert evidence["visible_assertions"] == [
        "canvas-expands-when-collapsed",
        "editor-panels-restored",
    ]
    assert evidence["assertion_evidence"]["collapsed_preview_position"] == (440, 70)
    assert (tmp_path / "accessibility.json").is_file()


def test_before_after_observation_requires_visual_change_and_restore(
    tmp_path: Path, monkeypatch,
) -> None:
    driver = FakeCompareDriver()
    monkeypatch.setattr(
        observations,
        "_observe_preset_apply",
        lambda *args: {
            "before_screenshot": "before.png",
            "assertion_evidence": {
                "restore_original_performed": True,
                "before_preview_sha256": "original",
            },
        },
    )
    evidence = _observe_before_after_compare(
        driver, FakeCompareController(driver), tmp_path
    )

    assert evidence["assertion_evidence"]["source_differs_from_edited"] is True
    assert evidence["assertion_evidence"]["restored_matches_edited"] is True
    assert (tmp_path / "source.png").is_file()
    assert (tmp_path / "after.png").is_file()
    assert not (tmp_path / "source.pending.png").exists()


def test_resume_requires_matching_artifact_hashes(tmp_path: Path) -> None:
    for name in ("before.png", "after.png", "accessibility.json"):
        (tmp_path / name).write_bytes(b"evidence")
    import hashlib

    digest = hashlib.sha256(b"evidence").hexdigest()
    payload = {
        "app_version": {"version": "1", "build": "2", "bundle_id": "bundle"},
        "contract_id": "workflow:example",
        "matrix_fingerprint": "c" * 64,
        "before_screenshot": "before.png",
        "before_screenshot_sha256": digest,
        "after_screenshot": "after.png",
        "after_screenshot_sha256": digest,
        "accessibility_snapshot": "accessibility.json",
        "accessibility_snapshot_sha256": digest,
    }
    observation = tmp_path / "observation.json"
    observation.write_text(json.dumps(payload), encoding="utf-8")

    assert _observation_valid(
        observation,
        app_version=payload["app_version"],
        contract_id="workflow:example",
        matrix_fingerprint="c" * 64,
    )
    (tmp_path / "after.png").write_bytes(b"changed")
    assert not _observation_valid(
        observation,
        app_version=payload["app_version"],
        contract_id="workflow:example",
        matrix_fingerprint="c" * 64,
    )


def test_blocked_observation_keeps_partial_artifact_hashes(tmp_path: Path) -> None:
    partial = tmp_path / "panorama" / "plugin.png"
    partial.parent.mkdir()
    partial.write_bytes(b"partial")
    output = tmp_path / "blocked-observation.json"

    _write_blocked_observation(
        output,
        contract_id="multi-image-three-workflows",
        reference_id="reference",
        app_version={"version": "1", "build": "2", "bundle_id": "bundle"},
        matrix_fingerprint="c" * 64,
        capture_environment={"native_full_screen": True},
        error=TimeoutError("panorama post-process stage 继续"),
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["gate"] == "blocked"
    assert payload["error_type"] == "TimeoutError"
    assert payload["artifact_sha256s"] == {
        "panorama/plugin.png": observations._sha256(partial)
    }


def test_multi_image_observation_aggregates_source_reset_evidence(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(
        observations,
        "_run_multi_image_workflow",
        lambda *args: {
            "source_edits_reset": True,
            "restore_original_performed": False,
        },
    )

    evidence = _observe_multi_image_three_workflows(
        FakeDriver(), FakeController(), tmp_path
    )

    assert evidence["assertion_evidence"]["source_edits_reset"] is True
    assert evidence["assertion_evidence"]["workflow_count"] == 3


def test_contract_selection_rejects_unknown_id() -> None:
    contracts = {"records": [{"id": "one"}]}
    assert _selected_contracts(contracts, "one") == [{"id": "one"}]
    try:
        _selected_contracts(contracts, "missing")
    except ValueError as exc:
        assert "unknown interaction contract" in str(exc)
    else:
        raise AssertionError("unknown contract must fail")


def test_contract_support_includes_audited_parameter_bindings() -> None:
    contract = {
        "id": "tool:details:parameter:amount",
        "kind": "tool-parameter-contract",
        "capability_id": "details",
        "parameter": "amount",
    }
    bindings = {
        "tool:details:parameter:amount:modified": {
            "status": "supported",
            "native": {"kind": "slider"},
        }
    }

    assert _contract_supported(contract, bindings)
    assert not _contract_supported(contract, {})
