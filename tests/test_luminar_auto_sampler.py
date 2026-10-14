import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from configs.luminar_sampling import SamplingRecipe
from scripts.luminar_capture.accessibility_driver import AccessibilityNode
from scripts.luminar_capture.app_controller import WindowBounds
from scripts.luminar_capture.auto_sampler import (
    AdvanceActivationCaptureError,
    LuminarAutoSampler,
    NonRetryableCaptureError,
    asset_picker_scroll_value,
    control_readback_matches,
    discover_new_controls,
    embedded_category_thumbnails,
    export_signature_changed,
    normalize_recipe_value,
    normalized_preview_stroke,
    render_change_required,
    rendered_source_matches,
    select_asset_thumbnail,
    select_primary_slider,
    select_recipe_slider,
    select_replacement_locator,
    select_unique_control,
    slider_click_position,
    thumbnail_match_is_confident,
)
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.state_machine import CaptureStatus


def _node(
    index: int,
    *,
    role: str,
    identifier: str | None,
    value: float | str | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    position: tuple[int, int] = (1000, 100),
) -> AccessibilityNode:
    return AccessibilityNode(
        index=index,
        role=role,
        subrole=None,
        identifier=identifier,
        title=None,
        description=None,
        help=None,
        value=value,
        min_value=minimum,
        max_value=maximum,
        enabled=True,
        focused=False,
        selected=False,
        position=position,
        size=(200, 20),
        orientation=None,
    )


def test_discovers_only_new_enabled_parameter_controls() -> None:
    existing = _node(1, role="AXSlider", identifier="existing", value=0)
    added = _node(2, role="AXSlider", identifier="amount", value=0)
    label = _node(3, role="AXStaticText", identifier="label", value="Amount")

    controls = discover_new_controls((existing,), (existing, added, label))

    assert controls == (added,)


def test_primary_slider_uses_topmost_new_slider() -> None:
    lower = _node(2, role="AXSlider", identifier="lower", position=(1000, 500))
    upper = _node(1, role="AXSlider", identifier="upper", position=(1000, 300))

    assert select_primary_slider((lower, upper)) == upper


def test_primary_slider_prefers_writable_inner_control() -> None:
    wrapper = AccessibilityNode(
        **{
            **_node(
                1,
                role="AXSlider",
                identifier="Slider.Amount",
                position=(1000, 300),
            ).__dict__,
            "enabled": None,
        }
    )
    writable = _node(
        2,
        role="AXSlider",
        identifier="Slider.Amount.Slider",
        position=(1000, 318),
    )

    assert select_primary_slider((wrapper, writable)) == writable


def test_recipe_slider_requires_the_exact_writable_identifier() -> None:
    amount = _node(1, role="AXSlider", identifier="Slider.Amount.Slider")
    contrast = _node(2, role="AXSlider", identifier="Slider.Contrast.Slider")

    assert select_recipe_slider((amount, contrast), "Slider.Contrast.Slider") == contrast


def test_menu_control_readback_requires_one_exact_committed_value() -> None:
    menu = AccessibilityNode(
        **{
            **_node(1, role="AXPopUpButton", identifier="NSButton.ChoseLUT").__dict__,
            "value": "Anaheim",
        }
    )

    assert select_unique_control((menu,), "NSButton.ChoseLUT") == menu
    assert control_readback_matches(menu, "Anaheim")
    assert not control_readback_matches(menu, "Los Angeles")


def test_slider_readback_compares_native_numeric_value() -> None:
    slider = _node(
        1,
        role="AXSlider",
        identifier="Slider.Amount.Slider",
        value=100.0,
    )

    assert control_readback_matches(slider, 100)
    assert not control_readback_matches(slider, 50)


def test_recipe_percentage_is_mapped_to_native_slider_range() -> None:
    slider = _node(
        1,
        role="AXSlider",
        identifier="amount",
        minimum=-1.0,
        maximum=1.0,
    )

    assert normalize_recipe_value(slider, 50.0) == 0.0


