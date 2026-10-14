"""Typed Python boundary for Luminar's macOS Accessibility tree."""

from __future__ import annotations

import json
import math
import subprocess
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .input_guard import LocalInputGuard


@dataclass(frozen=True)
class AccessibilityNode:
    index: int
    role: str | None
    subrole: str | None
    identifier: str | None
    title: str | None
    description: str | None
    help: str | None
    value: Any
    min_value: float | None
    max_value: float | None
    enabled: bool | None
    focused: bool | None
    selected: bool | None
    position: tuple[int, int] | None
    size: tuple[int, int] | None
    orientation: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AccessibilityNode:
        def point(name: str) -> tuple[int, int] | None:
            value = payload.get(name)
            if not isinstance(value, list) or len(value) != 2:
                return None
            return int(value[0]), int(value[1])

        def number(name: str) -> float | None:
            value = payload.get(name)
            return float(value) if isinstance(value, (int, float)) else None

        return cls(
            index=int(payload["index"]),
            role=payload.get("role"),
            subrole=payload.get("subrole"),
            identifier=payload.get("identifier"),
            title=payload.get("title"),
            description=payload.get("description"),
            help=payload.get("help"),
            value=payload.get("value"),
            min_value=number("min_value"),
            max_value=number("max_value"),
            enabled=payload.get("enabled"),
            focused=payload.get("focused"),
            selected=payload.get("selected"),
            position=point("position"),
            size=point("size"),
            orientation=payload.get("orientation"),
        )

    @property
    def stable_key(self) -> tuple[Any, ...]:
        return self.role, self.identifier, self.title, self.position, self.size


