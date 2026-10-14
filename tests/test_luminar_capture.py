import hashlib
import json
import plistlib
from collections import deque
from pathlib import Path

import pytest
from PIL import Image

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.accessibility_driver import (
    AccessibilityNode,
    LuminarAccessibilityDriver,
)
from scripts.luminar_capture.app_controller import LuminarAppController, WindowBounds
from scripts.luminar_capture.auto_sampler import (
    NonRetryableCaptureError,
    build_native_export_stem,
    crop_native_preview,
    select_preview_node,
)
from scripts.luminar_capture.capture_runner import (
    _copy_as_png,
    finalize_case,
    import_computer_use_state,
)
from scripts.luminar_capture.case_reader import CaptureCase, load_cases
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.preflight import (
    NativeCaptureRequirements,
    run_preflight,
)
from scripts.luminar_capture.queue_handlers import LuminarQueueHandlers
from scripts.luminar_capture.semantic_locator import find_by_locator
from scripts.luminar_capture.stability import (
    normalized_image_change_metrics,
    normalized_image_mae,
    stable_screenshot_sequence,
)
from scripts.luminar_capture.state_machine import CaptureJournal, CaptureStatus
from scripts.run_luminar_auto_sampling import requires_ui_control


def test_native_export_name_is_readable_stable_and_filesystem_safe(tmp_path: Path) -> None:
    source = tmp_path / "夏日 portrait 01.jpg"
    source.write_bytes(b"source")
    case = CaptureCase(
        case_id="exact-face-ai",
        capability_id="face_ai",
        input_path=source,
        input_sha256="a" * 64,
        parameters={"amount": 0.65, "opacity": 1.0},
        asset_id=None,
    )

    stem = build_native_export_stem(case, "20260901T060620.259504+0000-ba2fe5ae")

    assert stem.startswith("luminar-neo__face-ai__portrait-01__amount-0-65__opacity-1-0__")
    assert stem.endswith("__20260901t060620-259504")
    assert len(stem) <= 180
    assert all(character.isalnum() or character in {"-", "_"} for character in stem)


def test_load_cases_filters_and_validates_source(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case",
                        "capability_id": "sky_replace",
                        "input": {
                            "path": str(source),
                            "sha256": hashlib.sha256(b"source").hexdigest(),
                        },
                        "parameters": {"amount": 0.5},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = load_cases(cases, case_ids={"case"})

    assert loaded[0].capability_id == "sky_replace"
    assert loaded[0].input_path == source


def test_copy_as_png_preserves_valid_rgb_png_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "destination.png"
    Image.new("RGB", (8, 6), (1, 2, 3)).save(source, compress_level=9)

    _copy_as_png(source, destination)

    assert destination.read_bytes() == source.read_bytes()


def test_finalize_case_writes_normalized_images_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    preview = tmp_path / "preview.jpg"
    exported = tmp_path / "export.jpg"
    Image.new("RGB", (8, 6), (1, 2, 3)).save(source)
    Image.new("RGB", (8, 6), (4, 5, 6)).save(preview)
    Image.new("RGB", (8, 6), (7, 8, 9)).save(exported)
    case = CaptureCase(
        case_id="case",
        capability_id="develop",
        input_path=source,
        input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        parameters={"amount": 0.4},
        asset_id=None,
    )
    layout = CaptureLayout(tmp_path / "captures", case.case_id)
    layout.prepare()
    Image.new("RGB", (16, 12), (10, 20, 30)).save(layout.staging_before_path)

    metadata = finalize_case(
        case,
        layout,
        preview_source=preview,
        export_source=exported,
        reference_build="luminar-neo-macos-1.26.0-21267",
        operator_mode="test",
        app_version={"version": "1.26.0", "build": "21267"},
    )

    assert layout.preview_path.is_file()
    assert layout.export_path.is_file()
    assert layout.before_path.is_file()
    assert metadata["sha256"]["preview"]
    assert metadata["sha256"]["export"]
    assert metadata["sha256"]["ui_before"]
    assert metadata["asset_path"] is None
    assert metadata["asset_sha256"] is None
    assert json.loads(layout.state_path.read_text())["status"] == "ready"


def test_native_preview_crop_uses_accessibility_bounds(tmp_path: Path) -> None:
    screenshot = tmp_path / "window.png"
    destination = tmp_path / "preview.png"
    Image.new("RGB", (200, 100), (10, 10, 10)).save(screenshot)
    node = AccessibilityNode(
        index=1,
        role="AXImage",
        subrole=None,
        identifier="main-preview",
        title=None,
        description="目录",
        help=None,
        value=None,
        min_value=None,
        max_value=None,
        enabled=True,
        focused=None,
        selected=None,
        position=(20, 10),
        size=(60, 40),
        orientation=None,
    )
    bounds = WindowBounds(0, 0, 100, 50)

    selected = select_preview_node((node,), bounds)
    driver = object.__new__(LuminarAccessibilityDriver)
    assert driver.has_locator("目录", (node,))
    crop_native_preview(
        screenshot, destination, node=selected, bounds=bounds
    )

    with Image.open(destination) as image:
        assert image.size == (120, 80)


def test_native_helper_targets_stable_bundle_identifier() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts/luminar_capture/native_helper.swift"
    ).read_text(encoding="utf-8")

    assert 'private let bundleIdentifier = "com.skylum.luminarneo"' in source
    assert "$0.bundleIdentifier == bundleIdentifier" in source
    assert "$0.localizedName == processName" not in source