def test_signed_product_amount_is_mapped_to_signed_native_slider() -> None:
    slider = _node(
        1,
        role="AXSlider",
        identifier="amount",
        minimum=-100.0,
        maximum=100.0,
    )

    assert normalize_recipe_value(slider, -1.0, value_space="normalized-signed") == -100.0
    assert normalize_recipe_value(slider, 0.4, value_space="normalized-signed") == 40.0


def test_negative_product_amount_rejects_unsigned_native_slider() -> None:
    slider = _node(
        1,
        role="AXSlider",
        identifier="amount",
        minimum=0.0,
        maximum=100.0,
    )

    with pytest.raises(ValueError, match="cannot be represented"):
        normalize_recipe_value(slider, -1.0, value_space="normalized-signed")


def test_ax_slider_wrapper_value_maps_to_its_visible_track() -> None:
    wrapper = AccessibilityNode(
        **{
            **_node(
                1,
                role="AXSlider",
                identifier="Slider.Red",
                minimum=-100,
                maximum=100,
                position=(1104, 574),
            ).__dict__,
            "enabled": None,
            "size": (218, 40),
        }
    )

    assert slider_click_position(wrapper, 100) == (1319, 603)
    assert slider_click_position(wrapper, 0) == (1212, 603)


def test_normalized_preview_stroke_maps_to_canvas_geometry() -> None:
    preview = AccessibilityNode(
        **{
            **_node(1, role="AXImage", identifier="preview").__dict__,
            "position": (100, 200),
            "size": (800, 600),
        }
    )

    assert normalized_preview_stroke(preview, [0.25, 0.1, 0.75, 0.9]) == (
        300,
        260,
        700,
        740,
    )


def test_normalized_preview_stroke_rejects_out_of_bounds_recipe() -> None:
    preview = _node(1, role="AXImage", identifier="preview")

    with pytest.raises(ValueError, match="normalized"):
        normalized_preview_stroke(preview, [-0.1, 0.1, 0.5, 0.5])


