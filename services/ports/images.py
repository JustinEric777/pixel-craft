"""Application ports for source-image access without binding to Pillow."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol


class ImageReader(Protocol):
    def open(self, path: Path) -> AbstractContextManager[Any]:
        """Open a source image for one application use case."""
