"""Small macOS boundary used by the guided Luminar capture runner."""

from __future__ import annotations

import plistlib
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WindowBounds:
    x: int
    y: int
    width: int
    height: int


class LuminarAppController:
    def __init__(
        self,
        app_path: Path,
        *,
        before_ui_control: Callable[[str], None] | None = None,
    ) -> None:
        self.app_path = app_path.resolve()
        self.before_ui_control = before_ui_control
        if not self.app_path.is_dir():
            raise FileNotFoundError(f"Luminar app does not exist: {self.app_path}")
        with (self.app_path / "Contents/Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        self.bundle_id = str(info.get("CFBundleIdentifier", ""))
        self.process_name = str(info.get("CFBundleExecutable", ""))
        if not self.bundle_id or not self.process_name:
            raise RuntimeError("Luminar bundle identity is incomplete")

    def set_ui_control_guard(self, guard: Callable[[str], None] | None) -> None:
        self.before_ui_control = guard

    def _guard(self, reason: str) -> None:
        if self.before_ui_control is not None:
            self.before_ui_control(reason)

    def version(self) -> dict[str, str]:
        with (self.app_path / "Contents/Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        return {
            "version": str(info.get("CFBundleShortVersionString", "unknown")),
            "build": str(info.get("CFBundleVersion", "unknown")),
            "bundle_id": str(info.get("CFBundleIdentifier", "unknown")),
        }

    def launch(self, *, timeout_seconds: float = 30.0) -> None:
        self._guard("launch")
        self._run(["open", "-a", str(self.app_path)])
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    (
                        'tell application "System Events" to exists process '
                        f'"{self.process_name}"'
                    ),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip() == "true":
                return
            time.sleep(0.25)
        raise TimeoutError("Luminar did not expose an application process after launch")

    def activate(self) -> None:
        self._guard("activate")
        script = f'tell application id "{self.bundle_id}" to activate'
        self._run(["osascript", "-e", script])

    def open_add_images_folder_dialog(self) -> None:
        self._guard("open-add-images-folder-dialog")
        script = f"""
tell application "System Events"
  tell process "{self.process_name}"
    set frontmost to true
    click menu item "添加带图像的文件夹..." of menu 1 of menu bar item "文件" of menu bar 1
  end tell
end tell
"""
        self._run(["osascript", "-e", script])

    def open_image(self, path: Path, *, timeout_seconds: float = 30.0) -> None:
        source = self.request_open_image(path)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._window_title() == source.name:
                return
            time.sleep(0.25)
        raise TimeoutError(
            f"Luminar did not select capture input {source.name!r}; "
            f"current document is {self._window_title()!r}"
        )

    def request_open_image(self, path: Path) -> Path:
        """Ask Luminar to open an image without assuming a standard AppKit window."""
        source = path.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Luminar capture input does not exist: {source}")
        self._guard("open-image")
        self._run(["open", "-a", str(self.app_path), str(source)])
        return source

    def ensure_window(self, *, timeout_seconds: float = 10.0) -> None:
        """Restore the most recent Luminar window when the process has none."""
        if self._window_count() > 0:
            return

        grace_deadline = time.monotonic() + min(timeout_seconds, 1.5)
        while time.monotonic() < grace_deadline:
            if self._window_count() > 0:
                return
            time.sleep(0.1)

        reopen = f'tell application id "{self.bundle_id}" to reopen'
        self._guard("restore-window")
        self._run(["osascript", "-e", reopen])
        script = f"""
tell application "System Events"
  tell process "{self.process_name}"
    set frontmost to true
    if (count of windows) is 0 then
      try
        click menu item "目录" of menu 1 of menu bar item "文件" of menu bar 1
      end try
    end if
    if (count of windows) is 0 then
      try
        set recentItem to last menu item of menu 1 of menu bar item "窗口" of menu bar 1
        if enabled of recentItem then click recentItem
      end try
    end if
  end tell
end tell
"""
        self._run(["osascript", "-e", script])
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._window_count() > 0:
                return
            time.sleep(0.25)
        raise RuntimeError(
            "Luminar is running without a restorable window; open its catalog window first"
        )

    def _window_count(self) -> int:
        result = self._run(
            [
                "osascript",
                "-e",
                (
                    'tell application "System Events" to tell process '
                    f'"{self.process_name}" '
                    "to get count of windows"
                ),
            ]
        )
        return int(result.stdout.strip())

    def _window_title(self) -> str:
        if self._window_count() == 0:
            return ""
        result = self._run(
            [
                "osascript",
                "-e",
                (
                    'tell application "System Events" to tell process '
                    f'"{self.process_name}" '
                    "to get title of window 1"
                ),
            ]
        )
        return result.stdout.strip()

    def window_bounds(self) -> WindowBounds:
        self.ensure_window()
        script = f"""
tell application "System Events"
  tell process "{self.process_name}"
    set bestArea to 0
    set bestPosition to {{0, 0}}
    set bestSize to {{0, 0}}
    repeat with candidateWindow in windows
      set candidatePosition to position of candidateWindow
      set candidateSize to size of candidateWindow
      set candidateArea to (item 1 of candidateSize) * (item 2 of candidateSize)
      if candidateArea > bestArea then
        set bestArea to candidateArea
        set bestPosition to candidatePosition
        set bestSize to candidateSize
      end if
    end repeat
    return (item 1 of bestPosition as text) & "," & (item 2 of bestPosition as text) & "," & (item 1 of bestSize as text) & "," & (item 2 of bestSize as text)
  end tell
end tell
"""
        result = self._run(["osascript", "-e", script])
        values = [int(value) for value in result.stdout.strip().split(",")]
        if len(values) != 4:
            raise RuntimeError(f"unexpected Luminar window bounds: {result.stdout!r}")
        return WindowBounds(*values)

    def resize_window(self, width: int, height: int) -> WindowBounds:
        """Resize the largest Luminar window for a fixed-viewport UI capture."""
        if width <= 0 or height <= 0:
            raise ValueError("Luminar window dimensions must be positive")
        self._guard("resize-window")
        self.ensure_window()
        exit_full_screen = f"""
tell application "System Events"
  tell process "{self.process_name}"
    repeat with candidateWindow in windows
      try
        if value of attribute "AXFullScreen" of candidateWindow then
          set value of attribute "AXFullScreen" of candidateWindow to false
          exit repeat
        end if
      end try
    end repeat
  end tell
end tell
"""
        self._run(["osascript", "-e", exit_full_screen])
        time.sleep(0.8)
        script = f"""
tell application "System Events"
  tell process "{self.process_name}"
    set frontmost to true
    set bestArea to 0
    set bestWindow to missing value
    repeat with candidateWindow in windows
      set candidateSize to size of candidateWindow
      set candidateArea to (item 1 of candidateSize) * (item 2 of candidateSize)
      if candidateArea > bestArea then
        set bestArea to candidateArea
        set bestWindow to candidateWindow
      end if
    end repeat
    if bestWindow is missing value then error "Luminar has no resizable window"
    try
      set value of attribute "AXZoomed" of bestWindow to false
    end try
    set position of bestWindow to {{0, 0}}
    set size of bestWindow to {{{width}, {height}}}
  end tell
end tell
"""
        self._run(["osascript", "-e", script])
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            bounds = self.window_bounds()
            if bounds.width == width and bounds.height == height:
                return bounds
            time.sleep(0.1)
        bounds = self.window_bounds()
        raise RuntimeError(
            "Luminar window did not reach requested viewport: "
            f"{bounds.width}x{bounds.height} != {width}x{height}"
        )

    def enter_full_screen(self, *, timeout_seconds: float = 12.0) -> WindowBounds:
        """Put the largest Luminar window in native macOS full-screen mode."""

        self._guard("enter-full-screen")
        self.ensure_window()
        script = f"""
tell application "System Events"
  tell process "{self.process_name}"
    set frontmost to true
    set bestArea to 0
    set bestWindow to missing value
    repeat with candidateWindow in windows
      set candidateSize to size of candidateWindow
      set candidateArea to (item 1 of candidateSize) * (item 2 of candidateSize)
      if candidateArea > bestArea then
        set bestArea to candidateArea
        set bestWindow to candidateWindow
      end if
    end repeat
    if bestWindow is missing value then error "Luminar has no full-screen window"
    if not (value of attribute "AXFullScreen" of bestWindow) then
      set value of attribute "AXFullScreen" of bestWindow to true
    end if
  end tell
end tell
"""
        self._run(["osascript", "-e", script])
        deadline = time.monotonic() + timeout_seconds
        stable_bounds: WindowBounds | None = None
        stable_since: float | None = None
        while time.monotonic() < deadline:
            result = self._run(
                [
                    "osascript",
                    "-e",
                    f"""
tell application "System Events"
  tell process "{self.process_name}"
    set bestArea to 0
    set bestWindow to missing value
    repeat with candidateWindow in windows
      set candidateSize to size of candidateWindow
      set candidateArea to (item 1 of candidateSize) * (item 2 of candidateSize)
      if candidateArea > bestArea then
        set bestArea to candidateArea
        set bestWindow to candidateWindow
      end if
    end repeat
    if bestWindow is missing value then return false
    return value of attribute "AXFullScreen" of bestWindow
  end tell
end tell
""",
                ]
            )
            if result.stdout.strip() != "true":
                time.sleep(0.2)
                continue
            bounds = self.window_bounds()
            if bounds == stable_bounds:
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since >= 0.8:
                    return bounds
            else:
                stable_bounds = bounds
                stable_since = None
            time.sleep(0.2)
        raise TimeoutError("Luminar did not reach stable native full-screen mode")

    def screenshot_window(
        self,
        output: Path,
        *,
        window_id: int | None = None,
        bounds: WindowBounds | None = None,
    ) -> WindowBounds:
        bounds = bounds or self.window_bounds()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f"{output.stem}.tmp{output.suffix}")
        if window_id is not None and window_id > 0:
            result = subprocess.run(
                [
                    "screencapture",
                    "-x",
                    "-o",
                    "-l",
                    str(window_id),
                    str(temporary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and temporary.is_file():
                temporary.replace(output)
                return bounds
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise RuntimeError(
                f"Luminar window-id screenshot failed for {window_id}: {detail}"
            )
        region = f"{bounds.x},{bounds.y},{bounds.width},{bounds.height}"
        self._run(["screencapture", "-x", "-R", region, str(temporary)])
        temporary.replace(output)
        return bounds

    @staticmethod
    def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise RuntimeError(f"command failed ({command[0]}): {detail}")
        return result