def test_rendered_source_match_uses_rgb_and_luma_thresholds(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    matching = tmp_path / "matching.png"
    different = tmp_path / "different.png"
    Image.new("RGB", (32, 48), (20, 40, 60)).save(source)
    Image.new("RGB", (16, 24), (20, 40, 60)).save(matching)
    Image.new("RGB", (16, 24), (220, 210, 200)).save(different)

    matched, metrics = rendered_source_matches(
        source,
        matching,
        size=16,
        rgb_mae_max=0.01,
        luma_mae_max=0.01,
    )
    rejected, _ = rendered_source_matches(
        source,
        different,
        size=16,
        rgb_mae_max=0.01,
        luma_mae_max=0.01,
    )

    assert matched is True
    assert metrics == {"rgb_mae": 0.0, "luma_mae": 0.0}
    assert rejected is False


def test_accessibility_node_locator_matches_identifier_title_or_value() -> None:
    from scripts.luminar_capture.accessibility_driver import LuminarAccessibilityDriver

    identifier = _node(1, role="AXButton", identifier="tool")
    title = AccessibilityNode(**{**identifier.__dict__, "identifier": None, "title": "编辑"})

    driver = object.__new__(LuminarAccessibilityDriver)

    assert driver.has_locator("tool", (identifier, title))
    assert driver.has_locator("编辑", (identifier, title))
    assert not driver.has_locator("天空", (identifier, title))


def test_asset_picker_selects_requested_asset_by_semantic_metadata() -> None:
    first = _node(1, role="AXButton", identifier="Blue Sky 1.jpg")
    requested = _node(2, role="AXButton", identifier="Blue Sky 2.jpg")

    selected = select_asset_thumbnail(
        (first, requested), asset_id="Blue Sky/Blue Sky 2.jpg"
    )

    assert selected.index == 2


def test_asset_picker_does_not_silently_substitute_first_asset() -> None:
    first = _node(1, role="AXButton", identifier="Blue Sky 1.jpg")

    try:
        select_asset_thumbnail((first,), asset_id="Blue Sky/Blue Sky 2.jpg")
    except RuntimeError as exc:
        assert "not exposed" in str(exc)
    else:
        raise AssertionError("missing requested asset must fail closed")


def test_selects_localized_export_replacement_button() -> None:
    button = AccessibilityNode(
        **{
            **_node(1, role="AXButton", identifier=None).__dict__,
            "title": "替换",
        }
    )

    assert select_replacement_locator((button,)) == "替换"


def test_detects_overwritten_export_signature(tmp_path) -> None:
    export = tmp_path / "case.jpeg"
    export.write_bytes(b"before")
    before = {export.resolve(): (len(b"before"), export.stat().st_mtime_ns)}
    export.write_bytes(b"after-change")

    assert export_signature_changed(tmp_path, stem="case", before=before)


def test_neutral_exact_amount_does_not_require_a_render_change() -> None:
    recipe = SamplingRecipe(
        capability_id="face_ai",
        workspace="edit",
        locator_id="face",
        strategy="subject_aware",
        default_capture=False,
        effective={
            "parameter_binding": {
                "parameter": "amount",
                "value": 0.0,
                "value_space": "normalized-signed",
            }
        },
    )

    assert render_change_required("effect", recipe) is False


def test_nonzero_exact_amount_still_requires_a_render_change() -> None:
    recipe = SamplingRecipe(
        capability_id="face_ai",
        workspace="edit",
        locator_id="face",
        strategy="subject_aware",
        default_capture=False,
        effective={
            "parameter_binding": {
                "parameter": "amount",
                "value": 1.0,
                "value_space": "normalized-signed",
            }
        },
    )

    assert render_change_required("effect", recipe) is True


def test_probe_opens_capture_input_before_requiring_a_window(monkeypatch) -> None:
    events: list[str] = []

    class Controller:
        def launch(self, *, timeout_seconds: float) -> None:
            events.append("launch")

        def enter_full_screen(self, *, timeout_seconds: float) -> None:
            events.append("full-screen")

    class Driver:
        def activate(self) -> None:
            events.append("driver-activate")

    sampler = object.__new__(LuminarAutoSampler)
    sampler.controller = Controller()
    sampler.driver = Driver()
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(action_seconds=1.0, navigation_seconds=1.0)
    )
    monkeypatch.setattr(
        sampler,
        "_prepare_case",
        lambda case, layout, journal, attempt: events.append("prepare-case"),
    )
    monkeypatch.setattr(
        sampler,
        "_reset_transient_ui",
        lambda: events.append("reset-transient-ui"),
    )

    def stop_after_window_restore() -> None:
        events.append("wait-window")
        raise RuntimeError("stop")

    monkeypatch.setattr(sampler, "_wait_for_accessibility_window", stop_after_window_restore)

    with pytest.raises(RuntimeError, match="stop"):
        sampler._probe_once(
            SimpleNamespace(),
            SimpleNamespace(),
            SimpleNamespace(),
            SimpleNamespace(),
            1,
        )

    assert events == [
        "launch",
        "reset-transient-ui",
        "prepare-case",
        "driver-activate",
        "full-screen",
        "wait-window",
    ]


def test_prepare_case_tolerates_transient_accessibility_timeout(tmp_path) -> None:
    source = tmp_path / "fixture.jpg"
    source.write_bytes(b"fixture")
    expected_sha = hashlib.sha256(b"fixture").hexdigest()
    snapshots = iter(
        [
            TimeoutError("temporary AX stall"),
            (_node(1, role="AXStaticText", identifier=None, value=source.name),),
        ]
    )
    transitions: list[tuple[object, dict[str, object]]] = []

    class Controller:
        def request_open_image(self, path: Path) -> None:
            assert path == source.resolve()

    class Driver:
        def snapshot(self):
            result = next(snapshots)
            if isinstance(result, BaseException):
                raise result
            return result

    class Journal:
        def transition(self, status, **payload) -> None:
            transitions.append((status, payload))

    sampler = object.__new__(LuminarAutoSampler)
    sampler.controller = Controller()
    sampler.driver = Driver()
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(navigation_seconds=1.0, stable_seconds=0.0)
    )

    sampler._prepare_case(
        SimpleNamespace(
            case_id="case",
            input_path=source,
            input_sha256=expected_sha,
        ),
        SimpleNamespace(),
        Journal(),
        0,
    )

    assert len(transitions) == 1


