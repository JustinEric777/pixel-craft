"""Pure workflow entities shared by the multi-image application service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowKind(StrEnum):
    HDR = "hdr_merge"
    FOCUS = "focus_stacking"
    PANORAMA = "panorama_stitching"

    @classmethod
    def parse(cls, value: str) -> WorkflowKind:
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            raise ValueError(f"unsupported workflow kind: {value}") from exc


@dataclass(frozen=True)
class WorkflowFrame:
    id: str
    filename: str
    path: str
    sha256: str
    width: int
    height: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class WorkflowSession:
    id: str
    kind: WorkflowKind
    root: str
    frames: list[WorkflowFrame] = field(default_factory=list)
    status: str = "draft"
    analysis: dict[str, Any] = field(default_factory=dict)
    preview_path: str | None = None
    export_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "root": self.root,
            "frames": [frame.to_dict() for frame in self.frames],
            "status": self.status,
            "analysis": self.analysis,
            "preview_path": self.preview_path,
            "export_path": self.export_path,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WorkflowSession:
        return cls(
            id=str(payload["id"]),
            kind=WorkflowKind.parse(str(payload["kind"])),
            root=str(payload["root"]),
            frames=[WorkflowFrame(**item) for item in payload.get("frames", [])],
            status=str(payload.get("status", "draft")),
            analysis=dict(payload.get("analysis", {})),
            preview_path=payload.get("preview_path"),
            export_path=payload.get("export_path"),
        )
