"""Canonical paths for one captured Luminar parity case."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaptureLayout:
    root: Path
    case_id: str

    @property
    def output_dir(self) -> Path:
        return self.root / "luminar_outputs" / self.case_id

    @property
    def ui_dir(self) -> Path:
        return self.root / "luminar_ui" / self.case_id

    @property
    def metadata_path(self) -> Path:
        return self.root / "metadata" / f"{self.case_id}.json"

    @property
    def state_path(self) -> Path:
        return self.root / "state" / f"{self.case_id}.json"

    @property
    def event_log_path(self) -> Path:
        return self.root / "logs" / f"{self.case_id}.jsonl"

    @property
    def attempts_dir(self) -> Path:
        return self.root / "attempts" / self.case_id

    def attempt_path(self, attempt_id: str) -> Path:
        return self.attempts_dir / f"{attempt_id}.json"

    def attempt_event_log_path(self, attempt_id: str) -> Path:
        return self.attempts_dir / f"{attempt_id}.jsonl"

    @property
    def staging_dir(self) -> Path:
        return self.root / "staging" / self.case_id

    @property
    def staging_before_path(self) -> Path:
        return self.staging_dir / "before.png"

    @property
    def staging_after_path(self) -> Path:
        return self.staging_dir / "after.png"

    @property
    def staging_preview_path(self) -> Path:
        return self.staging_dir / "preview.png"

    @property
    def staging_before_ax_path(self) -> Path:
        return self.staging_dir / "before.ax.txt"

    @property
    def staging_after_ax_path(self) -> Path:
        return self.staging_dir / "after.ax.txt"

    @property
    def preview_path(self) -> Path:
        return self.output_dir / "preview.png"

    @property
    def export_path(self) -> Path:
        return self.output_dir / "export.png"

    def native_export_path(self, suffix: str) -> Path:
        return self.output_dir / f"native-export{suffix.lower()}"

    @property
    def mask_path(self) -> Path:
        return self.output_dir / "mask.png"

    @property
    def before_path(self) -> Path:
        return self.ui_dir / "before.png"

    @property
    def after_path(self) -> Path:
        return self.ui_dir / "after.png"

    @property
    def before_ax_path(self) -> Path:
        return self.ui_dir / "before.ax.txt"

    @property
    def after_ax_path(self) -> Path:
        return self.ui_dir / "after.ax.txt"

    def prepare(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ui_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.attempts_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