def test_prepare_case_does_not_reopen_the_already_selected_input(tmp_path) -> None:
    source = tmp_path / "fixture.jpg"
    source.write_bytes(b"fixture")
    expected_sha = hashlib.sha256(b"fixture").hexdigest()
    transitions: list[tuple[object, dict[str, object]]] = []

    class Controller:
        @staticmethod
        def request_open_image(path: Path) -> None:
            pytest.fail(f"already selected input was reopened: {path}")

    class Driver:
        @staticmethod
        def snapshot():
            return (_node(1, role="AXStaticText", identifier=None, value=source.name),)

    class Journal:
        @staticmethod
        def transition(status, **payload) -> None:
            transitions.append((status, payload))

    sampler = object.__new__(LuminarAutoSampler)
    sampler.controller = Controller()
    sampler.driver = Driver()
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(navigation_seconds=1.0, stable_seconds=0.0)
    )

    sampler._prepare_case(
        SimpleNamespace(
            case_id="case",
            input_path=source,
            input_sha256=expected_sha,
        ),
        SimpleNamespace(),
        Journal(),
        0,
    )

    assert transitions[0][1]["input_verification"] == "filename"


def test_export_directory_reuses_existing_save_sheet_snapshot(tmp_path) -> None:
    native_root = tmp_path / "native-exports"
    location = _node(
        1,
        role="AXPopUpButton",
        identifier="where popup",
        value=native_root.name,
    )

    class Driver:
        def snapshot(self):
            raise AssertionError("export directory must not rescan the Save sheet")

    sampler = object.__new__(LuminarAutoSampler)
    sampler.driver = Driver()
    sampler.config = SimpleNamespace(native_export_root=native_root)

    sampler._ensure_export_directory((location,))


def test_wait_for_locator_tolerates_transient_accessibility_timeout() -> None:
    expected = _node(1, role="AXTextField", identifier="saveAsNameTextField")
    snapshots = iter([TimeoutError("temporary AX stall"), (expected,)])

    class Driver:
        def snapshot(self):
            result = next(snapshots)
            if isinstance(result, BaseException):
                raise result
            return result

        @staticmethod
        def has_locator(locator, nodes) -> bool:
            return any(node.identifier == locator for node in nodes)

    sampler = object.__new__(LuminarAutoSampler)
    sampler.driver = Driver()
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(navigation_seconds=1.0)
    )

    assert sampler._wait_for_locator("saveAsNameTextField") == (expected,)


def test_wait_for_first_value_retries_until_save_sheet_is_available() -> None:
    attempts = iter([RuntimeError("not ready"), "native-exports"])

    class Driver:
        @staticmethod
        def read_value_first(locator):
            result = next(attempts)
            if isinstance(result, BaseException):
                raise result
            return result

    sampler = object.__new__(LuminarAutoSampler)
    sampler.driver = Driver()
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(navigation_seconds=1.0)
    )

    assert sampler._wait_for_first_value("where popup") == "native-exports"


def test_export_dimensions_are_restored_to_oriented_source(tmp_path: Path) -> None:
    source = tmp_path / "portrait.jpg"
    Image.new("RGB", (1080, 1845)).save(source)
    values = {"_NS:262": "1080", "_NS:254": "1440"}
    writes: list[tuple[str, str]] = []

    sampler = object.__new__(LuminarAutoSampler)

    def read_or_write(locator: str, *, value: str | None = None):
        if value is not None:
            values[locator] = value
            writes.append((locator, value))
        return values[locator]

    sampler._wait_for_first_value = read_or_write
    case = SimpleNamespace(input_path=source)

    assert sampler._ensure_original_export_dimensions(case) == {
        "before": [1080, 1440],
        "target": [1080, 1845],
        "after": [1080, 1845],
    }
    assert writes == [("_NS:262", "1080"), ("_NS:254", "1845")]


def test_effect_export_requires_an_enabled_restore_original_action() -> None:
    events: list[str] = []

    class Driver:
        @staticmethod
        def reset_all_edits(*, perform: bool) -> dict[str, bool]:
            events.append(f"atomic-reset-status:{perform}")
            return {"enabled": True, "performed": False}

    sampler = object.__new__(LuminarAutoSampler)
    sampler.driver = Driver()
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(action_seconds=1.0, navigation_seconds=2.0)
    )
    assert sampler._verify_photo_has_edits() == {
        "required": True,
        "verified": True,
        "locator_id": "ResetAllEdits",
        "enabled": True,
    }
    assert events == ["atomic-reset-status:False"]


