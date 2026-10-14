"""Application ports for adapters owned by infrastructure layers."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol

from core.project.entities import ProjectState


class ProjectRepository(Protocol):
    root: Path
    preview_root: Path

    def add_asset(
        self, filename: str, content: bytes, *, collection: str | None = None
    ) -> tuple[str, Path]:
        """Persist uploaded bytes and return their stable asset id/path."""

    def create_project(
        self, asset_path: Path, *, original_filename: str
    ) -> tuple[str, ProjectState]:
        """Create a project aggregate for a source image."""

    def save(self, project_id: str, state: ProjectState) -> None:
        """Persist a project aggregate."""

    def load(self, project_id: str) -> ProjectState:
        """Load a project aggregate."""


class CatalogRepository(Protocol):
    path: Path

    def records(self) -> list[dict[str, Any]]:
        """Read normalized records from the native Luminar catalog schema."""

    def upsert_asset(self, *, project_id: str, source: Path) -> str:
        """Insert or refresh one image and return its native catalog GUID."""

    def update_asset(self, asset_id: str, changes: dict[str, Any]) -> None:
        """Persist native user attributes for one image."""

class AssetCatalogPort(Protocol):
    payload: dict[str, Any]

    def list(self, family: str | None = None) -> list[dict[str, Any]]:
        """List manifest-backed assets."""

    def resolve(self, asset_id: str) -> Path:
        """Resolve a registered asset inside the configured root."""

    def layer_material_groups(self) -> list[dict[str, Any]]:
        """Return configured free overlay groups as logical materials."""

    def require_layer_material(self, material_id: str) -> dict[str, Any]:
        """Return one configured layer material."""

    def resolve_layer_material(self, material_id: str) -> Path:
        """Resolve one configured layer material inside the asset root."""


class ArtifactCachePort(Protocol):
    root: Path

    def source_hash(self, path: Path) -> str:
        """Return a content hash for a source image."""

    def list_records(self) -> list[dict[str, Any]]:
        """List cached artifact records."""


class ModelServicePort(Protocol):
    def analyze(
        self, image: Any, requested: list[str] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Run model-backed analysis."""

    def health(self) -> dict[str, Any]:
        """Return runtime health details."""

    def apply_image_effect(self, image: Any, effect: str, parameters: dict[str, Any]) -> Any:
        """Apply a model-backed image effect when available."""

    def execution(
        self, capability_ids: list[str], operation: str
    ) -> AbstractContextManager[dict[str, Any]]:
        """Collect request-scoped execution evidence."""

    def assert_effects_ready(self, capability_ids: list[str]) -> None:
        """Fail closed when the selected execution mode is not ready."""

    def capability_readiness(self, capability: dict[str, Any]) -> dict[str, Any]:
        """Return runtime and parity-backed capability readiness."""

class ProjectRenderer(Protocol):
    def render(self, state: ProjectState, *, asset_root: Path, model_service: Any) -> Any:
        """Render the current non-destructive edit graph."""