def test_app_controller_uses_bundle_metadata_for_process_identity(tmp_path: Path) -> None:
    app = tmp_path / "Luminar Neo.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleExecutable": "Luminar",
                "CFBundleIdentifier": "com.skylum.luminarneo",
                "CFBundleShortVersionString": "1.28.1",
                "CFBundleVersion": "23487",
            },
            handle,
        )

    controller = LuminarAppController(app)

    assert controller.process_name == "Luminar"
    assert controller.bundle_id == "com.skylum.luminarneo"
    assert controller.version() == {
        "version": "1.28.1",
        "build": "23487",
        "bundle_id": "com.skylum.luminarneo",
    }
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts/luminar_capture/app_controller.py"
    )
    assert 'process "Luminar Neo"' not in source.read_text(encoding="utf-8")


def test_parameter_state_fails_closed_on_stale_binding_reference() -> None:
    handler = object.__new__(LuminarQueueHandlers)
    handler.reference_id = "luminar-neo-macos-1.28.1-23487"
    handler._native_parameter_binding_reference_id = (
        "luminar-neo-macos-1.28.0-23071"
    )

    with pytest.raises(RuntimeError, match="binding reference mismatch"):
        handler._apply_native_parameter_state(None, None, None)


def test_normalized_image_mae_detects_rendered_change(tmp_path: Path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    Image.new("RGB", (8, 6), (0, 0, 0)).save(left)
    Image.new("RGB", (16, 12), (255, 255, 255)).save(right)

    assert normalized_image_mae(left, right) == 1.0
    assert normalized_image_mae(left, right, size=4, mode="L") == 1.0


def test_change_metrics_detect_localized_strong_changes(tmp_path: Path) -> None:
    left = tmp_path / "left.png"
    right = tmp_path / "right.png"
    Image.new("RGB", (100, 100), (0, 0, 0)).save(left)
    changed = Image.new("RGB", (100, 100), (0, 0, 0))
    for x in range(10):
        for y in range(10):
            changed.putpixel((x, y), (255, 255, 255))
    changed.save(right)

    metrics = normalized_image_change_metrics(left, right, size=100)

    assert metrics["mae"] == pytest.approx(0.01)
    assert metrics["strong_changed_pixel_fraction"] == 0.01


def test_sampling_config_covers_active_parity_capabilities() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_luminar_sampling_config(root / "configs/luminar_sampling.yaml")
    profile = load_reference_catalog(project_root=root).resolve()
    payload = json.loads(profile.cases_path.read_text(encoding="utf-8"))
    capability_ids = {
        str(item["capability_id"])
        for item in payload["cases"]
        if str(item["capability_id"]) not in config.excluded_capabilities
    }

    assert config.reference_id == profile.id
    assert config.native_export_root == profile.diagnostics_root.parent / "native-exports"
    assert capability_ids <= set(config.recipes)
    assert config.excluded_capabilities == frozenset({"super_resolution"})
    assert config.page_order == ("catalog", "presets", "edit")
    assert set(config.ui_states) == set(config.ui_state_pages)
    assert set(config.ui_state_pages.values()) <= set(config.page_order)


def test_semantic_locator_finds_fresh_accessibility_index() -> None:
    tree = """
0 标准窗口, ID: MainWindow
  11 按钮 EditExpandButton_AIEnhanceAdjustmentLayer
  12 按钮 EditExpandButton_SkyReplacementAdjustmentLayer
"""

    element = find_by_locator(tree, "EditExpandButton_SkyReplacementAdjustmentLayer")

    assert element.index == 12


def test_computer_use_state_is_staged_and_hashed_on_finalize(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    screenshot = tmp_path / "screen.png"
    accessibility = tmp_path / "screen.ax.txt"
    preview = tmp_path / "preview.png"
    exported = tmp_path / "export.png"
    Image.new("RGB", (8, 6), (1, 2, 3)).save(source)
    Image.new("RGB", (16, 12), (10, 20, 30)).save(screenshot)
    Image.new("RGB", (8, 6), (4, 5, 6)).save(preview)
    Image.new("RGB", (8, 6), (7, 8, 9)).save(exported)
    accessibility.write_text("0 标准窗口, ID: MainWindow\n", encoding="utf-8")
    case = CaptureCase(
        case_id="computer-use",
        capability_id="ai_enhance",
        input_path=source,
        input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        parameters={"amount": 0.5},
        asset_id=None,
    )
    layout = CaptureLayout(tmp_path / "captures", case.case_id)

    import_computer_use_state(
        layout,
        stage="before",
        screenshot_source=screenshot,
        accessibility_source=accessibility,
    )
    metadata = finalize_case(
        case,
        layout,
        preview_source=preview,
        export_source=exported,
        reference_build="luminar-neo-macos-1.25.1-21065",
        operator_mode="computer-use",
        app_version={"version": "1.25.1", "build": "21065"},
    )

    assert layout.before_ax_path.read_text(encoding="utf-8").startswith("0 标准窗口")
    assert metadata["sha256"]["ax_before"]
    assert json.loads(layout.event_log_path.read_text().splitlines()[-1])["status"] == "ready"


def test_capture_journal_preserves_attempt_events(tmp_path: Path) -> None:
    layout = CaptureLayout(tmp_path / "captures", "case")
    journal = CaptureJournal(layout)

    journal.transition(CaptureStatus.APP_READY, window="Luminar Neo")
    state = journal.transition(CaptureStatus.BASELINE_VERIFIED, photo="sample.jpg")

    assert [item["status"] for item in journal.events()] == [
        "preparing",
        "app-ready",
        "baseline-verified",
    ]
    assert all(
        item.get("stage_duration_ms", 0) >= 0
        for item in journal.events()[1:]
    )
    assert all(
        item.get("attempt_duration_ms", 0) >= 0
        for item in journal.events()[1:]
    )
    assert state["schema_version"] == 2


def test_failed_retry_does_not_replace_canonical_ready_capture(tmp_path: Path) -> None:
    layout = CaptureLayout(tmp_path / "captures", "case")
    journal = CaptureJournal(layout)
    first = journal.transition(CaptureStatus.READY, metadata="metadata/case.json")
    canonical_attempt = first["canonical"]["attempt_id"]

    journal.begin_attempt(reason="verification-rerun")
    state = journal.fail("Accessibility permission is not granted")

    assert state["status"] == "ready"
    assert state["canonical"]["attempt_id"] == canonical_attempt
    assert state["last_attempt"]["status"] == "failed"
    assert len(list(layout.attempts_dir.glob("*.json"))) == 2


def test_workflow_resume_requires_the_same_input_hashes(tmp_path: Path) -> None:
    layout = CaptureLayout(tmp_path / "captures", "workflow")
    journal = CaptureJournal(layout)
    input_paths = [tmp_path / "one.jpg", tmp_path / "two.jpg"]
    journal.transition(
        CaptureStatus.TOOL_OPENED,
        workflow="hdr_merge",
        inputs=[str(path) for path in input_paths],
        input_sha256s=["one", "two"],
    )

    assert LuminarQueueHandlers._workflow_was_started(
        journal,
        "hdr_merge",
        input_paths,
        [{"sha256": "one"}, {"sha256": "two"}],
    )
    assert not LuminarQueueHandlers._workflow_was_started(
        journal,
        "hdr_merge",
        input_paths,
        [{"sha256": "changed"}, {"sha256": "two"}],
    )


def test_stable_screenshot_sequence_uses_recent_samples(tmp_path: Path) -> None:
    paths = [tmp_path / f"sample-{index}.png" for index in range(3)]
    for path in paths:
        Image.new("RGB", (8, 6), (10, 20, 30)).save(path)

    assert stable_screenshot_sequence(paths, required=3, mae_max=0.0)


def test_stable_screenshot_sequence_accepts_capture_deque(tmp_path: Path) -> None:
    paths = deque(tmp_path / f"sample-{index}.png" for index in range(3))
    for path in paths:
        Image.new("RGB", (8, 6), (10, 20, 30)).save(path)

    assert stable_screenshot_sequence(paths, required=3, mae_max=0.0)


def test_existing_luminar_window_is_not_reopened(monkeypatch) -> None:
    controller = object.__new__(LuminarAppController)
    monkeypatch.setattr(controller, "_window_count", lambda: 1)

    def fail_if_reopened(command: list[str]) -> None:
        raise AssertionError(f"existing window should not be reopened: {command}")

    monkeypatch.setattr(controller, "_run", fail_if_reopened)

    controller.ensure_window(timeout_seconds=0.1)


def test_ui_control_guard_allows_only_dry_run_without_authorization() -> None:
    assert not requires_ui_control(preflight=False, dry_run=True)
    assert requires_ui_control(preflight=True, dry_run=False)
    assert requires_ui_control(preflight=True, dry_run=True)
    assert requires_ui_control(preflight=False, dry_run=False)


def test_preflight_requires_non_empty_accessibility_tree(tmp_path: Path) -> None:
    class Controller:
        def launch(self, *, timeout_seconds: float = 30.0) -> None:
            pass

        def activate(self) -> None:
            pass

        def ensure_window(self, *, timeout_seconds: float = 10.0) -> None:
            pass

        def version(self) -> dict[str, str]:
            return {
                "version": "1.28.0",
                "build": "23071",
                "bundle_id": "com.skylum.luminarneo",
            }

        def window_bounds(self) -> WindowBounds:
            return WindowBounds(0, 0, 8, 6)

        def screenshot_window(self, output: Path) -> None:
            Image.new("RGB", (8, 6), (1, 2, 3)).save(output)

    class Driver:
        def activate(self) -> None:
            pass

        def state(self) -> dict[str, object]:
            return {
                "ok": True,
                "frontmost": True,
                "window_count": 1,
                "main_window_count": 1,
            }

        def snapshot(self):
            return ()

        def write_snapshot(self, path: Path, nodes) -> None:
            raise AssertionError("empty trees must not be persisted")

    try:
        run_preflight(
            Controller(),
            Driver(),
            output_dir=tmp_path,
            timeout_seconds=1.0,
            requirements=NativeCaptureRequirements(
                reference_id="luminar-neo-macos-1.28.0-23071",
                app_version="1.28.0",
                app_build="23071",
                bundle_id="com.skylum.luminarneo",
                locale="zh-Hans",
                logical_viewport=(8, 6),
                physical_viewport=(8, 6),
                environment_evidence_path=tmp_path / "environment.json",
            ),
        )
    except RuntimeError as exc:
        assert "tree is empty" in str(exc)
    else:
        raise AssertionError("empty accessibility tree must block sampling")


@pytest.mark.parametrize("preset_marker", ["预置", "预设"])
def test_preflight_blocks_unverified_local_capture_session(
    tmp_path: Path, preset_marker: str
) -> None:
    class Controller:
        def launch(self, *, timeout_seconds: float = 30.0) -> None:
            pass

        def activate(self) -> None:
            pass

        def ensure_window(self, *, timeout_seconds: float = 10.0) -> None:
            pass

        def version(self) -> dict[str, str]:
            return {
                "version": "1.28.0",
                "build": "23071",
                "bundle_id": "com.skylum.luminarneo",
            }

        def window_bounds(self) -> WindowBounds:
            return WindowBounds(0, 0, 8, 6)

        def screenshot_window(self, output: Path) -> None:
            Image.new("RGB", (16, 12), (1, 2, 3)).save(output)

    def node(index: int, title: str) -> AccessibilityNode:
        return AccessibilityNode(
            index=index,
            role="AXButton",
            subrole=None,
            identifier=None,
            title=title,
            description=None,
            help=None,
            value=None,
            min_value=None,
            max_value=None,
            enabled=True,
            focused=None,
            selected=None,
            position=None,
            size=None,
            orientation=None,
        )

    class Driver:
        def activate(self) -> None:
            pass

        def state(self) -> dict[str, object]:
            return {
                "frontmost": True,
                "window_count": 3,
                "main_window_count": 1,
            }

        def snapshot(self):
            return (node(0, "目录"), node(1, preset_marker), node(2, "编辑"))

        def write_snapshot(self, path: Path, nodes) -> None:
            path.write_text("[]", encoding="utf-8")

    evidence = tmp_path / "environment.json"
    evidence.write_text(
        json.dumps(
            {
                "reference_id": "luminar-neo-macos-1.28.0-23071",
                "app": {
                    "version": "1.28.0",
                    "build": "23071",
                    "bundle_id": "com.skylum.luminarneo",
                    "locale": "zh-Hans",
                },
                "logical_viewport": [8, 6],
                "physical_viewport": [16, 12],
                "capture_mode": "local-physical-display",
                "display_session_verified": False,
                "automation_input_verified": False,
                "user_authorized_local_capture": False,
                "verification": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="capture_failures"):
        run_preflight(
            Controller(),
            Driver(),
            output_dir=tmp_path / "preflight",
            timeout_seconds=1.0,
            requirements=NativeCaptureRequirements(
                reference_id="luminar-neo-macos-1.28.0-23071",
                app_version="1.28.0",
                app_build="23071",
                bundle_id="com.skylum.luminarneo",
                locale="zh-Hans",
                logical_viewport=(8, 6),
                physical_viewport=(16, 12),
                environment_evidence_path=evidence,
            ),
        )


def test_tool_local_reset_proves_canvas_edit_before_panel_close() -> None:
    class Sampler:
        @staticmethod
        def _verify_photo_has_edits() -> dict[str, object]:
            raise NonRetryableCaptureError("global restore is deferred")

    reset = AccessibilityNode(
        index=7,
        role="AXButton",
        subrole=None,
        identifier="Luminar_Neo.AdjustListHeaderView.Erase.ResetButton",
        title=None,
        description=None,
        help="重置工具",
        value=None,
        min_value=None,
        max_value=None,
        enabled=True,
        focused=None,
        selected=None,
        position=None,
        size=None,
        orientation=None,
    )
    handler = object.__new__(LuminarQueueHandlers)
    handler.sampler = Sampler()

    evidence = handler._verify_native_edit_state((reset,))

    assert evidence == {
        "required": True,
        "verified": True,
        "locator_id": "Luminar_Neo.AdjustListHeaderView.Erase.ResetButton",
        "enabled": True,
        "scope": "tool",
        "global_restore_deferred_until_tool_close": True,
    }