def test_effect_export_rejects_a_disabled_restore_original_action() -> None:
    sampler = object.__new__(LuminarAutoSampler)
    sampler.driver = SimpleNamespace(
        reset_all_edits=lambda *, perform: {"enabled": False, "performed": False}
    )
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(action_seconds=0.01)
    )
    with pytest.raises(NonRetryableCaptureError, match="restore-original"):
        sampler._verify_photo_has_edits()


def test_inline_asset_collection_is_limited_by_neighboring_headings() -> None:
    heading = _node(
        1, role="AXStaticText", identifier="_NS:13", value="耀斑", position=(19, 644)
    )
    before = _node(2, role="AXImage", identifier="_NS:58", position=(19, 568))
    first = AccessibilityNode(
        **{
            **_node(3, role="AXImage", identifier="_NS:58", position=(19, 670)).__dict__,
            "size": (51, 51),
        }
    )
    second = AccessibilityNode(
        **{
            **_node(4, role="AXImage", identifier="_NS:58", position=(77, 734)).__dict__,
            "size": (51, 51),
        }
    )
    next_heading = _node(
        5, role="AXStaticText", identifier="_NS:13", value="下一组", position=(19, 810)
    )
    after = _node(6, role="AXImage", identifier="_NS:58", position=(19, 830))

    selected = embedded_category_thumbnails(
        (before, heading, first, second, next_heading, after),
        category="耀斑",
        bounds=WindowBounds(x=0, y=0, width=1440, height=900),
    )

    assert selected == (first, second)


def test_high_compression_thumbnail_requires_clear_runner_up_margin() -> None:
    assert thumbnail_match_is_confident(
        best_score=27.94,
        second_score=52.55,
        normal_maximum=16,
        hard_maximum=32,
        minimum_margin=8,
    )
    assert not thumbnail_match_is_confident(
        best_score=27.94,
        second_score=31.0,
        normal_maximum=16,
        hard_maximum=32,
        minimum_margin=8,
    )


def test_asset_picker_scroll_value_places_target_row_at_visible_start() -> None:
    assert asset_picker_scroll_value(
        asset_index=11, asset_count=35, columns=3, visible_rows=4
    ) == 0
    assert asset_picker_scroll_value(
        asset_index=12, asset_count=35, columns=3, visible_rows=4
    ) == 0.375
    assert asset_picker_scroll_value(
        asset_index=34, asset_count=35, columns=3, visible_rows=4
    ) == 1


def test_failed_probe_keeps_discovered_controls_and_applied_value() -> None:
    class Journal:
        @staticmethod
        def events():
            return [
                    {
                        "status": "default-captured",
                        "controls": [{"identifier": "Slider.Amount.Slider"}],
                    },
                    {
                        "status": "effect-applied",
                        "control": "Slider.Amount.Slider",
                        "value": 50,
                    },
                {"status": "after-captured", "stable_samples": 3},
            ]

    result = LuminarAutoSampler._failed_probe_result(
        case=SimpleNamespace(case_id="case", capability_id="details"),
        recipe=SimpleNamespace(locator_id="tool"),
        journal=Journal(),
        error=RuntimeError("unchanged source"),
    )

    assert result.capture_level == "effect"
    assert result.discovered_controls == ({"identifier": "Slider.Amount.Slider"},)
    assert result.effective_control == "Slider.Amount.Slider"
    assert result.effective_value == 50
    assert result.stable_samples == 3


def test_non_retryable_probe_failure_runs_only_once(tmp_path: Path) -> None:
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(retries=2)
    attempts: list[int] = []

    def fail_once(case, layout, recipe, journal, attempt):
        attempts.append(attempt)
        raise NonRetryableCaptureError("unchanged source")

    sampler._probe_once = fail_once
    sampler._write_result = lambda layout, result: None
    result = sampler.probe(
        SimpleNamespace(case_id="case", capability_id="denoise"),
        CaptureLayout(tmp_path, "case"),
        SimpleNamespace(locator_id="tool", effective={}),
    )

    assert attempts == [0]
    assert result.status == "failed"


