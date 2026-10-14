"""Fail-closed preflight checks for native Luminar sampling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

from .accessibility_driver import AccessibilityNode
from .app_controller import WindowBounds


@dataclass(frozen=True)
class NativeCaptureRequirements:
    """Exact native environment required by one immutable reference build."""

    reference_id: str
    app_version: str
    app_build: str
    bundle_id: str
    locale: str
    logical_viewport: tuple[int, int]
    physical_viewport: tuple[int, int]
    environment_evidence_path: Path


class PreflightController(Protocol):
    def version(self) -> dict[str, str]: ...

    def launch(self, *, timeout_seconds: float = 30.0) -> None: ...

    def activate(self) -> None: ...

    def ensure_window(self, *, timeout_seconds: float = 10.0) -> None: ...

    def screenshot_window(self, output: Path): ...

    def window_bounds(self) -> WindowBounds: ...


class PreflightDriver(Protocol):
    def activate(self) -> None: ...

    def state(self) -> dict[str, object]: ...

    def snapshot(self) -> tuple[AccessibilityNode, ...]: ...

    def write_snapshot(
        self, path: Path, nodes: tuple[AccessibilityNode, ...]
    ) -> None: ...


def run_preflight(
    controller: PreflightController,
    driver: PreflightDriver,
    *,
    output_dir: Path,
    timeout_seconds: float,
    requirements: NativeCaptureRequirements,
) -> dict[str, object]:
    """Verify the exact app, viewport, locale and isolated native session."""

    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / "window.png"
    accessibility_path = output_dir / "window.ax.json"

    controller.launch(timeout_seconds=timeout_seconds)
    controller.activate()
    controller.ensure_window(timeout_seconds=timeout_seconds)
    driver.activate()

    actual_app = controller.version()
    expected_app = {
        "version": requirements.app_version,
        "build": requirements.app_build,
        "bundle_id": requirements.bundle_id,
    }
    app_mismatches = {
        key: {"expected": expected, "actual": actual_app.get(key)}
        for key, expected in expected_app.items()
        if str(actual_app.get(key, "")) != expected
    }
    if app_mismatches:
        raise RuntimeError(f"Luminar app identity mismatch: {app_mismatches}")

    state = driver.state()
    window_count = int(state.get("window_count", 0))
    main_window_count = int(state.get("main_window_count", 0))
    if main_window_count != 1:
        raise RuntimeError(
            "Luminar must expose exactly one identified main window, "
            f"found {main_window_count} (all AX windows: {window_count})"
        )
    if state.get("frontmost") is not True:
        raise RuntimeError("Luminar is not the frontmost application")

    bounds = controller.window_bounds()
    logical_size = (bounds.width, bounds.height)
    if logical_size != requirements.logical_viewport:
        raise RuntimeError(
            "Luminar logical viewport mismatch: "
            f"{logical_size} != {requirements.logical_viewport}"
        )

    nodes = driver.snapshot()
    if not nodes:
        raise RuntimeError(
            "Luminar accessibility tree is empty; grant Accessibility permission "
            "to the Codex/terminal host and restart it"
        )
    driver.write_snapshot(accessibility_path, nodes)
    localized_values = {
        str(value)
        for node in nodes
        for value in (
            node.identifier,
            node.title,
            node.description,
            node.help,
            node.value,
        )
        if value is not None and value != ""
    }
    locale_markers: dict[str, str] = {}
    if requirements.locale == "zh-Hans":
        marker_groups = {
            "catalog": ("目录",),
            "presets": ("预置", "预设"),
            "edits": ("编辑",),
        }
        locale_markers = {
            name: next((marker for marker in markers if marker in localized_values), "")
            for name, markers in marker_groups.items()
        }
        missing_markers = [
            "/".join(marker_groups[name])
            for name, marker in locale_markers.items()
            if not marker
        ]
        if missing_markers:
            raise RuntimeError(
                "Luminar zh-Hans locale markers are missing: "
                + ", ".join(missing_markers)
            )

    controller.screenshot_window(screenshot_path)
    if not screenshot_path.is_file() or screenshot_path.stat().st_size <= 0:
        raise RuntimeError(
            "Luminar screenshot was not written; grant Screen Recording permission "
            "to the Codex/terminal host and restart it"
        )
    try:
        with Image.open(screenshot_path) as image:
            image.verify()
            screenshot_size = [image.width, image.height]
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Luminar screenshot is invalid: {exc}") from exc
    if tuple(screenshot_size) != requirements.physical_viewport:
        raise RuntimeError(
            "Luminar physical viewport mismatch: "
            f"{tuple(screenshot_size)} != {requirements.physical_viewport}"
        )

    evidence_path = requirements.environment_evidence_path.resolve()
    if not evidence_path.is_file():
        raise RuntimeError(f"native environment evidence is missing: {evidence_path}")
    try:
        environment = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"native environment evidence is invalid: {exc}") from exc
    expected_environment = {
        "reference_id": requirements.reference_id,
        "logical_viewport": list(requirements.logical_viewport),
        "physical_viewport": list(requirements.physical_viewport),
    }
    environment_mismatches = {
        key: {"expected": expected, "actual": environment.get(key)}
        for key, expected in expected_environment.items()
        if environment.get(key) != expected
    }
    evidence_app = environment.get("app") or {}
    for key, expected in {
        **expected_app,
        "locale": requirements.locale,
    }.items():
        if str(evidence_app.get(key, "")) != expected:
            environment_mismatches[f"app.{key}"] = {
                "expected": expected,
                "actual": evidence_app.get(key),
            }
    verification = environment.get("verification") or {}
    missing_verification = [
        key
        for key in ("provider", "session_id", "verified_at")
        if not verification.get(key)
    ]
    capture_failures = [
        key
        for key in (
            "display_session_verified",
            "automation_input_verified",
            "user_authorized_local_capture",
        )
        if environment.get(key) is not True
    ]
    if environment.get("capture_mode") != "local-physical-display":
        environment_mismatches["capture_mode"] = {
            "expected": "local-physical-display",
            "actual": environment.get("capture_mode"),
        }
    if environment_mismatches or missing_verification or capture_failures:
        raise RuntimeError(
            "native capture environment is not verified: "
            f"mismatches={environment_mismatches}, "
            f"missing_verification={missing_verification}, "
            f"capture_failures={capture_failures}"
        )

    return {
        "ok": True,
        "state": state,
        "app": actual_app,
        "locale": requirements.locale,
        "locale_markers": locale_markers,
        "logical_viewport": list(logical_size),
        "physical_viewport": screenshot_size,
        "environment_evidence": str(evidence_path),
        "capture_mode": "local-physical-display",
        "capture_provider": verification["provider"],
        "capture_session_id": verification["session_id"],
        "capture_verified_at": verification["verified_at"],
        "display_session_verified": True,
        "automation_input_verified": True,
        "user_authorized_local_capture": True,
        "node_count": len(nodes),
        "screenshot": str(screenshot_path),
        "screenshot_size": screenshot_size,
        "accessibility_snapshot": str(accessibility_path),
    }
