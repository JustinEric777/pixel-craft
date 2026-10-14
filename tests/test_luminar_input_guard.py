from scripts.luminar_capture.accessibility_driver import LuminarAccessibilityDriver
from scripts.luminar_capture.input_guard import LocalInputGuard


def test_input_guard_waits_for_initial_physical_idle(monkeypatch) -> None:
    samples = iter((0.1, 0.4, 5.0))
    sleeps: list[float] = []
    guard = LocalInputGuard(required_idle_seconds=5.0, poll_seconds=0.25)
    monkeypatch.setattr("scripts.luminar_capture.input_guard.time.sleep", sleeps.append)

    guard.wait(lambda: next(samples), reason="activate")

    assert sleeps == [0.25, 0.25]
    assert guard.report()["wait_count"] == 1


def test_input_guard_does_not_treat_its_own_recent_event_as_user_input(
    monkeypatch,
) -> None:
    guard = LocalInputGuard(required_idle_seconds=5.0, poll_seconds=0.25)
    guard.note_automation_input()
    monkeypatch.setattr(
        "scripts.luminar_capture.input_guard.time.sleep",
        lambda _: (_ for _ in ()).throw(AssertionError("unexpected wait")),
    )

    guard.wait(lambda: 0.01, reason="press")

    assert guard.report()["wait_count"] == 0


def test_low_interference_routes_pointer_actions_to_luminar_process() -> None:
    driver = object.__new__(LuminarAccessibilityDriver)
    driver.low_interference = True
    actions: list[tuple[str, ...]] = []
    driver._run = lambda *args: actions.append(args)  # type: ignore[method-assign]

    driver.click_at(1, 2)
    driver.scroll_at(3, 4, 5)
    driver.drag_at(6, 7, 8, 9)
    driver.command_click_at(10, 11)
    driver.guarded_canvas_click_at(12, 13)
    driver.guarded_canvas_drag_at(14, 15, 16, 17)

    assert actions == [
        ("target-click-at", "1", "2"),
        ("target-scroll-at", "3", "4", "5"),
        ("target-drag-at", "6", "7", "8", "9"),
        ("target-command-click-at", "10", "11"),
        ("restored-click-at", "12", "13"),
        ("restored-drag-at", "14", "15", "16", "17"),
    ]