def test_post_export_failure_does_not_repeat_export(tmp_path: Path) -> None:
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(retries=2)
    attempts: list[int] = []

    def export_then_fail(case, layout, recipe, journal, attempt):
        attempts.append(attempt)
        journal.transition(CaptureStatus.EXPORTED, export_path="result.jpeg")
        raise RuntimeError("late preview evidence")

    sampler._probe_once = export_then_fail
    sampler._write_result = lambda layout, result: None
    result = sampler.probe(
        SimpleNamespace(case_id="case", capability_id="slim_people"),
        CaptureLayout(tmp_path, "case"),
        SimpleNamespace(locator_id="tool", effective={}),
    )

    assert attempts == [0]
    assert result.status == "failed"
    assert "will not repeat the export" in result.error


def test_transient_probe_failure_retries_the_same_activation(tmp_path: Path) -> None:
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(retries=1)
    activation_indexes: list[int] = []

    def transient_then_ready(case, layout, recipe, journal, activation_index):
        activation_indexes.append(activation_index)
        if len(activation_indexes) == 1:
            raise RuntimeError("temporary window bounds")
        return SimpleNamespace(status="ready")

    sampler._probe_once = transient_then_ready
    sampler._write_result = lambda layout, result: None
    result = sampler.probe(
        SimpleNamespace(case_id="case", capability_id="denoise"),
        CaptureLayout(tmp_path, "case"),
        SimpleNamespace(
            locator_id="tool",
            effective={"activation_locator_ids": ["low", "mid", "high"]},
        ),
    )

    assert activation_indexes == [0, 0]
    assert result.status == "ready"


def test_ineffective_activation_advances_to_the_next_level(tmp_path: Path) -> None:
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(retries=0)
    activation_indexes: list[int] = []

    def advance_then_ready(case, layout, recipe, journal, activation_index):
        activation_indexes.append(activation_index)
        if activation_index == 0:
            raise AdvanceActivationCaptureError("no measurable change")
        return SimpleNamespace(status="ready")

    sampler._probe_once = advance_then_ready
    sampler._write_result = lambda layout, result: None
    result = sampler.probe(
        SimpleNamespace(case_id="case", capability_id="denoise"),
        CaptureLayout(tmp_path, "case"),
        SimpleNamespace(
            locator_id="tool",
            effective={"activation_locator_ids": ["low", "mid", "high"]},
        ),
    )

    assert activation_indexes == [0, 1]
    assert result.status == "ready"


def test_reset_photo_edits_accepts_disabled_restore_as_empty_edit_stack() -> None:
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(action_seconds=1.0, navigation_seconds=2.0)
    )
    sampler._clear_photo_edits = lambda **kwargs: 0

    evidence = sampler.reset_photo_edits()

    assert evidence["strategy"] == "disabled-reset-action"
    assert evidence["reset_performed"] is False
    assert evidence["reset_action_count"] == 0
    assert evidence["source_verification"] == (
        "selected-input+disabled-reset-action"
    )


def test_clear_photo_edits_repeats_atomic_reset_until_restore_is_disabled() -> None:
    sampler = object.__new__(LuminarAutoSampler)
    states = iter((
        {"enabled": True, "performed": True},
        {"enabled": True, "performed": True},
        {"enabled": False, "performed": False},
    ))
    calls: list[bool] = []
    def reset_all_edits(*, perform: bool) -> dict[str, bool]:
        calls.append(perform)
        return next(states)
    sampler.driver = SimpleNamespace(reset_all_edits=reset_all_edits)
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(action_seconds=1.0)
    )
    action_count = sampler._clear_photo_edits(timeout_seconds=1.0)

    assert calls == [True, True, True]
    assert action_count == 2


