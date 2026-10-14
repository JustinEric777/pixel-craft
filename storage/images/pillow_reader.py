"""Pillow adapter kept outside the application layer."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from PIL import Image


class PillowImageReader:
    def open(self, path: Path) -> AbstractContextManager[Any]:
        return Image.open(path)
