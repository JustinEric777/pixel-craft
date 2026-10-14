"""Filesystem-backed project repository for local single-user mode."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from core.project.entities import ImageRef, ProjectState
from core.project.serialization import load_project, save_project


class JsonProjectRepository:
    def __init__(
        self,
        root: Path,
        *,
        preview_root: Path,
    ) -> None:
        self.root = root
        self.preview_root = preview_root
        self.assets = root / "uploads"
        self.projects = root / "projects"
        self.assets.mkdir(parents=True, exist_ok=True)
        self.projects.mkdir(parents=True, exist_ok=True)

    def add_asset(
        self, filename: str, content: bytes, *, collection: str | None = None
    ) -> tuple[str, Path]:
        suffix = Path(filename).suffix.lower()
        asset_id = hashlib.sha256(content).hexdigest()[:24]
        safe_name = Path(filename).name or f"image{suffix}"
        safe_collection = Path(collection).name if collection else None
        parent = self.assets / safe_collection if safe_collection else self.assets
        target = parent / asset_id / safe_name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return asset_id, target

    def create_project(
        self, asset_path: Path, *, original_filename: str
    ) -> tuple[str, ProjectState]:
        project_id = uuid.uuid4().hex
        state = ProjectState(
            source=ImageRef(asset_path),
            metadata={
                "project_id": project_id,
                "version": 1,
                "original_filename": original_filename,
            },
        )
        self.save(project_id, state)
        return project_id, state

    def project_path(self, project_id: str) -> Path:
        return self.projects / f"{project_id}.json"

    def save(self, project_id: str, state: ProjectState) -> None:
        save_project(state, self.project_path(project_id))

    def load(self, project_id: str) -> ProjectState:
        path = self.project_path(project_id)
        if not path.is_file():
            raise FileNotFoundError(path)
        return load_project(path)