def test_verify_photo_has_edits_waits_until_restore_original_is_enabled() -> None:
    sampler = object.__new__(LuminarAutoSampler)
    states = iter(({"enabled": False}, {"enabled": True}))
    calls: list[bool] = []
    def reset_all_edits(*, perform: bool) -> dict[str, bool]:
        calls.append(perform)
        return next(states)
    sampler.driver = SimpleNamespace(reset_all_edits=reset_all_edits)
    sampler.config = SimpleNamespace(
        timeouts=SimpleNamespace(action_seconds=1.0)
    )
    evidence = sampler._verify_photo_has_edits()

    assert calls == [False, False]
    assert evidence == {
        "required": True,
        "verified": True,
        "locator_id": "ResetAllEdits",
        "enabled": True,
    }


def test_unchanged_complete_export_is_non_retryable(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    preview = tmp_path / "preview.png"
    exported = tmp_path / "export.png"
    for path in (source, preview, exported):
        Image.new("RGB", (16, 12), (10, 20, 30)).save(path)
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(
        preview_export_comparison_size=16,
        preview_export_rgb_mae_max=0.01,
        preview_export_luma_mae_max=0.01,
        change_pixel_delta_min=0.02,
        export_source_mae_min=0.01,
        change_pixel_fraction_min=0.01,
    )

    with pytest.raises(NonRetryableCaptureError, match="unchanged source"):
        sampler._validate_rendered_effect(
            SimpleNamespace(input_path=source),
            layout=SimpleNamespace(staging_dir=tmp_path),
            preview_path=preview,
            export_path=exported,
            require_change=True,
        )

    assert not exported.exists()
    assert (tmp_path / "rejected-export-attempt-0.png").is_file()


def test_unchanged_denoise_advances_to_the_next_explicit_level(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    preview = tmp_path / "preview.png"
    exported = tmp_path / "export.png"
    for path in (source, preview, exported):
        Image.new("RGB", (16, 12), (10, 20, 30)).save(path)
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(
        preview_export_comparison_size=16,
        preview_export_rgb_mae_max=0.01,
        preview_export_luma_mae_max=0.01,
        change_pixel_delta_min=0.02,
        export_source_mae_min=0.01,
        change_pixel_fraction_min=0.01,
    )
    recipe = SamplingRecipe(
        capability_id="denoise",
        workspace="edit",
        locator_id="denoise",
        strategy="primary_slider",
        default_capture=False,
        effective={
            "activation_locator_ids": [
                "NSButton.Noiseless.Low",
                "NSButton.Noiseless.Mid",
                "NSButton.Noiseless.High",
            ]
        },
    )

    with pytest.raises(RuntimeError, match="unchanged source") as error:
        sampler._validate_rendered_effect(
            SimpleNamespace(input_path=source),
            layout=SimpleNamespace(staging_dir=tmp_path),
            preview_path=preview,
            export_path=exported,
            require_change=True,
            recipe=recipe,
            attempt=0,
        )

    assert not isinstance(error.value, NonRetryableCaptureError)
    assert (tmp_path / "rejected-export-attempt-0.png").is_file()


def test_low_amplitude_effect_can_use_a_recipe_specific_change_floor(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    preview = tmp_path / "preview.png"
    exported = tmp_path / "export.png"
    Image.new("RGB", (16, 12), (10, 20, 30)).save(source)
    Image.new("RGB", (16, 12), (12, 22, 32)).save(preview)
    Image.new("RGB", (16, 12), (12, 22, 32)).save(exported)
    sampler = object.__new__(LuminarAutoSampler)
    sampler.config = SimpleNamespace(
        preview_export_comparison_size=16,
        preview_export_rgb_mae_max=0.01,
        preview_export_luma_mae_max=0.01,
        change_pixel_delta_min=0.02,
        export_source_mae_min=0.01,
        change_pixel_fraction_min=0.01,
    )
    recipe = SamplingRecipe(
        capability_id="denoise",
        workspace="edit",
        locator_id="denoise",
        strategy="primary_slider",
        default_capture=False,
        effective={"export_source_mae_min": 0.005},
    )

    sampler._validate_rendered_effect(
        SimpleNamespace(input_path=source),
        layout=SimpleNamespace(staging_dir=tmp_path),
        preview_path=preview,
        export_path=exported,
        require_change=True,
        recipe=recipe,
    )

    assert exported.is_file()