class LuminarAccessibilityDriver:
    def __init__(
        self,
        helper_path: Path | None = None,
        *,
        timeout_seconds: float = 30.0,
        low_interference: bool = False,
        required_idle_seconds: float = 5.0,
        idle_poll_seconds: float = 0.5,
    ) -> None:
        self.source_path = Path(__file__).with_name("native_helper.swift").resolve()
        self.helper_path = (
            helper_path
            or Path(__file__).resolve().parents[2] / ".tools" / "luminar-ax-helper"
        ).resolve()
        if not self.source_path.is_file():
            raise FileNotFoundError(
                f"Luminar accessibility helper source is missing: {self.source_path}"
            )
        if timeout_seconds <= 0:
            raise ValueError("Luminar accessibility timeout must be positive")
        self.timeout_seconds = timeout_seconds
        self.low_interference = low_interference
        self.input_guard = LocalInputGuard(
            required_idle_seconds=required_idle_seconds,
            poll_seconds=idle_poll_seconds,
        )
        self._ensure_helper()
        self._input_actions: Counter[str] = Counter()
        self._initial_cursor_position = (
            self.cursor_position() if self.low_interference else None
        )

    def wait_for_user_idle(self, reason: str = "native-ui-control") -> None:
        if not self.low_interference:
            return
        self.input_guard.wait(self.hid_idle_seconds, reason=reason)

    def hid_idle_seconds(self) -> float:
        return float(self._invoke("hid-idle")["seconds"])

    def cursor_position(self) -> tuple[float, float]:
        raw = self._invoke("cursor-position")["position"]
        return float(raw[0]), float(raw[1])

    def interference_report(self) -> dict[str, Any]:
        current_cursor = self.cursor_position() if self.low_interference else None
        cursor_delta = (
            math.dist(self._initial_cursor_position, current_cursor)
            if self._initial_cursor_position is not None and current_cursor is not None
            else None
        )
        global_pointer_actions = sum(
            count
            for mode, count in self._input_actions.items()
            if "global" in mode
        )
        return {
            **self.input_guard.report(),
            "input_actions": dict(sorted(self._input_actions.items())),
            "global_pointer_actions": global_pointer_actions,
            "initial_cursor_position": self._initial_cursor_position,
            "final_cursor_position": current_cursor,
            "cursor_delta_points": cursor_delta,
            "cursor_unchanged_observed": (
                cursor_delta <= 1.0
                if cursor_delta is not None
                else None
            ),
        }

    def state(self) -> dict[str, Any]:
        return self._run("state")

    def activate(self) -> None:
        self._run("activate")

    def open_export_dialog(self) -> None:
        self._run("new-export")

    def open_go_to_folder(self) -> None:
        self._run("go-to-folder")

    def confirm(self) -> None:
        self._run("confirm")

    def cancel(self) -> None:
        self._run("cancel")

    def reset_all_edits(self, *, perform: bool = True) -> dict[str, Any]:
        """Open, inspect and optionally commit Restore Original atomically."""

        return self._run(
            "reset-all-edits" if perform else "reset-all-edits-status"
        )

    def select_menu_item(self, parent_locator: str, item_locator: str) -> dict[str, Any]:
        """Open and select a transient native menu item atomically."""

        return self._run("select-menu-item", parent_locator, item_locator)

    def snapshot(self) -> tuple[AccessibilityNode, ...]:
        payload = self._run("snapshot")
        return tuple(AccessibilityNode.from_payload(item) for item in payload["nodes"])

    def inspect(self, locator: str) -> dict[str, Any]:
        return self._run("inspect", locator)

    def read_attribute(self, locator: str, attribute: str) -> Any:
        return self._run("read-attribute", locator, attribute)["value"]

    def perform_action(self, locator: str, action: str) -> None:
        self._run("perform-action", locator, action)

    def set_selected(self, locator: str, selected: bool) -> None:
        self._run("set-selected", locator, str(selected).lower())

    def open_export_menu(self) -> tuple[AccessibilityNode, ...]:
        payload = self._run("open-export-menu")
        return tuple(AccessibilityNode.from_payload(item) for item in payload["nodes"])

    def press(self, locator: str) -> None:
        self._run("press", locator)

    def ax_press(self, locator: str) -> None:
        self._run("ax-press", locator)

    def press_at(self, index: int) -> None:
        self._run("press-at", str(index))

    def ax_press_at(self, index: int) -> None:
        self._run("ax-press-at", str(index))

    def has_locator(self, locator: str, nodes: tuple[AccessibilityNode, ...] | None = None) -> bool:
        candidates = nodes if nodes is not None else self.snapshot()
        return any(
            node.identifier == locator
            or node.title == locator
            or node.description == locator
            or node.help == locator
            or node.value == locator
            for node in candidates
        )

    def set_value(self, locator: str, value: str | float | bool) -> Any:
        return self._run("set-value", locator, str(value))["value"]

    def read_value_first(self, locator: str) -> Any:
        return self._run("read-value-first", locator)["value"]

    def set_value_first(self, locator: str, value: str | float | bool) -> Any:
        return self._run("set-value-first", locator, str(value))["value"]

    def press_first(self, locator: str) -> None:
        self._run("press-first", locator)

    def set_value_at(self, index: int, value: str | float | bool) -> Any:
        return self._run("set-value-at", str(index), str(value))["value"]

    def scroll_at(self, x: int, y: int, lines: int) -> None:
        action = "target-scroll-at" if self.low_interference else "scroll-at"
        self._run(action, str(x), str(y), str(lines))

    def click_at(self, x: int, y: int) -> None:
        action = "target-click-at" if self.low_interference else "click-at"
        self._run(action, str(x), str(y))

    def target_click_at(self, x: int, y: int) -> None:
        self._run("target-click-at", str(x), str(y))

    def right_click_at(self, x: int, y: int) -> None:
        self._run("right-click-at", str(x), str(y))

    def mouse_down_at(self, x: int, y: int) -> None:
        self._run("mouse-down-at", str(x), str(y))

    def mouse_up_at(self, x: int, y: int) -> None:
        self._run("mouse-up-at", str(x), str(y))

    def mouse_move_at(self, x: int, y: int) -> None:
        self._run("mouse-move-at", str(x), str(y))

    def key_down(self, key_code: int, *modifiers: str) -> None:
        self._run("key-down", str(key_code), ",".join(modifiers))

    def key_up(self, key_code: int, *modifiers: str) -> None:
        self._run("key-up", str(key_code), ",".join(modifiers))

    def shortcut(self, key_code: int, *modifiers: str) -> None:
        self._run("shortcut", str(key_code), ",".join(modifiers))

    def target_shortcut(self, key_code: int, *modifiers: str) -> None:
        self._run("target-shortcut", str(key_code), ",".join(modifiers))

    def drag_at(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        action = "target-drag-at" if self.low_interference else "drag-at"
        self._run(
            action,
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
        )

    def guarded_canvas_click_at(self, x: int, y: int) -> None:
        """Use a real canvas click while idle, restoring the system cursor."""

        self._run("restored-click-at", str(x), str(y))

    def guarded_canvas_drag_at(
        self, start_x: int, start_y: int, end_x: int, end_y: int
    ) -> None:
        """Use a real canvas drag while idle, restoring the system cursor."""

        self._run(
            "restored-drag-at",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
        )

    def command_click_at(self, x: int, y: int) -> None:
        action = (
            "target-command-click-at"
            if self.low_interference
            else "command-click-at"
        )
        self._run(action, str(x), str(y))

    def write_snapshot(self, path: Path, nodes: tuple[AccessibilityNode, ...]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "format": "macos-accessibility-v1",
                    "nodes": [asdict(node) for node in nodes],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _run(self, action: str, *arguments: str) -> dict[str, Any]:
        protected_global_press = (
            action == "press"
            and bool(arguments)
            and arguments[0]
            in {
                "MPCatalogFilterNodeViewNodeLabel",
                "MPInstrumentInfoViewControllerFileName",
            }
        )
        idle_guarded_actions = {
            "activate",
            "new-export",
            "go-to-folder",
            "confirm",
            "cancel",
            "open-export-menu",
            "select-menu-item",
            "scroll-at",
            "click-at",
            "command-click-at",
            "drag-at",
            "restored-click-at",
            "restored-drag-at",
            "right-click-at",
            "mouse-down-at",
            "mouse-move-at",
            "mouse-up-at",
            "key-down",
            "key-up",
            "shortcut",
            "press-at",
        }
        if self.low_interference and (
            action in idle_guarded_actions or protected_global_press
        ):
            self.wait_for_user_idle(action)
        payload = self._invoke(action, *arguments)
        if self.low_interference:
            mode = payload.get("input_mode")
            if isinstance(mode, str):
                self._input_actions[mode] += 1
            elif action.startswith("target-"):
                self._input_actions["targeted-process"] += 1
            elif action in {
                "click-at",
                "scroll-at",
                "drag-at",
                "command-click-at",
                "right-click-at",
                "mouse-down-at",
                "mouse-up-at",
                "mouse-move-at",
            }:
                self._input_actions["global-pointer"] += 1
            elif action in {"ax-press", "perform-action", "set-value", "set-selected"}:
                self._input_actions["accessibility"] += 1
        if self.low_interference and action not in {
            "state",
            "snapshot",
            "inspect",
            "read-attribute",
            "read-value-first",
            "hid-idle",
            "cursor-position",
        }:
            self.input_guard.note_automation_input()
        return payload

    def _invoke(self, action: str, *arguments: str) -> dict[str, Any]:
        command = [str(self.helper_path), action, *arguments]
        result: subprocess.CompletedProcess[str] | None = None
        for attempt in range(3):
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError(
                    f"Luminar accessibility {action} exceeded "
                    f"{self.timeout_seconds:.1f}s"
                ) from exc
            detail = result.stderr.strip() or result.stdout.strip()
            if result.returncode == 0 or "no accessibility window" not in detail:
                break
            if attempt < 2:
                time.sleep(0.2)
        assert result is not None
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise RuntimeError(f"Luminar accessibility {action} failed: {detail}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Luminar accessibility {action} returned invalid JSON: {result.stdout!r}"
            ) from exc
        if not payload.get("ok"):
            raise RuntimeError(f"Luminar accessibility {action} failed: {payload}")
        return payload

    def _ensure_helper(self) -> None:
        if (
            self.helper_path.is_file()
            and self.helper_path.stat().st_mtime_ns >= self.source_path.stat().st_mtime_ns
        ):
            return
        self.helper_path.parent.mkdir(parents=True, exist_ok=True)
        module_cache = self.helper_path.parent / "swift-module-cache"
        module_cache.mkdir(parents=True, exist_ok=True)
        command = [
            "swiftc",
            str(self.source_path),
            "-module-cache-path",
            str(module_cache),
            "-o",
            str(self.helper_path),
            "-framework",
            "AppKit",
            "-framework",
            "ApplicationServices",
            "-framework",
            "IOKit",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise RuntimeError(f"failed to build Luminar accessibility helper: {detail}")
