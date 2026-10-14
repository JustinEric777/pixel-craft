"""Read-only application ports for published runtime catalogs."""

from __future__ import annotations

from typing import Any, Protocol


class ManifestCatalog(Protocol):
    def models(self) -> dict[str, Any]:
        """Return the published model registry response."""

    def capabilities(self) -> list[dict[str, Any]]:
        """Return the published capability records."""
