"""Real local multi-image workflows used by HDR, focus and panorama tools.

The algorithms here are deliberately deterministic and dependency-light. They
are a functional baseline and produce real output; Luminar parity remains a
separate evidence gate until reference exports are captured.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, ClassVar

from PIL import Image

from core.errors import WorkflowInputError, WorkflowNotFoundError, WorkflowStateError
from core.workflow.entities import WorkflowFrame, WorkflowKind, WorkflowSession
from image_ops.merge import render_focus_stack, render_hdr, render_panorama


class MultiImageService:
    """Coordinate session persistence, frame validation and deterministic renders."""

    MIN_FRAMES = 2
    MAX_FRAMES = 20
    SUPPORTED_SUFFIXES: ClassVar[set[str]] = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

    def __init__(self, data_root: Path) -> None:
        self.root = data_root / "workflows"

    def create(self, kind: str) -> dict[str, Any]:
        try:
            workflow_kind = WorkflowKind.parse(kind)
        except ValueError as exc:
            raise WorkflowInputError(str(exc)) from exc
        workflow_id = uuid.uuid4().hex
        session_root = self.root / workflow_id
        session_root.mkdir(parents=True, exist_ok=True)
        session = WorkflowSession(workflow_id, workflow_kind, str(session_root))
        self._save(session)
        return session.to_dict()

    def add_frame(self, workflow_id: str, filename: str, content: bytes) -> dict[str, Any]:
        session = self._load(workflow_id)
        suffix = Path(filename or "frame.jpg").suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise WorkflowInputError("supported workflow frame formats: jpg, png, webp, tiff")
        if len(session.frames) >= self.MAX_FRAMES:
            raise WorkflowInputError(f"a workflow accepts at most {self.MAX_FRAMES} frames")
        try:
            with Image.open(__import__("io").BytesIO(content)) as image:
                image.verify()
            with Image.open(__import__("io").BytesIO(content)) as image:
                width, height = image.size
        except Exception as exc:
            raise WorkflowInputError("workflow frame is not a readable image") from exc
        digest = hashlib.sha256(content).hexdigest()
        frame_path = Path(session.root) / "frames" / f"{len(session.frames):02d}-{digest[:16]}{suffix}"
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        frame_path.write_bytes(content)
        session.frames.append(
            WorkflowFrame(digest[:24], filename, str(frame_path), digest, width, height)
        )
        session.status = "draft"
        session.analysis = {}
        self._save(session)
        return session.to_dict()

    def get(self, workflow_id: str) -> dict[str, Any]:
        return self._load(workflow_id).to_dict()

    def remove_frame(self, workflow_id: str, frame_id: str) -> dict[str, Any]:
        session = self._load(workflow_id)
        next_frames = [frame for frame in session.frames if frame.id != frame_id]
        if len(next_frames) == len(session.frames):
            raise WorkflowInputError(f"workflow frame not found: {frame_id}")
        session.frames = next_frames
        self._invalidate_render(session)
        self._save(session)
        return session.to_dict()

    def reorder_frames(self, workflow_id: str, frame_ids: list[str]) -> dict[str, Any]:
        session = self._load(workflow_id)
        current = {frame.id: frame for frame in session.frames}
        if len(frame_ids) != len(current) or set(frame_ids) != set(current):
            raise WorkflowInputError("frame_ids must contain every workflow frame exactly once")
        session.frames = [current[frame_id] for frame_id in frame_ids]
        self._invalidate_render(session)
        self._save(session)
        return session.to_dict()

    def analyze(self, workflow_id: str) -> dict[str, Any]:
        session = self._load(workflow_id)
        self._require_frame_count(session)
        sizes = [[frame.width, frame.height] for frame in session.frames]
        session.analysis = {
            "status": "ready",
            "frame_count": len(session.frames),
            "sizes": sizes,
            "same_dimensions": len({tuple(size) for size in sizes}) == 1,
            "kind": session.kind.value,
            "duplicate_frames": len(session.frames)
            - len({frame.sha256 for frame in session.frames}),
            "render_signature": self._render_signature(session),
            "reference_parity": "pending-reference-outputs",
        }
        session.status = "analyzed"
        self._save(session)
        return session.to_dict()

    def preview(self, workflow_id: str, *, export: bool = False) -> Path:
        session = self._load(workflow_id)
        self._require_frame_count(session)
        signature = self._render_signature(session)
        cached_preview = Path(session.preview_path) if session.preview_path else None
        if (
            export
            and cached_preview is not None
            and cached_preview.is_file()
            and session.analysis.get("render_signature") == signature
        ):
            target = Path(session.root) / "export.png"
            shutil.copyfile(cached_preview, target)
            session.export_path = str(target)
            session.status = "exported"
            self._save(session)
            return target
        images = self._load_images(session)
        output = self._render(session.kind, images)
        target = Path(session.root) / ("export.png" if export else "preview.png")
        output.save(target, format="PNG")
        if export:
            session.export_path = str(target)
            session.status = "exported"
        else:
            session.preview_path = str(target)
            session.status = "preview-ready"
        session.analysis = {
            **session.analysis,
            "status": "ready",
            "output_size": list(output.size),
            "render_signature": signature,
            "reference_parity": "pending-reference-outputs",
        }
        self._save(session)
        return target

    @staticmethod
    def _render_signature(session: WorkflowSession) -> str:
        payload = json.dumps(
            {
                "kind": session.kind.value,
                "frames": [frame.sha256 for frame in session.frames],
                "renderer_version": 2,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _invalidate_render(session: WorkflowSession) -> None:
        session.status = "draft"
        session.analysis = {}
        session.preview_path = None
        session.export_path = None

    def _load(self, workflow_id: str) -> WorkflowSession:
        path = self.root / workflow_id / "session.json"
        if not path.is_file():
            raise WorkflowNotFoundError(f"workflow not found: {workflow_id}")
        try:
            return WorkflowSession.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise WorkflowNotFoundError(f"workflow state is unreadable: {workflow_id}") from exc

    def _save(self, session: WorkflowSession) -> None:
        path = Path(session.root) / "session.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _require_frame_count(self, session: WorkflowSession) -> None:
        if len(session.frames) < self.MIN_FRAMES:
            raise WorkflowStateError(
                f"{session.kind.value} requires at least {self.MIN_FRAMES} image frames"
            )

    @staticmethod
    def _load_images(session: WorkflowSession) -> list[Image.Image]:
        images: list[Image.Image] = []
        try:
            for frame in session.frames:
                with Image.open(frame.path) as image:
                    images.append(image.convert("RGB"))
        except (OSError, ValueError) as exc:
            for image in images:
                image.close()
            raise WorkflowInputError("one or more workflow frames cannot be opened") from exc
        return images

    def _render(self, kind: WorkflowKind, images: list[Image.Image]) -> Image.Image:
        try:
            if kind is WorkflowKind.HDR:
                return render_hdr(images)
            if kind is WorkflowKind.FOCUS:
                return render_focus_stack(images)
            return render_panorama(images)
        finally:
            for image in images:
                image.close()
